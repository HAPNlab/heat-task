"""Data recording for the ramp-and-hold task."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from medoc.ramp_hold.conditions import RunConfig
    from medoc.ramp_hold.session import SessionInfo


@dataclass(frozen=True, slots=True)
class BehaviorRecord:
    trial_n: int
    baseline: float
    target_temp: float
    ramp_up_onset_s: float | str
    hold_onset_s: float | str
    ramp_down_onset_s: float | str
    baseline_return_s: float | str
    rating: int | str
    rating_rt_ms: float | str
    rating_timeout: int
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


BEHAVIOR_COLUMNS = [
    "trial_n",
    "baseline",
    "target_temp",
    "ramp_up_onset_s",
    "hold_onset_s",
    "ramp_down_onset_s",
    "baseline_return_s",
    "rating",
    "rating_rt_ms",
    "rating_timeout",
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
]


class CsvWriter:
    def __init__(self, path: Path, columns: list[str]) -> None:
        self._file = open(path, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=columns)
        self._writer.writeheader()
        self._columns = columns

    def append(self, record: object) -> None:
        row = {name: getattr(record, name) for name in self._columns}
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


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


def write_manifest(
    run_dir: Path,
    session_info: "SessionInfo",
    session_time: datetime,
    run_config: "RunConfig",
    frame_rate: float,
) -> None:
    manifest = {
        "subject_id": session_info.subject_id,
        "host": session_info.host,
        "port": session_info.port,
        "run_file": session_info.run_file,
        "program_word": run_config.program_word,
        "program_id": run_config.program_id,
        "session_time": session_time.isoformat(timespec="seconds"),
        "frame_rate_hz": round(frame_rate, 3),
        "n_trials": len(run_config.trials),
        "trials": [
            {"baseline": trial.baseline, "target_temp": trial.target_temp}
            for trial in run_config.trials
        ],
    }
    with open(run_dir / "manifest.json", "w") as handle:
        json.dump(manifest, handle, indent=2)
