"""Tests for the ramp-and-hold recorder: CSV writers and the manifest wiring
onto psyexp_core."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from heat_task.io.conditions import RunConfig, SequenceConfig
from heat_task.io.recording import (
    BEHAVIOR_COLUMNS,
    BehaviorRecord,
    BehaviorWriter,
    write_manifest,
)
from heat_task.io.setup_wizard import SessionInfo


@dataclass
class _FakeScreenDiag:
    gl_vendor: str = "TestVendor"
    gl_renderer: str = "TestRenderer"
    win_type: str = "pyglet"
    pyglet_version: str = "2.0"
    platform_str: str = "test"
    calib_median_ms: float = 16.7
    calib_p99_ms: float = 17.0
    calib_max_ms: float = 18.0
    calib_n: int = 120
    monitor: object = None


def _run_config() -> RunConfig:
    return RunConfig(
        file_path=Path("conditions/example.toml"),
        program_word="00001111",
        sequences=(
            SequenceConfig(baseline=35.0, target_temp=46.0, time_before_s=5.0),
            SequenceConfig(baseline=35.0, target_temp=48.0),
        ),
    )


def test_behavior_csv_roundtrip(tmp_path: Path):
    path = tmp_path / "behavioral.csv"
    w = BehaviorWriter(path)
    w.append(
        BehaviorRecord(
            sequence_n=1, baseline_temp=35.0, target_temp=46.0,
            ramp_up_onset_s=1.0, hold_onset_s=2.0, ramp_down_onset_s=3.0,
            baseline_return_s=4.0, rating=5.0,
            rating_no_response=0, sequence_end_s=10.0, sample_count=120,
        )
    )
    w.close()
    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert set(rows[0].keys()) == set(BEHAVIOR_COLUMNS)
    assert rows[0]["target_temp"] == "46.0"


def test_write_manifest_merges_header_and_core_blocks(tmp_path: Path):
    session_info = SessionInfo(
        subject_id="S1", host="192.168.1.100", port=20121,
        run_file="example.toml", screen_index=0, show_instructions=True,
    )
    write_manifest(
        run_dir=tmp_path,
        session_info=session_info,
        session_time=datetime(2026, 6, 9, 14, 30, 0),
        run_config=_run_config(),
        frame_rate=60.0,
        screen_diag=_FakeScreenDiag(),
        win_res=[1920, 1080],
    )
    m = json.loads((tmp_path / "manifest.json").read_text())

    # heat-task header
    assert m["subject_id"] == "S1"
    assert m["host"] == "192.168.1.100"
    assert m["program_word"] == "00001111"
    assert m["n_trials"] == 2
    assert m["sequences"][1]["target_temp"] == 48.0
    assert m["sequences"][0]["time_before_s"] == 5.0
    assert "heat_task_version" in m

    # study params
    assert m["study_params"]["baseline_tolerance"] == 0.40

    # core-owned blocks
    assert "psyexp_core_version" in m
    assert "system" in m and "psychopy_version" in m["system"]
    assert m["display"]["resolution"] == [1920, 1080]
    assert m["display"]["vsync_calibration"]["n_samples"] == 120
    assert m["frame_rate_hz"] == 60.0
