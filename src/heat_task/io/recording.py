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
    trial_n: int
    baseline: float
    target_temp: float
    ramp_up_onset_s: float | str
    hold_onset_s: float | str
    ramp_down_onset_s: float | str
    baseline_return_s: float | str
    rating: float
    rating_no_response: int
    trial_end_s: float
    sample_count: int


@dataclass(frozen=True, slots=True)
class TraceSample:
    sample_n: int
    time_s: float
    trial_n: int
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
    "trial_n",
    "baseline",
    "target_temp",
    "ramp_up_onset_s",
    "hold_onset_s",
    "ramp_down_onset_s",
    "baseline_return_s",
    "rating",
    "rating_no_response",
    "trial_end_s",
    "sample_count",
]

TRACE_COLUMNS = [
    "sample_n",
    "time_s",
    "trial_n",
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
        "program_word": run_config.program_word,
        "program_id": run_config.program_id,
        "trials": [
            {"baseline": trial.baseline, "target_temp": trial.target_temp}
            for trial in run_config.trials
        ],
    }
    study_params = {
        "initial_delay_s": run_config.initial_delay_s,
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
        n_trials=len(run_config.trials),
        frame_dur_s=(1.0 / frame_rate) if frame_rate else None,
        frame_dur_source="calibration",
    )
