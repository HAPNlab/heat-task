"""
Phase helpers and one-trial runtime for the ramp-and-hold task.
Owns keyboard polling during the active task and Medoc status sampling.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

from psychopy import core, visual
from psychopy.hardware import keyboard
from rich.console import Console

from heat_task import config, display, recorder
from heat_task.conditions import TrialConfig
from heat_task.console import TrialLiveView
from heat_task.detector import DetectorConfig, RampHoldDetector
from heat_task.input import clear_events, get_keys, wait_for_keys
from heat_task.medoc.client import MedocClient
from heat_task.medoc.models import ReturnCode


@dataclass(frozen=True, slots=True)
class StatusSample:
    monotonic_time: float
    temperature: float
    system_state: int
    test_state: int
    test_time_ms: int
    rtt_ms: float


class StatusPoller:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._stop_event = threading.Event()
        self._queue: queue.SimpleQueue[StatusSample] = queue.SimpleQueue()
        self._thread = threading.Thread(target=self._run, name="medoc-status-poller", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def drain(self) -> list[StatusSample]:
        items: list[StatusSample] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                return items

    def _run(self) -> None:
        client: MedocClient | None = None
        while not self._stop_event.is_set():
            if client is None:
                try:
                    client = MedocClient.connect(
                        self._host,
                        self._port,
                        connect_timeout=config.CONNECT_TIMEOUT_S,
                        recv_timeout=config.POLL_RECV_TIMEOUT_S,
                    )
                except Exception:
                    time.sleep(1.0)
                    continue

            sample_time = time.monotonic()
            try:
                response = client.status()
            except Exception:
                response = None

            if response is None:
                # Timeout or an undecodable frame: the long-lived stream may be
                # desynced (a mid-frame timeout leaves bytes unread). Drop the
                # socket and reconnect to resynchronise rather than reusing it
                # and emitting garbage — that is what caused multi-second stalls.
                client.close()
                client = None
                continue

            self._queue.put(
                StatusSample(
                    monotonic_time=sample_time,
                    temperature=response.temperature,
                    system_state=response.system_state,
                    test_state=response.test_state,
                    test_time_ms=response.test_time,
                    rtt_ms=(time.monotonic() - sample_time) * 1000.0,
                )
            )

            if config.POLL_INTERVAL_S > 0:
                time.sleep(config.POLL_INTERVAL_S)

        if client is not None:
            client.close()


@dataclass(slots=True)
class TrialState:
    trial_n: int
    trial: TrialConfig
    detector: RampHoldDetector
    ramp_up_onset_s: float | str = ""
    hold_onset_s: float | str = ""
    ramp_down_onset_s: float | str = ""
    baseline_return_s: float | str = ""
    rating: float = config.RATING_MIN
    rating_no_response: int = 0
    sample_count: int = 0


def wait_for_start(
    win: visual.Window,
    stimuli: display.Stimuli,
    kb: keyboard.Keyboard | None,
) -> None:
    """Keep the participant crosshair onscreen until the experimenter starts."""
    clear_events(kb)
    while True:
        display.draw_crosshair(stimuli)
        win.flip()
        key_name = _wait_for_key(kb, [*config.START_KEYS, *config.QUIT_KEYS])
        if key_name in config.QUIT_KEYS:
            core.quit()
        if key_name in config.START_KEYS:
            return


def run_end_screen(
    win: visual.Window,
    stimuli: display.Stimuli,
    kb: keyboard.Keyboard | None,
) -> None:
    """Show the closing screen until the operator dismisses it."""
    clear_events(kb)
    while True:
        display.draw_end(stimuli)
        win.flip()
        key_name = _wait_for_key(kb, [*config.END_KEYS, *config.QUIT_KEYS])
        if key_name in config.QUIT_KEYS:
            core.quit()
        if key_name in config.END_KEYS:
            return


def run_trial(
    *,
    win: visual.Window,
    stimuli: display.Stimuli,
    kb: keyboard.Keyboard | None,
    task_start: float,
    trial_n: int,
    trial_config: TrialConfig,
    trace_index: int,
    trace_writer: recorder.TraceWriter,
    poller: StatusPoller,
    initial_delay_s: float | None = None,
    prev_baseline_return_s: float | None = None,
    view: TrialLiveView | None = None,
) -> tuple[recorder.BehaviorRecord, int]:
    """Run one complete ramp-hold trial and return its behavioural record."""
    state = TrialState(
        trial_n=trial_n,
        trial=trial_config,
        detector=RampHoldDetector(trial_config),
    )
    rating_active = False
    rating_started_at = 0.0
    rating_complete = False
    rating_interacted = False
    rating_start_x = 0.0
    marker_x = -config.SLIDER_HALF_W
    ramp_up_primed = False
    ramp_down_primed = False

    while True:
        now_s = time.monotonic() - task_start

        if not ramp_up_primed and state.detector.phase == "baseline":
            if trial_n == 1 and initial_delay_s is not None:
                if now_s >= initial_delay_s - config.PRIME_WINDOW_S:
                    state.detector.prime(DetectorConfig.primed())
                    ramp_up_primed = True
            elif trial_config.baseline_duration_s is not None and prev_baseline_return_s is not None:
                if now_s >= prev_baseline_return_s + trial_config.baseline_duration_s - config.PRIME_WINDOW_S:
                    state.detector.prime(DetectorConfig.primed())
                    ramp_up_primed = True

        if (
            not ramp_down_primed
            and state.detector.phase == "hold"
            and trial_config.target_hold_duration_s is not None
            and isinstance(state.hold_onset_s, float)
            and now_s >= state.hold_onset_s + trial_config.target_hold_duration_s - config.PRIME_WINDOW_S
        ):
            state.detector.prime(DetectorConfig.primed())
            ramp_down_primed = True

        for sample in poller.drain():
            trace_index += 1
            sample_time_s = sample.monotonic_time - task_start
            update = state.detector.update(sample.temperature)
            state.sample_count += 1
            if view is not None:
                view.on_sample(update.smoothed_temperature, update.phase, sample.rtt_ms)

            if update.transitioned:
                if update.event == "ramp_up":
                    state.ramp_up_onset_s = round(sample_time_s, 3)
                elif update.event == "hold":
                    state.hold_onset_s = round(sample_time_s, 3)
                elif update.event == "ramp_down":
                    state.ramp_down_onset_s = round(sample_time_s, 3)
                    rating_active = True
                    rating_started_at = sample_time_s
                    rating_interacted = False
                    marker_x = -config.SLIDER_HALF_W
                    stimuli.mouse.setPos([-config.SLIDER_HALF_W, 0])
                    rating_start_x = stimuli.mouse.getPos()[0]
                    clear_events(kb)
                elif update.event == "complete":
                    state.baseline_return_s = round(sample_time_s, 3)

            trace_writer.append(
                recorder.TraceSample(
                    sample_n=trace_index,
                    time_s=round(sample_time_s, 6),
                    trial_n=state.trial_n,
                    baseline=trial_config.baseline,
                    target_temp=trial_config.target_temp,
                    raw_temperature=round(update.raw_temperature, 4),
                    smoothed_temperature=round(update.smoothed_temperature, 4),
                    phase=update.phase,
                    transitioned=int(update.transitioned),
                    event=update.event or "",
                    system_state=sample.system_state,
                    test_state=sample.test_state,
                    test_time_ms=sample.test_time_ms,
                )
            )

        _check_quit(kb)

        if rating_active:
            raw_x = stimuli.mouse.getPos()[0]
            if abs(raw_x - rating_start_x) > config.SLIDER_INTERACT_EPS:
                rating_interacted = True
            selected_rating, marker_x = _snap_rating(raw_x)

            if now_s - rating_started_at >= config.RATING_TIMEOUT_S:
                state.rating = selected_rating
                state.rating_no_response = 0 if rating_interacted else 1
                rating_active = False
                rating_complete = True

            if rating_complete and not rating_active and view is not None:
                view.on_rating(state.rating, bool(state.rating_no_response))

        if rating_active:
            display.draw_rating(stimuli, marker_x)
        elif state.detector.phase == "ramp_up":
            display.draw_ready(stimuli)
        else:
            display.draw_crosshair(stimuli)
        win.flip()

        # Heartbeat the console every frame so the "● Live" blink keeps pulsing
        # even during gaps in MMS polling (throttled inside the view).
        if view is not None:
            view.tick()

        if state.detector.phase == "complete" and rating_complete:
            return recorder.BehaviorRecord(
                trial_n=state.trial_n,
                baseline=trial_config.baseline,
                target_temp=trial_config.target_temp,
                ramp_up_onset_s=state.ramp_up_onset_s,
                hold_onset_s=state.hold_onset_s,
                ramp_down_onset_s=state.ramp_down_onset_s,
                baseline_return_s=state.baseline_return_s,
                rating=state.rating,
                rating_no_response=state.rating_no_response,
                trial_end_s=round(time.monotonic() - task_start, 3),
                sample_count=state.sample_count,
            ), trace_index


def send_command(host: str, port: int, method_name: str, *args: object):
    with MedocClient.connect(
        host,
        port,
        connect_timeout=config.CONNECT_TIMEOUT_S,
        recv_timeout=config.RECV_TIMEOUT_S,
    ) as client:
        method = getattr(client, method_name)
        return method(*args)


def require_ok(console: Console, label: str, response) -> None:
    if response is None:
        raise RuntimeError(f"{label} failed: no response from MMS")
    if response.return_code != int(ReturnCode.OK):
        flags = _decode_return_code(response.return_code)
        raise RuntimeError(f"{label} failed: {flags} (code {response.return_code})")
    console.print(f"[green]{label} ok[/green]")


def _decode_return_code(code: int) -> str:
    """Decode a bitfield return code into human-readable flag names."""
    flag_bits = {
        ReturnCode.ILLEGAL_ARG: "ILLEGAL_ARG",
        ReturnCode.ILLEGAL_STATE: "ILLEGAL_STATE",
        ReturnCode.ILLEGAL_TEST_STATE: "ILLEGAL_TEST_STATE",
        ReturnCode.DEVICE_COMM_ERROR: "DEVICE_COMM_ERROR",
        ReturnCode.SAFETY_WARNING: "SAFETY_WARNING",
        ReturnCode.SAFETY_ERROR: "SAFETY_ERROR",
    }
    names = [name for flag, name in flag_bits.items() if code & int(flag)]
    return " | ".join(names) if names else f"UNKNOWN({code})"


def _snap_rating(raw_x: float) -> tuple[int, float]:
    """Snap a raw mouse x to an integer rating (0..10) and its marker x."""
    clamped = max(-config.SLIDER_HALF_W, min(config.SLIDER_HALF_W, raw_x))
    frac = (clamped + config.SLIDER_HALF_W) / (2 * config.SLIDER_HALF_W)
    span = config.RATING_MAX - config.RATING_MIN
    value = config.RATING_MIN + round(frac * span)
    marker_x = -config.SLIDER_HALF_W + (value - config.RATING_MIN) / span * (2 * config.SLIDER_HALF_W)
    return value, marker_x


def _wait_for_key(kb: keyboard.Keyboard | None, key_list: list[str]) -> str:
    pressed = wait_for_keys(kb, key_list)
    return pressed[0]


def _drain_key_names(kb: keyboard.Keyboard | None, key_list: list[str]) -> list[str]:
    return get_keys(kb, key_list)


def _check_quit(kb: keyboard.Keyboard | None) -> None:
    if _drain_key_names(kb, config.QUIT_KEYS):
        core.quit()
