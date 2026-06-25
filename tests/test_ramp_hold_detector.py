"""Tests for the ramp-and-hold phase tracker."""

from __future__ import annotations

from heat_task.io.conditions import SequenceConfig
from heat_task.task.phase_tracker import PhaseTracker, PhaseTrackerConfig


def test_detector_transitions_through_all_phases() -> None:
    tracker = PhaseTracker(
        SequenceConfig(baseline=32.0, target_temp=45.0),
        PhaseTrackerConfig(
            smoothing_window=3,
            trend_window=3,
            consecutive_samples=2,
            baseline_tolerance=0.5,
            target_tolerance=0.5,
            ramp_start_delta=0.2,
            ramp_down_delta=0.3,
            min_slope_per_sample=0.02,
        ),
    )
    samples = [
        32.0,
        32.1,
        32.4,
        33.0,
        34.2,
        44.7,
        45.1,
        45.0,
        44.6,
        44.1,
        40.0,
        32.4,
        32.1,
        32.0,
        32.0,
    ]

    events = [
        update.event
        for update in (tracker.update(value) for value in samples)
        if update.event
    ]

    assert events == ["ramp_up", "hold", "ramp_down", "complete"]


def test_detector_completes_when_next_ramp_starts_before_baseline_return() -> None:
    """When temperature doesn't return to baseline before the next ramp, the detector
    should still transition to complete once the new upward ramp is detected."""
    tracker = PhaseTracker(
        SequenceConfig(baseline=30.0, target_temp=45.0),
        PhaseTrackerConfig(
            smoothing_window=3,
            trend_window=3,
            consecutive_samples=2,
            baseline_tolerance=0.5,
            target_tolerance=0.5,
            ramp_start_delta=0.2,
            ramp_down_delta=0.3,
            min_slope_per_sample=0.02,
        ),
    )
    # Ramp up from 35 (thermode resting temp, well above 30 baseline) to ~45, hold, ramp down
    # only to ~32 (never reaches 30 baseline), then next trial ramp starts.
    samples = [
        35.0, 35.0,           # baseline phase (flat, no upward trend)
        35.5, 36.5,           # ramp up starts
        40.0, 44.8, 45.1,    # approaching hold
        45.0, 45.0,           # hold
        44.5, 43.0,           # ramp down starts
        38.0, 34.0, 32.0,    # dropping but never reaching 30.0
        32.5, 33.5,           # next trial ramp starts (rising above 30.2)
        35.0, 37.0, 39.0,    # rising more steeply
    ]

    events = [
        update.event
        for update in (tracker.update(value) for value in samples)
        if update.event
    ]

    assert events == ["ramp_up", "hold", "ramp_down", "complete"]


def test_detector_ignores_small_hold_fluctuations() -> None:
    tracker = PhaseTracker(
        SequenceConfig(baseline=32.0, target_temp=45.0),
        PhaseTrackerConfig(
            smoothing_window=3,
            trend_window=3,
            consecutive_samples=2,
            baseline_tolerance=0.5,
            target_tolerance=0.5,
            ramp_start_delta=0.2,
            ramp_down_delta=0.5,
            min_slope_per_sample=0.02,
        ),
    )
    samples = [32.0, 32.2, 32.5, 33.1, 44.8, 45.0, 45.1, 44.9, 45.0, 44.8, 45.1]

    events = [
        update.event
        for update in (tracker.update(value) for value in samples)
        if update.event
    ]

    assert events == ["ramp_up", "hold"]
