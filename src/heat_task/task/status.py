"""Background Medoc status sampling.

StatusPoller runs in its own thread, opening a fresh MMS connection per poll and
pushing temperature samples (and the failures that produce none) onto queues the
render loop drains each frame.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

from heat_task import config
from heat_task.medoc.client import MedocClient

# Timestamps here use time.monotonic() rather than a psychopy core.Clock on
# purpose: this is a free-running background thread, and core.monotonicClock is
# itself a thin offset over time.monotonic(). Coupling the poller to PsychoPy's
# global clock would add a dependency without changing the numbers, and the task
# loop converts these stamps to a task-relative origin (task_start) anyway.


@dataclass(frozen=True, slots=True)
class StatusSample:
    monotonic_time: float
    temperature: float
    system_state: int
    test_state: int
    test_time_ms: int
    rtt_ms: float


@dataclass(frozen=True, slots=True)
class NetEvent:
    """A status-poll failure that produced no sample, with its cause and the gap
    since the last good sample. Lets the trace's silent gaps be explained."""

    monotonic_time: float
    cause: str  # "recv_timeout" | "status_error" | "connect_failure"
    detail: str
    gap_s: float


class StatusPoller:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._stop_event = threading.Event()
        self._queue: queue.SimpleQueue[StatusSample] = queue.SimpleQueue()
        self._events: queue.SimpleQueue[NetEvent] = queue.SimpleQueue()
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

    def drain_events(self) -> list[NetEvent]:
        items: list[NetEvent] = []
        while True:
            try:
                items.append(self._events.get_nowait())
            except queue.Empty:
                return items

    def _run(self) -> None:
        # The MMS serves exactly one response per TCP connection and then closes
        # it, so each poll opens a fresh socket. (Reusing one socket made every
        # second poll see the expected close and look like a failure.) On a
        # healthy LAN a connect costs a few ms; a connect that stalls or fails is
        # the real source of the rare multi-hundred-ms / ~1 s lag spikes.
        last_good = time.monotonic()  # for the gap_s reported on failures
        backoff = config.RECONNECT_BACKOFF_S
        while not self._stop_event.is_set():
            connect_start = time.monotonic()
            try:
                client = MedocClient.connect(
                    self._host,
                    self._port,
                    connect_timeout=config.CONNECT_TIMEOUT_S,
                    recv_timeout=config.POLL_RECV_TIMEOUT_S,
                )
            except Exception as exc:
                now = time.monotonic()
                self._events.put(
                    NetEvent(
                        monotonic_time=now,
                        cause="connect_failure",
                        detail=f"{type(exc).__name__}: {exc} "
                        f"(connect took {(now - connect_start) * 1000.0:.0f}ms)",
                        gap_s=now - last_good,
                    )
                )
                # Bounded exponential backoff so a down MMS isn't hammered. The
                # old flat 1 s sleep here was itself the ~1 s spike.
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2, config.RECONNECT_BACKOFF_MAX_S)
                continue
            backoff = config.RECONNECT_BACKOFF_S

            sample_time = time.monotonic()
            try:
                response, cause, detail = client.poll_status()
            except Exception as exc:  # send error, etc.
                response, cause, detail = None, "send_error", f"{type(exc).__name__}: {exc}"
            finally:
                client.close()  # the MMS closes after one response regardless

            if response is None:
                now = time.monotonic()
                self._events.put(
                    NetEvent(
                        monotonic_time=now,
                        cause=cause,
                        detail=detail,
                        gap_s=now - last_good,
                    )
                )
                continue

            last_good = time.monotonic()
            self._queue.put(
                StatusSample(
                    monotonic_time=sample_time,
                    temperature=response.temperature,
                    system_state=response.system_state,
                    test_state=response.test_state,
                    test_time_ms=response.test_time,
                    rtt_ms=(last_good - sample_time) * 1000.0,
                )
            )

            if config.POLL_INTERVAL_S > 0:
                time.sleep(config.POLL_INTERVAL_S)
