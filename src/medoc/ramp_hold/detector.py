"""Temperature-only phase detector for the ramp-and-hold task."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from medoc.ramp_hold import config
from medoc.ramp_hold.conditions import TrialConfig


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    smoothing_window: int = config.SMOOTHING_WINDOW
    trend_window: int = config.TREND_WINDOW
    consecutive_samples: int = config.CONSECUTIVE_SAMPLES
    baseline_tolerance: float = config.BASELINE_TOLERANCE
    target_tolerance: float = config.TARGET_TOLERANCE
    ramp_start_delta: float = config.RAMP_START_DELTA
    ramp_down_delta: float = config.RAMP_DOWN_DELTA
    min_slope_per_sample: float = config.MIN_SLOPE_PER_SAMPLE

    @classmethod
    def primed(cls) -> DetectorConfig:
        return cls(
            smoothing_window=config.PRIMED_SMOOTHING_WINDOW,
            trend_window=config.PRIMED_TREND_WINDOW,
            consecutive_samples=config.PRIMED_CONSECUTIVE_SAMPLES,
            ramp_start_delta=config.PRIMED_RAMP_START_DELTA,
            ramp_down_delta=config.PRIMED_RAMP_DOWN_DELTA,
            min_slope_per_sample=config.PRIMED_MIN_SLOPE_PER_SAMPLE,
        )


@dataclass(frozen=True, slots=True)
class DetectorUpdate:
    raw_temperature: float
    smoothed_temperature: float
    phase: str
    transitioned: bool
    event: str | None


@dataclass(slots=True)
class RampHoldDetector:
    trial: TrialConfig
    config: DetectorConfig = field(default_factory=DetectorConfig)
    phase: str = field(init=False, default="baseline")
    _window: deque[float] = field(init=False)
    _slopes: deque[float] = field(init=False)
    _gates: dict[str, int] = field(init=False, default_factory=dict)
    _last_smoothed: float | None = field(init=False, default=None)
    _peak_temperature: float = field(init=False)

    def __post_init__(self) -> None:
        self._window = deque(maxlen=self.config.smoothing_window)
        self._slopes = deque(maxlen=self.config.trend_window)
        self._peak_temperature = self.trial.baseline

    def prime(self, primed_config: DetectorConfig) -> None:
        """Switch to tighter detection params ahead of an expected transition."""
        self._window = deque(self._window, maxlen=primed_config.smoothing_window)
        self._slopes = deque(self._slopes, maxlen=primed_config.trend_window)
        self.config = primed_config
        self._gates.clear()

    def update(self, raw_temperature: float) -> DetectorUpdate:
        self._window.append(raw_temperature)
        smoothed = sum(self._window) / len(self._window)

        if self._last_smoothed is not None:
            self._slopes.append(smoothed - self._last_smoothed)
        self._last_smoothed = smoothed

        transitioned = False
        event: str | None = None

        if self.phase == "baseline":
            condition = self._upward_trend() and smoothed >= (
                self.trial.baseline + self.config.ramp_start_delta
            )
            if self._advance_gate("ramp_up", condition):
                self.phase = "ramp_up"
                transitioned = True
                event = "ramp_up"
        elif self.phase == "ramp_up":
            self._peak_temperature = max(self._peak_temperature, smoothed)
            if self._advance_gate("hold", self._near_target(smoothed)):
                self.phase = "hold"
                transitioned = True
                event = "hold"
        elif self.phase == "hold":
            self._peak_temperature = max(self._peak_temperature, smoothed)
            condition = self._downward_trend() and (
                smoothed <= self.trial.target_temp - (self.config.target_tolerance / 2.0)
                or smoothed <= self._peak_temperature - self.config.ramp_down_delta
            )
            if self._advance_gate("ramp_down", condition):
                self.phase = "ramp_down"
                transitioned = True
                event = "ramp_down"
        elif self.phase == "ramp_down":
            # Transition to complete when temperature returns to near baseline OR when a new
            # upward ramp is detected (next trial starting before full baseline return).
            near_baseline = self._near_baseline(smoothed)
            new_ramp_starting = self._upward_trend() and smoothed >= (
                self.trial.baseline + self.config.ramp_start_delta
            )
            if self._advance_gate("complete", near_baseline or new_ramp_starting):
                self.phase = "complete"
                transitioned = True
                event = "complete"

        return DetectorUpdate(
            raw_temperature=raw_temperature,
            smoothed_temperature=smoothed,
            phase=self.phase,
            transitioned=transitioned,
            event=event,
        )

    def _near_baseline(self, temperature: float) -> bool:
        return abs(temperature - self.trial.baseline) <= self.config.baseline_tolerance

    def _near_target(self, temperature: float) -> bool:
        return abs(temperature - self.trial.target_temp) <= self.config.target_tolerance

    def _upward_trend(self) -> bool:
        if not self._slopes:
            return False
        return (sum(self._slopes) / len(self._slopes)) >= self.config.min_slope_per_sample

    def _downward_trend(self) -> bool:
        if not self._slopes:
            return False
        return (sum(self._slopes) / len(self._slopes)) <= -self.config.min_slope_per_sample

    def _advance_gate(self, name: str, condition: bool) -> bool:
        if condition:
            self._gates[name] = self._gates.get(name, 0) + 1
        else:
            self._gates[name] = 0
        return self._gates[name] >= self.config.consecutive_samples
