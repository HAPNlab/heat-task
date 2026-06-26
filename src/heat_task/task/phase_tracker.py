"""Infers the current ramp-and-hold phase from the temperature stream alone.

The tracker never sees the thermode's command schedule; it walks a five-state
machine (baseline → ramp_up → hold → ramp_down → complete) purely from the
measured curve. See config.py for the thresholds and the state diagram.
"""

from __future__ import annotations

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
    smoothing_window: int = config.SMOOTHING_WINDOW
    trend_window: int = config.TREND_WINDOW
    consecutive_samples: int = config.CONSECUTIVE_SAMPLES
    baseline_tolerance: float = config.BASELINE_TOLERANCE
    target_tolerance: float = config.TARGET_TOLERANCE
    ramp_start_delta: float = config.RAMP_START_DELTA
    ramp_down_delta: float = config.RAMP_DOWN_DELTA
    min_slope_per_sample: float = config.MIN_SLOPE_PER_SAMPLE

    @classmethod
    def primed(cls) -> PhaseTrackerConfig:
        return cls(
            smoothing_window=config.PRIMED_SMOOTHING_WINDOW,
            trend_window=config.PRIMED_TREND_WINDOW,
            consecutive_samples=config.PRIMED_CONSECUTIVE_SAMPLES,
            ramp_start_delta=config.PRIMED_RAMP_START_DELTA,
            ramp_down_delta=config.PRIMED_RAMP_DOWN_DELTA,
            min_slope_per_sample=config.PRIMED_MIN_SLOPE_PER_SAMPLE,
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
    _window: deque[float] = field(init=False)
    _slopes: deque[float] = field(init=False)
    _gates: dict[Phase, int] = field(init=False, default_factory=dict)
    _last_smoothed: float | None = field(init=False, default=None)
    _peak_temperature: float = field(init=False)

    def __post_init__(self) -> None:
        self._window = deque(maxlen=self.config.smoothing_window)
        self._slopes = deque(maxlen=self.config.trend_window)
        self._peak_temperature = self.sequence.baseline

    def prime(self, primed_config: PhaseTrackerConfig) -> None:
        """Switch to tighter detection params ahead of an expected transition."""
        self._window = deque(self._window, maxlen=primed_config.smoothing_window)
        self._slopes = deque(self._slopes, maxlen=primed_config.trend_window)
        self.config = primed_config
        self._gates.clear()

    def update(self, raw_temperature: float) -> PhaseUpdate:
        self._window.append(raw_temperature)
        smoothed = sum(self._window) / len(self._window)

        if self._last_smoothed is not None:
            self._slopes.append(smoothed - self._last_smoothed)
        self._last_smoothed = smoothed

        transitioned = False
        event: Phase | None = None

        if self.phase == Phase.BASELINE:
            condition = self._upward_trend() and smoothed >= (
                self.sequence.baseline + self.config.ramp_start_delta
            )
            if self._advance_gate(Phase.RAMP_UP, condition):
                self.phase = Phase.RAMP_UP
                transitioned = True
                event = Phase.RAMP_UP
        elif self.phase == Phase.RAMP_UP:
            self._peak_temperature = max(self._peak_temperature, smoothed)
            if self._advance_gate(Phase.HOLD, self._near_target(smoothed)):
                self.phase = Phase.HOLD
                transitioned = True
                event = Phase.HOLD
        elif self.phase == Phase.HOLD:
            self._peak_temperature = max(self._peak_temperature, smoothed)
            condition = self._downward_trend() and (
                smoothed <= self.sequence.target_temp - (self.config.target_tolerance / 2.0)
                or smoothed <= self._peak_temperature - self.config.ramp_down_delta
            )
            if self._advance_gate(Phase.RAMP_DOWN, condition):
                self.phase = Phase.RAMP_DOWN
                transitioned = True
                event = Phase.RAMP_DOWN
        elif self.phase == Phase.RAMP_DOWN:
            # Transition to complete when temperature returns to near baseline OR when a new
            # upward ramp is detected (next sequence starting before full baseline return).
            near_baseline = self._near_baseline(smoothed)
            new_ramp_starting = self._upward_trend() and smoothed >= (
                self.sequence.baseline + self.config.ramp_start_delta
            )
            if self._advance_gate(Phase.COMPLETE, near_baseline or new_ramp_starting):
                self.phase = Phase.COMPLETE
                transitioned = True
                event = Phase.COMPLETE

        return PhaseUpdate(
            raw_temperature=raw_temperature,
            smoothed_temperature=smoothed,
            phase=self.phase,
            transitioned=transitioned,
            event=event,
        )

    def _near_baseline(self, temperature: float) -> bool:
        return abs(temperature - self.sequence.baseline) <= self.config.baseline_tolerance

    def _near_target(self, temperature: float) -> bool:
        return abs(temperature - self.sequence.target_temp) <= self.config.target_tolerance

    def _upward_trend(self) -> bool:
        if not self._slopes:
            return False
        return (sum(self._slopes) / len(self._slopes)) >= self.config.min_slope_per_sample

    def _downward_trend(self) -> bool:
        if not self._slopes:
            return False
        return (sum(self._slopes) / len(self._slopes)) <= -self.config.min_slope_per_sample

    def _advance_gate(self, name: Phase, condition: bool) -> bool:
        if condition:
            self._gates[name] = self._gates.get(name, 0) + 1
        else:
            self._gates[name] = 0
        return self._gates[name] >= self.config.consecutive_samples
