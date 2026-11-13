"""Infers the current ramp-and-hold phase from the temperature stream alone.

The tracker never sees the thermode's command schedule; it walks a five-state
machine (baseline → ramp_up → hold → ramp_down → complete) purely from the
measured curve. See config.py for the thresholds and the state diagram.

A thermode at a plateau isn't flat: the reading jitters, it overshoots the
target and settles back, and it undershoots baseline and recovers. None of that
may read as a ramp. Every ramp transition therefore needs all three of:

* Level: the smoothed temperature is well clear of the plateau it left, beyond
  any overshoot, undershoot or jitter the thermode shows while holding.
* Rate: it is moving the ramp's way at MIN_RAMP_RATE °C/s or faster, measured
  over TREND_S of sample time (so the poll rate and repeated device readings
  don't change it).
* Dwell: both stay true for DWELL_S before the phase changes.

Smoothing is a rolling median, so one or two bad readings can't move it.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from heat_task import config
from heat_task.io.conditions import SequenceConfig


class Phase(StrEnum):
    """The five ramp-and-hold states, in the order the tracker walks them.

    A StrEnum so each member compares equal to and serialises as its plain name
    (e.g. ``"baseline"``) — keeping the CSV trace and any string consumers
    unchanged while giving callers a typed, autocomplete-able vocabulary.
    """

    BASELINE = "baseline"
    RAMP_UP = "ramp_up"
    HOLD = "hold"
    RAMP_DOWN = "ramp_down"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class PhaseTrackerConfig:
    smoothing_s: float = config.SMOOTHING_S
    trend_s: float = config.TREND_S
    dwell_s: float = config.DWELL_S
    baseline_tolerance: float = config.BASELINE_TOLERANCE
    target_tolerance: float = config.TARGET_TOLERANCE
    ramp_start_delta: float = config.RAMP_START_DELTA
    ramp_down_delta: float = config.RAMP_DOWN_DELTA
    min_ramp_rate: float = config.MIN_RAMP_RATE

    def __post_init__(self) -> None:
        # Hold starts at target - target_tolerance, so a ramp-down line at or
        # above that would sit inside the hold band and fire on a settled hold.
        if self.ramp_down_delta <= self.target_tolerance:
            raise ValueError(
                f"ramp_down_delta ({self.ramp_down_delta}) must exceed "
                f"target_tolerance ({self.target_tolerance})"
            )


@dataclass(frozen=True, slots=True)
class PhaseUpdate:
    raw_temperature: float
    smoothed_temperature: float
    phase: Phase
    transitioned: bool
    event: Phase | None


@dataclass(slots=True)
class PhaseTracker:
    sequence: SequenceConfig
    config: PhaseTrackerConfig = field(default_factory=PhaseTrackerConfig)
    phase: Phase = field(init=False, default=Phase.BASELINE)
    # (time_s, raw) inside the smoothing window.
    _raw: deque[tuple[float, float]] = field(init=False, default_factory=deque)
    # (time_s, smoothed): the newest point at least trend_s old, then everything newer.
    _history: deque[tuple[float, float]] = field(init=False, default_factory=deque)
    # The transition whose condition currently holds, and when it started holding.
    _pending: tuple[Phase, float] | None = field(init=False, default=None)
    # Highest smoothed temperature in ramp_up; lowest in ramp_down.
    _extreme: float = field(init=False, default=0.0)

    def update(self, raw_temperature: float, time_s: float) -> PhaseUpdate:
        smoothed = self._smooth(raw_temperature, time_s)
        slope = self._slope(smoothed, time_s)

        if self.phase == Phase.RAMP_UP:
            self._extreme = max(self._extreme, smoothed)
        elif self.phase == Phase.RAMP_DOWN:
            self._extreme = min(self._extreme, smoothed)

        event = self._debounce(self._candidate(smoothed, slope), time_s)
        if event is not None:
            self.phase = event
            self._extreme = smoothed

        return PhaseUpdate(
            raw_temperature=raw_temperature,
            smoothed_temperature=smoothed,
            phase=self.phase,
            transitioned=event is not None,
            event=event,
        )

    def _candidate(self, smoothed: float, slope: float | None) -> Phase | None:
        """The phase the current sample argues for, before the dwell check."""
        cfg = self.config
        baseline = self.sequence.baseline
        target = self.sequence.target_temp
        rising = slope is not None and slope >= cfg.min_ramp_rate
        falling = slope is not None and slope <= -cfg.min_ramp_rate

        if self.phase == Phase.BASELINE:
            if rising and smoothed >= baseline + cfg.ramp_start_delta:
                return Phase.RAMP_UP
        elif self.phase == Phase.RAMP_UP:
            if smoothed >= target - cfg.target_tolerance:
                return Phase.HOLD
            # The ramp turned back before reaching target (e.g. MMS stopped
            # it): go straight to ramp_down so the trial still gets its rating.
            if falling and smoothed <= self._extreme - cfg.ramp_down_delta:
                return Phase.RAMP_DOWN
        elif self.phase == Phase.HOLD:
            # Measured from target, not the peak, so overshoot settling back
            # down to target never counts as a fall.
            if falling and smoothed <= target - cfg.ramp_down_delta:
                return Phase.RAMP_DOWN
        elif self.phase == Phase.RAMP_DOWN:
            if smoothed <= baseline + cfg.baseline_tolerance:
                return Phase.COMPLETE
            # The thermode bottomed out above the baseline band and the next
            # ramp has begun. Measured from the lowest point reached, so a wobble
            # partway down can't pass for it.
            if rising and smoothed >= self._extreme + cfg.ramp_start_delta:
                return Phase.COMPLETE
        return None

    def _debounce(self, candidate: Phase | None, time_s: float) -> Phase | None:
        """Return *candidate* once it has held for dwell_s, else None."""
        if candidate is None:
            self._pending = None
            return None
        if self._pending is None or self._pending[0] != candidate:
            self._pending = (candidate, time_s)
        if time_s - self._pending[1] >= self.config.dwell_s:
            self._pending = None
            return candidate
        return None

    def _smooth(self, raw_temperature: float, time_s: float) -> float:
        """Median of the raw readings in the last smoothing_s."""
        self._raw.append((time_s, raw_temperature))
        while self._raw[0][0] <= time_s - self.config.smoothing_s:
            self._raw.popleft()
        return statistics.median(value for _, value in self._raw)

    def _slope(self, smoothed: float, time_s: float) -> float | None:
        """°C/s from the smoothed value trend_s ago to now; None until there's
        that much history."""
        history = self._history
        history.append((time_s, smoothed))
        cutoff = time_s - self.config.trend_s
        while len(history) > 1 and history[1][0] <= cutoff:
            history.popleft()
        ref_time, ref_value = history[0]
        if ref_time > cutoff:
            return None
        return (smoothed - ref_value) / (time_s - ref_time)
