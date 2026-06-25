"""Data recording for the ramp-and-hold task."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

from psyexp_core.manifest import write_manifest as _core_write_manifest
from psyexp_core.recording import CsvWriter

from heat_task import config

if TYPE_CHECKING:
    from psyexp_core.diagnostics import ScreenDiagnostics

    from heat_task.io.conditions import RunConfig
    from heat_task.io.setup_wizard import SessionInfo


@dataclass(frozen=True, slots=True)
class BehaviorRecord:
    sequence_n: int
    baseline_temp: float
    target_temp: float
    ramp_up_onset_s: float | str
    hold_onset_s: float | str
    ramp_down_onset_s: float | str
    baseline_return_s: float | str
    rating: float
    rating_no_response: int
    sequence_end_s: float
    sample_count: int

@dataclass(frozen=True, slots=True)
class TraceSample:
    """One row of the temperature trace: a single Medoc status sample polled
    during a sequence, enriched with the phase/event the tracker derived from it.
    One is written per poll, so the trace is the run sampled at the poll rate."""

    sample_n: int
    time_s: float
    sequence_n: int
    baseline: float
    target_temp: float
    raw_temperature: float
    smoothed_temperature: float
    phase: str
    transitioned: int
    event: str
    system_state: int
    test_state: int
    test_time_ms: int
    rtt_ms: float


@dataclass(frozen=True, slots=True)
class NetEventRecord:
    """A status-poll failure (timeout, decode error, or reconnect failure).

    Emitted when a poll produces no temperature sample, so the otherwise
    unexplained gaps in the temperature trace can be attributed after the fact.
    """

    time_s: float
    cause: str
    detail: str
    gap_s: float


BEHAVIOR_COLUMNS = [
    "sequence_n",
    "baseline_temp",
    "target_temp",
    "ramp_up_onset_s",
    "hold_onset_s",
    "ramp_down_onset_s",
    "baseline_return_s",
    "rating",
    "rating_no_response",
    "sequence_end_s",
    "sample_count",
]

TRACE_COLUMNS = [
    "sample_n",
    "time_s",
    "sequence_n",
    "baseline",
    "target_temp",
    "raw_temperature",
    "smoothed_temperature",
    "phase",
    "transitioned",
    "event",
    "system_state",
    "test_state",
    "test_time_ms",
    "rtt_ms",
]

NET_EVENT_COLUMNS = [
    "time_s",
    "cause",
    "detail",
    "gap_s",
]


class BehaviorWriter(CsvWriter):
    def __init__(self, path: Path) -> None:
        super().__init__(path, BEHAVIOR_COLUMNS)

    def append(self, record: BehaviorRecord) -> None:  # type: ignore[override]
        super().append(record)


class TraceWriter(CsvWriter):
    def __init__(self, path: Path) -> None:
        super().__init__(path, TRACE_COLUMNS)

    def append(self, record: TraceSample) -> None:  # type: ignore[override]
        super().append(record)


class NetEventWriter(CsvWriter):
    def __init__(self, path: Path) -> None:
        super().__init__(path, NET_EVENT_COLUMNS)

    def append(self, record: NetEventRecord) -> None:  # type: ignore[override]
        super().append(record)


def make_writers(
    run_dir: Path, file_stem: str, *, save_net_events: bool
) -> tuple[BehaviorWriter, TraceWriter, NetEventWriter | None]:
    """Open the per-run CSV writers; the net-event writer is created only when
    network diagnostics were requested."""
    behavior_writer = BehaviorWriter(run_dir / f"behavioral_{file_stem}.csv")
    trace_writer = TraceWriter(run_dir / f"temperature_trace_{file_stem}.csv")
    net_event_writer = (
        NetEventWriter(run_dir / f"net_events_{file_stem}.csv") if save_net_events else None
    )
    return behavior_writer, trace_writer, net_event_writer


def _heat_task_version() -> str:
    try:
        return version("heat-task")
    except PackageNotFoundError:
        return "unknown"


def write_manifest(
    run_dir: Path,
    session_info: SessionInfo,
    session_time: datetime,
    run_config: RunConfig,
    frame_rate: float,
    screen_diag: ScreenDiagnostics,
    win_res: list[int],
) -> None:
    """Write the run manifest via the shared harness, injecting the heat-task
    header and study parameters; psyexp_core fills in system/display/process."""
    header = {
        "heat_task_version": _heat_task_version(),
        "subject_id": session_info.subject_id,
        "host": session_info.host,
        "port": session_info.port,
        "run_file": session_info.run_file,
        "screen_index": session_info.screen_index,
        "program_word": run_config.program_word,
        "program_id": run_config.program_id,
        "sequences": [
            {
                "baseline": seq.baseline,
                "target_temp": seq.target_temp,
                "time_before_s": seq.time_before_s,
                "target_hold_duration_s": seq.target_hold_duration_s,
                "baseline_duration_s": seq.baseline_duration_s,
            }
            for seq in run_config.sequences
        ],
    }
    study_params = {
        "rating_timeout_s": config.RATING_TIMEOUT_S,
        "baseline_tolerance": config.BASELINE_TOLERANCE,
        "target_tolerance": config.TARGET_TOLERANCE,
        "ramp_start_delta": config.RAMP_START_DELTA,
        "ramp_down_delta": config.RAMP_DOWN_DELTA,
        "min_slope_per_sample": config.MIN_SLOPE_PER_SAMPLE,
        "smoothing_window": config.SMOOTHING_WINDOW,
        "trend_window": config.TREND_WINDOW,
        "consecutive_samples": config.CONSECUTIVE_SAMPLES,
    }
    _core_write_manifest(
        run_dir,
        header=header,
        session_time=session_time,
        screen_diag=screen_diag,
        win_res=win_res,
        study_params=study_params,
        frame_rate=frame_rate,
        n_trials=len(run_config.sequences),
        frame_dur_s=(1.0 / frame_rate) if frame_rate else None,
        frame_dur_source="calibration",
    )
