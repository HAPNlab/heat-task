"""Data models for a Medoc experiment parsed from a .ats file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RampAndHoldSequence:
    number: int
    trials: int
    baseline_temp: float        # °C
    destination_temp: float     # °C
    destination_rate: float     # °C/s
    return_rate: float          # °C/s
    duration_ms: int            # ms
    time_before_ms: int         # ms — hold at baseline before first trial of this sequence
    waiting_time_for_response_ms: int   # ms — patient response window after each trial (within ISI)
    inter_trials_min_ms: int    # ms
    inter_trials_max_ms: int    # ms
    inter_trials_time_option: int   # 0 = Onset-to-Onset, 1 = End-to-Onset
    destination_criterion: int  # 0 = Temperature, 1 = Time
    trigger: int                # 0 = Auto, 1 = TTL (wait for external signal before each trial)
    randomize_with_next: bool
    # Whether the device should emit a time mark (TTL pulse) at each trial milestone
    mark_onset: bool
    mark_destination: bool
    mark_end_of_duration: bool
    mark_end_of_trial: bool


@dataclass(frozen=True, slots=True)
class ThermodeProgram:
    name: str
    sequences: tuple[RampAndHoldSequence, ...]
    randomize_sequences: bool
    delay_before_ms: int        # ms — hold at baseline before the program starts


@dataclass(frozen=True, slots=True)
class Experiment:
    programs: tuple[ThermodeProgram, ...]
