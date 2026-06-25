"""Sequence runtime for the ramp-and-hold task.

run_sequences() walks the run's sequence schedule, threading the continuous
trace-sample numbering between sequences and writing each behavioural record.

run_sequence() drives a single sequence's render loop: it primes the phase
tracker ahead of scheduled transitions, drains Medoc status samples (writing the
temperature trace and detecting phase changes), runs the rating slider, holds
out the sequence's trailing baseline, and returns the behavioural record.

Each sequence owns the baseline period that *follows* its ramp-down (the MMS
ISI): after the temperature returns to baseline the loop keeps running until
baseline_duration_s has elapsed, so the trailing baseline is recorded in full
before the sequence ends. The final sequence is no different — its trailing
baseline is what the run sits through before the closing screen appears, so no
end-of-run special case is needed.

Prop drilling is kept in check with SequenceRuntime: the dependencies that are
constant for the whole run (window, stimuli, keyboard, writers, poller, view,
run clock) are bundled once and passed as a single object, so only the
genuinely per-sequence values stay as keyword arguments.
"""

from __future__ import annotations

from dataclasses import dataclass

from psychopy import core, visual
from psychopy.hardware import keyboard

from heat_task import config
from heat_task.io import recording
from heat_task.io.conditions import RunConfig, SequenceConfig
from heat_task.task import display
from heat_task.task.console import SequenceLiveView
from heat_task.task.phase_tracker import PhaseTracker, PhaseTrackerConfig
from heat_task.task.phases import check_quit
from heat_task.task.rating import RatingController
from heat_task.task.status import StatusPoller


@dataclass(slots=True)
class SequenceRuntime:
    """Dependencies constant across the whole run, bundled to avoid prop drilling."""

    win: visual.Window
    stimuli: display.Stimuli
    kb: keyboard.Keyboard | None
    clock: core.Clock  # reads 0 at START; getTime() is already task-relative seconds
    trace_writer: recording.TraceWriter
    net_event_writer: recording.NetEventWriter | None
    poller: StatusPoller
    view: SequenceLiveView | None = None


@dataclass(slots=True)
class SequenceState:
    sequence_n: int
    sequence: SequenceConfig
    tracker: PhaseTracker
    ramp_up_onset_s: float | str = ""
    hold_onset_s: float | str = ""
    ramp_down_onset_s: float | str = ""
    baseline_return_s: float | str = ""
    sample_count: int = 0


def run_sequences(
    runtime: SequenceRuntime,
    run_config: RunConfig,
    view: SequenceLiveView,
    behavior_writer: recording.BehaviorWriter,
) -> None:
    """Run every sequence in the schedule, carrying the trace numbering between them."""
    # Running total of temperature-trace rows written; carried across sequences so
    # the trace's sample_n column numbers continuously instead of resetting each
    # sequence.
    trace_sample_count = 0
    for seq_index, seq_config in enumerate(run_config.sequences, start=1):
        view.start_sequence(seq_index, seq_config.baseline, seq_config.target_temp)
        record, trace_sample_count = run_sequence(
            runtime,
            sequence_n=seq_index,
            sequence_config=seq_config,
            trace_sample_count=trace_sample_count,
        )
        behavior_writer.append(record)


def run_sequence(
    runtime: SequenceRuntime,
    *,
    sequence_n: int,
    sequence_config: SequenceConfig,
    trace_sample_count: int,
) -> tuple[recording.BehaviorRecord, int]:
    """Run one complete ramp-hold sequence and return its behavioural record.

    The render loop continues past the ramp-down and baseline return until the
    sequence's trailing baseline (baseline_duration_s) has elapsed, so that
    period is recorded before the sequence ends."""
    state = SequenceState(
        sequence_n=sequence_n,
        sequence=sequence_config,
        tracker=PhaseTracker(sequence_config),
    )
    rating = RatingController(runtime.stimuli)
    # The sequence's clock starts now (right after the previous sequence's
    # trailing baseline); its ramp-up is expected time_before_s later.
    sequence_start_s = runtime.clock.getTime()
    ramp_up_primed = False
    ramp_down_primed = False

    while True:
        now_s = runtime.clock.getTime()

        if not ramp_up_primed:
            ramp_up_primed = _maybe_prime_ramp_up(state, now_s, sequence_start_s)
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

        if (
            state.tracker.phase == "complete"
            and rating.complete
            and _baseline_elapsed(state, now_s)
        ):
            record = _build_record(state, sequence_config, runtime.clock, rating)
            return record, trace_sample_count


