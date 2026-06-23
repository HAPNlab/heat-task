"""Trial runtime for the ramp-and-hold task.

run_trials() walks the run's trial schedule, threading the carry-over state
(continuous trace numbering and the previous baseline-return time) between
trials and writing each behavioural record.

run_trial() drives a single trial's render loop: it primes the phase tracker
ahead of scheduled transitions, drains Medoc status samples (writing the
temperature trace and detecting phase changes), runs the rating slider, and
returns the trial's behavioural record.

Prop drilling is kept in check with TrialRuntime: the dependencies that are
constant for the whole run (window, stimuli, keyboard, writers, poller, view,
run clock) are bundled once and passed as a single object, so only the
genuinely per-trial values stay as keyword arguments.
"""

from __future__ import annotations

from dataclasses import dataclass

from psychopy import core, visual
from psychopy.hardware import keyboard

from heat_task import config
from heat_task.io import recording
from heat_task.io.conditions import RunConfig, TrialConfig
from heat_task.task import display
from heat_task.task.console import TrialLiveView
from heat_task.task.phase_tracker import PhaseTracker, PhaseTrackerConfig
from heat_task.task.phases import check_quit
from heat_task.task.rating import RatingController
from heat_task.task.status import StatusPoller


@dataclass(slots=True)
class TrialRuntime:
    """Dependencies constant across the whole run, bundled to avoid prop drilling."""

    win: visual.Window
    stimuli: display.Stimuli
    kb: keyboard.Keyboard | None
    clock: core.Clock  # reads 0 at START; getTime() is already task-relative seconds
    trace_writer: recording.TraceWriter
    net_event_writer: recording.NetEventWriter | None
    poller: StatusPoller
    view: TrialLiveView | None = None


@dataclass(slots=True)
class TrialState:
    trial_n: int
    trial: TrialConfig
    tracker: PhaseTracker
    ramp_up_onset_s: float | str = ""
    hold_onset_s: float | str = ""
    ramp_down_onset_s: float | str = ""
    baseline_return_s: float | str = ""
    sample_count: int = 0


def run_trials(
    runtime: TrialRuntime,
    run_config: RunConfig,
    view: TrialLiveView,
    behavior_writer: recording.BehaviorWriter,
) -> None:
    """Run every trial in the schedule, carrying state between them."""
    # Running total of temperature-trace rows written; carried across trials so
    # the trace's sample_n column numbers continuously instead of resetting each
    # trial.
    trace_sample_count = 0
    # The previous trial's baseline-return time anchors when the next trial's
    # ramp-up is expected (see _maybe_prime_ramp_up); None until the first trial
    # completes, or whenever a baseline return wasn't detected.
    prev_baseline_return_s: float | None = None
    for trial_index, trial_config in enumerate(run_config.trials, start=1):
        view.start_trial(trial_index, trial_config.baseline, trial_config.target_temp)
        record, trace_sample_count = run_trial(
            runtime,
            trial_n=trial_index,
            trial_config=trial_config,
            trace_sample_count=trace_sample_count,
            initial_delay_s=run_config.initial_delay_s,
            prev_baseline_return_s=prev_baseline_return_s,
        )
        behavior_writer.append(record)
        prev_baseline_return_s = (
            record.baseline_return_s if isinstance(record.baseline_return_s, float) else None
        )


def run_trial(
    runtime: TrialRuntime,
    *,
    trial_n: int,
    trial_config: TrialConfig,
    trace_sample_count: int,
    initial_delay_s: float | None = None,
    prev_baseline_return_s: float | None = None,
) -> tuple[recording.BehaviorRecord, int]:
    """Run one complete ramp-hold trial and return its behavioural record."""
    state = TrialState(
        trial_n=trial_n,
        trial=trial_config,
        tracker=PhaseTracker(trial_config),
    )
    rating = RatingController(runtime.stimuli)
    ramp_up_primed = False
    ramp_down_primed = False

    while True:
        now_s = runtime.clock.getTime()

        if not ramp_up_primed:
            ramp_up_primed = _maybe_prime_ramp_up(
                state, now_s, initial_delay_s, prev_baseline_return_s
            )
        if not ramp_down_primed:
            ramp_down_primed = _maybe_prime_ramp_down(state, now_s)

        trace_sample_count = _drain_samples(runtime, state, rating, trace_sample_count)
        _drain_net_events(runtime)

        check_quit(runtime.kb)

        if rating.update(now_s) and runtime.view is not None:
            runtime.view.on_rating(rating.rating, bool(rating.no_response))

        _draw_frame(runtime, state, rating)
        # Heartbeat the console every frame so the "● Live" blink keeps pulsing
        # even during gaps in MMS polling (throttled inside the view).
        if runtime.view is not None:
            runtime.view.tick()

        if state.tracker.phase == "complete" and rating.complete:
            record = _build_record(state, trial_config, runtime.clock, rating)
            return record, trace_sample_count


