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

from medoc.client import MedocClient
from medoc.models import ReturnCode
from medoc.ramp_hold import config, display, recorder
from medoc.ramp_hold.conditions import TrialConfig
from medoc.ramp_hold.detector import RampHoldDetector
from medoc.ramp_hold.input import clear_events, get_keys, wait_for_keys


@dataclass(frozen=True, slots=True)
class StatusSample:
    monotonic_time: float
    temperature: float
    system_state: int
    test_state: int
    test_time_ms: int


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
        next_poll_at = time.monotonic()
        while not self._stop_event.is_set():
            sample_time = time.monotonic()
            try:
                response = send_command(self._host, self._port, "status")
            except Exception:
                response = None

            if response is not None:
                self._queue.put(
                    StatusSample(
                        monotonic_time=sample_time,
                        temperature=response.temperature,
                        system_state=response.system_state,
                        test_state=response.test_state,
                        test_time_ms=response.test_time,
                    )
                )

            next_poll_at += config.POLL_INTERVAL_S
            sleep_for = next_poll_at - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)


@dataclass(slots=True)
class TrialState:
    trial_n: int
    trial: TrialConfig
    detector: RampHoldDetector
    ramp_up_onset_s: float | str = ""
    hold_onset_s: float | str = ""
    ramp_down_onset_s: float | str = ""
    baseline_return_s: float | str = ""
    rating: float | str = ""
    rating_rt_ms: float | str = ""
    rating_timeout: int = 0
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
    selected_rating = 0.0
    marker_x = -config.SLIDER_HALF_W

    while True:
        now_s = time.monotonic() - task_start
        for sample in poller.drain():
            trace_index += 1
            sample_time_s = sample.monotonic_time - task_start
            update = state.detector.update(sample.temperature)
            state.sample_count += 1

            if update.transitioned:
                if update.event == "ramp_up":
                    state.ramp_up_onset_s = round(sample_time_s, 3)
                elif update.event == "hold":
                    state.hold_onset_s = round(sample_time_s, 3)
                elif update.event == "ramp_down":
                    state.ramp_down_onset_s = round(sample_time_s, 3)
                    rating_active = True
                    rating_started_at = sample_time_s
                    selected_rating = 0.0
                    marker_x = -config.SLIDER_HALF_W
                    stimuli.mouse.setPos([-config.SLIDER_HALF_W, 0])
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
            marker_x = max(-config.SLIDER_HALF_W, min(config.SLIDER_HALF_W, raw_x))
            selected_rating = (marker_x + config.SLIDER_HALF_W) / (2 * config.SLIDER_HALF_W) * 10.0

            for key_name in _drain_key_names(
                kb,
                [*config.RATING_KEYS["confirm"], *config.QUIT_KEYS],
            ):
                if key_name in config.QUIT_KEYS:
                    core.quit()
                if key_name in config.RATING_KEYS["confirm"]:
                    state.rating = round(selected_rating, 2)
                    state.rating_rt_ms = round((now_s - rating_started_at) * 1000.0, 2)
                    rating_active = False
                    rating_complete = True
                    break

            if not rating_complete and stimuli.mouse.leftButtonPressed:
                state.rating = round(selected_rating, 2)
                state.rating_rt_ms = round((now_s - rating_started_at) * 1000.0, 2)
                rating_active = False
                rating_complete = True

            if rating_active and now_s - rating_started_at >= config.RATING_TIMEOUT_S:
                state.rating_timeout = 1
                rating_active = False
                rating_complete = True

        if rating_active:
            display.draw_rating(stimuli, marker_x)
        elif state.detector.phase == "ramp_up":
            display.draw_ready(stimuli)
        else:
            display.draw_crosshair(stimuli)
        win.flip()

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
                rating_rt_ms=state.rating_rt_ms,
                rating_timeout=state.rating_timeout,
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


def _wait_for_key(kb: keyboard.Keyboard | None, key_list: list[str]) -> str:
    pressed = wait_for_keys(kb, key_list)
    return pressed[0]


def _drain_key_names(kb: keyboard.Keyboard | None, key_list: list[str]) -> list[str]:
    return get_keys(kb, key_list)


def _check_quit(kb: keyboard.Keyboard | None) -> None:
    if _drain_key_names(kb, config.QUIT_KEYS):
        core.quit()