def _maybe_prime_ramp_up(
    state: SequenceState, now_s: float, sequence_start_s: float
) -> bool:
    """Switch the tracker to twitchy params as the scheduled ramp-up nears.

    The ramp-up is expected the sequence's time_before_s lead-in after the
    sequence began (0 for every sequence but the first, so they prime as soon as
    they start)."""
    if state.tracker.phase != "baseline":
        return False
    scheduled = sequence_start_s + state.sequence.time_before_s
    if now_s >= scheduled - config.PRIME_WINDOW_S:
        state.tracker.prime(PhaseTrackerConfig.primed())
        return True
    return False


def _maybe_prime_ramp_down(state: SequenceState, now_s: float) -> bool:
    """Switch the tracker to twitchy params as the scheduled ramp-down nears."""
    sequence = state.sequence
    if (
        state.tracker.phase == "hold"
        and sequence.target_hold_duration_s is not None
        and isinstance(state.hold_onset_s, float)
        and now_s >= state.hold_onset_s + sequence.target_hold_duration_s - config.PRIME_WINDOW_S
    ):
        state.tracker.prime(PhaseTrackerConfig.primed())
        return True
    return False


def _baseline_elapsed(state: SequenceState, now_s: float) -> bool:
    """Whether the sequence's trailing baseline period has fully elapsed.

    True immediately when no baseline duration is configured; otherwise once
    baseline_duration_s has passed since the baseline return. The
    baseline_return_s guard means a sequence never hangs if the return was never
    detected (the tracker wouldn't be "complete" in that case anyway)."""
    duration = state.sequence.baseline_duration_s
    if duration is None:
        return True
    if not isinstance(state.baseline_return_s, float):
        return True
    return now_s >= state.baseline_return_s + duration


def _drain_samples(
    runtime: SequenceRuntime,
    state: SequenceState,
    rating: RatingController,
    trace_sample_count: int,
) -> int:
    """Process every queued status sample: update the tracker, record onsets and
    the temperature trace, and arm the rating slider on ramp-down.

    trace_sample_count is the running total of trace rows written so far across
    all sequences; it carries across sequences so sample_n numbers the trace
    continuously rather than restarting each sequence."""
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
                sequence_n=state.sequence_n,
                baseline=state.sequence.baseline,
                target_temp=state.sequence.target_temp,
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
    state: SequenceState,
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


def _drain_net_events(runtime: SequenceRuntime) -> None:
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


def _draw_frame(runtime: SequenceRuntime, state: SequenceState, rating: RatingController) -> None:
    if rating.active:
        rating.draw()
    elif state.tracker.phase == "ramp_up":
        display.draw_ready(runtime.stimuli)
    else:
        display.draw_crosshair(runtime.stimuli)
    runtime.win.flip()


def _build_record(
    state: SequenceState,
    sequence_config: SequenceConfig,
    clock: core.Clock,
    rating: RatingController,
) -> recording.BehaviorRecord:
    return recording.BehaviorRecord(
        sequence_n=state.sequence_n,
        baseline_temp=sequence_config.baseline,
        target_temp=sequence_config.target_temp,
        ramp_up_onset_s=state.ramp_up_onset_s,
        hold_onset_s=state.hold_onset_s,
        ramp_down_onset_s=state.ramp_down_onset_s,
        baseline_return_s=state.baseline_return_s,
        rating=rating.rating,
        rating_no_response=rating.no_response,
        sequence_end_s=round(clock.getTime(), 3),
        sample_count=state.sample_count,
    )