def _maybe_prime_ramp_up(
    state: TrialState,
    now_s: float,
    initial_delay_s: float | None,
    prev_baseline_return_s: float | None,
) -> bool:
    """Switch the tracker to twitchy params as the scheduled ramp-up nears.

    The expected ramp-up time is the initial delay on trial 1, otherwise the
    previous trial's baseline-return time plus this trial's baseline duration.
    """
    if state.tracker.phase != "baseline":
        return False
    trial = state.trial
    if state.trial_n == 1 and initial_delay_s is not None:
        ready = now_s >= initial_delay_s - config.PRIME_WINDOW_S
    elif trial.baseline_duration_s is not None and prev_baseline_return_s is not None:
        scheduled = prev_baseline_return_s + trial.baseline_duration_s
        ready = now_s >= scheduled - config.PRIME_WINDOW_S
    else:
        return False
    if ready:
        state.tracker.prime(PhaseTrackerConfig.primed())
        return True
    return False


def _maybe_prime_ramp_down(state: TrialState, now_s: float) -> bool:
    """Switch the tracker to twitchy params as the scheduled ramp-down nears."""
    trial = state.trial
    if (
        state.tracker.phase == "hold"
        and trial.target_hold_duration_s is not None
        and isinstance(state.hold_onset_s, float)
        and now_s >= state.hold_onset_s + trial.target_hold_duration_s - config.PRIME_WINDOW_S
    ):
        state.tracker.prime(PhaseTrackerConfig.primed())
        return True
    return False


def _drain_samples(
    runtime: TrialRuntime,
    state: TrialState,
    rating: RatingController,
    trace_sample_count: int,
) -> int:
    """Process every queued status sample: update the tracker, record onsets and
    the temperature trace, and arm the rating slider on ramp-down.

    trace_sample_count is the running total of trace rows written so far across
    all trials; it carries across trials so sample_n numbers the trace
    continuously rather than restarting each trial."""
    for sample in runtime.poller.drain():
        trace_sample_count += 1
        sample_time_s = sample.time_s
        update = state.tracker.update(sample.temperature)
        state.sample_count += 1
        if runtime.view is not None:
            runtime.view.on_sample(update.smoothed_temperature, update.phase, sample.rtt_ms)

        if update.transitioned:
            _record_transition(state, rating, update.event, sample_time_s, runtime.kb)

        runtime.trace_writer.append(
            recording.TraceSample(
                sample_n=trace_sample_count,
                time_s=round(sample_time_s, 6),
                trial_n=state.trial_n,
                baseline=state.trial.baseline,
                target_temp=state.trial.target_temp,
                raw_temperature=round(update.raw_temperature, 4),
                smoothed_temperature=round(update.smoothed_temperature, 4),
                phase=update.phase,
                transitioned=int(update.transitioned),
                event=update.event or "",
                system_state=sample.system_state,
                test_state=sample.test_state,
                test_time_ms=sample.test_time_ms,
                rtt_ms=round(sample.rtt_ms, 3),
            )
        )
    return trace_sample_count


def _record_transition(
    state: TrialState,
    rating: RatingController,
    event: str | None,
    sample_time_s: float,
    kb: keyboard.Keyboard | None,
) -> None:
    if event == "ramp_up":
        state.ramp_up_onset_s = round(sample_time_s, 3)
    elif event == "hold":
        state.hold_onset_s = round(sample_time_s, 3)
    elif event == "ramp_down":
        state.ramp_down_onset_s = round(sample_time_s, 3)
        rating.begin(sample_time_s, kb)
    elif event == "complete":
        state.baseline_return_s = round(sample_time_s, 3)


def _drain_net_events(runtime: TrialRuntime) -> None:
    for event in runtime.poller.drain_events():
        if runtime.net_event_writer is not None:
            runtime.net_event_writer.append(
                recording.NetEventRecord(
                    time_s=round(event.time_s, 6),
                    cause=event.cause,
                    detail=event.detail,
                    gap_s=round(event.gap_s, 4),
                )
            )
        if runtime.view is not None:
            runtime.view.on_net_event()


def _draw_frame(runtime: TrialRuntime, state: TrialState, rating: RatingController) -> None:
    if rating.active:
        rating.draw()
    elif state.tracker.phase == "ramp_up":
        display.draw_ready(runtime.stimuli)
    else:
        display.draw_crosshair(runtime.stimuli)
    runtime.win.flip()


def _build_record(
    state: TrialState,
    trial_config: TrialConfig,
    clock: core.Clock,
    rating: RatingController,
) -> recording.BehaviorRecord:
    return recording.BehaviorRecord(
        trial_n=state.trial_n,
        baseline=trial_config.baseline,
        target_temp=trial_config.target_temp,
        ramp_up_onset_s=state.ramp_up_onset_s,
        hold_onset_s=state.hold_onset_s,
        ramp_down_onset_s=state.ramp_down_onset_s,
        baseline_return_s=state.baseline_return_s,
        rating=rating.rating,
        rating_no_response=rating.no_response,
        trial_end_s=round(clock.getTime(), 3),
        sample_count=state.sample_count,
    )
