"""Data models for a Medoc experiment parsed from a .ats file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RampAndHoldSequence:
    number: int
    trials: int
    baseline_temp: float        # °C
    destination_temp: float     # °C
    destination_rate: float     # °C/s (Double in .ats)
    return_rate: float          # °C/s (Double in .ats)
    duration_ms: int            # ms
    time_before_ms: int         # ms
    inter_trials_min_ms: int    # ms
    inter_trials_max_ms: int    # ms


@dataclass(frozen=True, slots=True)
class ThermodeProgram:
    name: str
    sequences: tuple[RampAndHoldSequence, ...]


@dataclass(frozen=True, slots=True)
class Experiment:
    programs: tuple[ThermodeProgram, ...]
