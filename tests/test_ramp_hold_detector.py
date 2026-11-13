"""Tests for the ramp-and-hold phase tracker.

The tracker must report exactly ramp_up → hold → ramp_down → complete once per
sequence, and nothing for the thermode's normal plateau behaviour: reading
jitter, the overshoot that settles back to target early in the hold, and the
undershoot that recovers after the return to baseline.
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path

import pytest

from heat_task.io.conditions import SequenceConfig
from heat_task.task.phase_tracker import Phase, PhaseTracker, PhaseTrackerConfig

FULL_SEQUENCE = [Phase.RAMP_UP, Phase.HOLD, Phase.RAMP_DOWN, Phase.COMPLETE]
FIXTURES = Path(__file__).parent / "fixtures"

Samples = list[tuple[float, float]]


def run(tracker: PhaseTracker, samples: Samples) -> list[tuple[Phase, float]]:
    """Feed (time_s, temperature) samples; return each (event, time_s) fired."""
    events = []
    for time_s, temperature in samples:
        update = tracker.update(temperature, time_s)
        if update.event is not None:
            events.append((update.event, time_s))
    return events


def names(events: list[tuple[Phase, float]]) -> list[Phase]:
    return [event for event, _ in events]


def _bump(t: float, peak_s: float) -> float:
    """0 at t=0, rising to 1 at peak_s, then decaying: an overshoot's shape."""
    x = t / peak_s
    return x * math.exp(1 - x)


@dataclass(frozen=True)
class Thermode:
    """A ramp-and-hold curve shaped like the recorded TSA thermode, read the way
    the status poller reads it (MMS updates its reading every device_period_s;
    the poller reads it every ~poll_period_s, so most reads are repeats)."""

    baseline: float = 35.0
    target: float = 46.0
    lead_s: float = 3.0
    up_rate: float = 3.5  # °C/s
    hold_s: float = 10.0
    down_rate: float = 3.0  # °C/s
    tail_s: float = 6.0
    overshoot: float = 0.25  # °C above the hold level, ~0.7 s into the hold
    undershoot: float = 0.30  # °C below baseline, ~0.7 s after the return
    hold_offset: float = 0.0  # where the hold settles relative to target
    noise: float = 0.03  # σ of reading jitter, °C
    device_period_s: float = 0.06
    poll_period_s: float = 0.021

    @property
    def hold_level(self) -> float:
        return self.target + self.hold_offset

    @property
    def ramp_up_start(self) -> float:
        return self.lead_s

    @property
    def hold_start(self) -> float:
        return self.lead_s + (self.hold_level - self.baseline) / self.up_rate

    @property
    def ramp_down_start(self) -> float:
        return self.hold_start + self.hold_s

    @property
    def baseline_return(self) -> float:
        return self.ramp_down_start + (self.hold_level - self.baseline) / self.down_rate

    @property
    def end(self) -> float:
        return self.baseline_return + self.tail_s

    def temperature(self, t: float) -> float:
        if t < self.ramp_up_start:
            return self.baseline
        if t < self.hold_start:
            return self.baseline + (t - self.ramp_up_start) * self.up_rate
        if t < self.ramp_down_start:
            return self.hold_level + self.overshoot * _bump(t - self.hold_start, 0.7)
        if t < self.baseline_return:
            return self.hold_level - (t - self.ramp_down_start) * self.down_rate
        return self.baseline - self.undershoot * _bump(t - self.baseline_return, 0.7)

    def samples(self, seed: int = 0, start_s: float = 0.0) -> Samples:
        rng = random.Random(seed)
        out: Samples = []
        reading = self.baseline
        next_update = 0.0
        t = 0.0
        while t < self.end:
            if t >= next_update:
                reading = round(self.temperature(t) + rng.gauss(0.0, self.noise), 2)
                next_update += self.device_period_s
            out.append((round(start_s + t, 4), reading))
            t += self.poll_period_s * rng.uniform(0.6, 1.6)
        return out

    def tracker(self) -> PhaseTracker:
        return PhaseTracker(SequenceConfig(baseline=self.baseline, target_temp=self.target))


def _load_recording(name: str) -> Samples:
    with (FIXTURES / name).open() as f:
        return [(float(row["time_s"]), float(row["raw_temperature"])) for row in csv.DictReader(f)]


def test_recorded_overshoot_is_not_a_ramp_down() -> None:
    """A 46 °C sequence recorded from the TSA thermode (35 °C baseline): ramp-up
    at ~20.2 s, a 0.25 °C overshoot that settles back over the first few
    seconds of the hold, ramp-down at ~53.5 s, back at baseline ~57.2 s with a
    0.3 °C undershoot. The old tracker fired ramp_down at 25.7 s and complete at
    27.2 s, both mid-hold."""
    tracker = PhaseTracker(SequenceConfig(baseline=35.0, target_temp=46.0))

    events = run(tracker, _load_recording("recorded_46c_sequence.csv"))

    assert names(events) == FULL_SEQUENCE
    onsets = dict(events)
    assert 20.2 < onsets[Phase.RAMP_UP] < 21.0
    assert 22.8 < onsets[Phase.HOLD] < 23.6
    assert 53.5 < onsets[Phase.RAMP_DOWN] < 54.3
    assert 57.0 < onsets[Phase.COMPLETE] < 57.8


@pytest.mark.parametrize(
    "thermode",
    [
        pytest.param(Thermode(), id="like-recording"),
        pytest.param(Thermode(overshoot=0.5, undershoot=0.5), id="double-overshoot"),
        pytest.param(Thermode(noise=0.08), id="noisy"),
        pytest.param(Thermode(hold_offset=-0.4), id="hold-sags-to-tolerance-edge"),
        pytest.param(Thermode(hold_offset=0.4), id="hold-settles-high"),
        pytest.param(Thermode(up_rate=1.5, down_rate=1.5), id="slow-ramps"),
        pytest.param(Thermode(up_rate=8.0, down_rate=8.0), id="fast-ramps"),
        pytest.param(Thermode(poll_period_s=0.01), id="fast-polling"),
        pytest.param(Thermode(poll_period_s=0.08), id="slow-polling"),
    ],
)
def test_one_clean_sequence_per_ramp_and_hold(thermode: Thermode) -> None:
    for seed in range(10):
        events = run(thermode.tracker(), thermode.samples(seed))

        assert names(events) == FULL_SEQUENCE, f"seed {seed}: {events}"
        onsets = dict(events)
        assert thermode.ramp_up_start < onsets[Phase.RAMP_UP] < thermode.ramp_up_start + 1.0
        assert abs(onsets[Phase.HOLD] - thermode.hold_start) < 0.6
        assert thermode.ramp_down_start < onsets[Phase.RAMP_DOWN] < thermode.ramp_down_start + 1.0
        assert abs(onsets[Phase.COMPLETE] - thermode.baseline_return) < 0.6


def test_poll_gaps_do_not_confuse_the_tracker() -> None:
    """Reconnects leave ~1 s holes in the stream; one mid-hold, one right as the
    ramp-down starts."""
    thermode = Thermode()
    holes = [
        (thermode.hold_start + 2.0, thermode.hold_start + 3.0),
        (thermode.ramp_down_start + 0.05, thermode.ramp_down_start + 1.05),
    ]
    samples = [(t, v) for t, v in thermode.samples() if not any(a <= t < b for a, b in holes)]

    events = run(thermode.tracker(), samples)

    assert names(events) == FULL_SEQUENCE


@pytest.mark.parametrize("bad_readings", [1, 2])
@pytest.mark.parametrize("phase_at", ["baseline", "hold"])
@pytest.mark.parametrize("spike", [-5.0, 5.0])
def test_bad_readings_cannot_trip_a_transition(
    bad_readings: int, phase_at: str, spike: float
) -> None:
    thermode = Thermode()
    at = thermode.ramp_up_start - 1.0 if phase_at == "baseline" else thermode.hold_start + 3.0
    until = at + bad_readings * thermode.device_period_s
    for seed in range(10):
        samples = [
            (t, v + spike if at <= t < until else v)
            for t, v in thermode.samples(seed)
            if t < thermode.ramp_down_start
        ]

        events = run(thermode.tracker(), samples)

        assert names(events) == [Phase.RAMP_UP, Phase.HOLD], f"seed {seed}: {events}"


def test_fast_small_rise_at_baseline_is_not_a_ramp_up() -> None:
    """The thermode sits 0.5 °C under baseline, then snaps up 0.6 °C at 3 °C/s:
    ramp speed, but not a ramp's worth of rise."""
    sequence = SequenceConfig(baseline=35.0, target_temp=46.0)
    low = [(i * 0.02, 34.5) for i in range(50)]  # 0.00 – 0.98 s
    snap = [(1.0 + i * 0.02, round(34.5 + 0.06 * i, 2)) for i in range(1, 11)]
    settled = [(1.2 + i * 0.02, 35.1) for i in range(1, 100)]

    assert run(PhaseTracker(sequence), low + snap + settled) == []


def test_slow_drift_during_hold_is_not_a_ramp_down() -> None:
    """The hold sags a full degree over 10 s (0.1 °C/s), past the ramp-down
    line, before the real ramp-down."""
    thermode = Thermode()

    def temperature(t: float) -> float:
        sag = 0.1 * min(max(t - thermode.hold_start, 0.0), thermode.hold_s)
        if t < thermode.ramp_down_start:
            return thermode.temperature(t) - sag
        return thermode.temperature(t) - sag * max(0.0, 1.0 - (t - thermode.ramp_down_start))

    samples = [(t, round(temperature(t), 2)) for t, _ in thermode.samples()]

    events = run(thermode.tracker(), samples)

    assert names(events) == FULL_SEQUENCE
    assert dict(events)[Phase.RAMP_DOWN] > thermode.ramp_down_start


def test_condition_must_hold_for_the_dwell_time() -> None:
    """A ramp-shaped jump that is gone again within DWELL_S doesn't count; one
    that stays does. Smoothing is turned off to isolate the dwell."""
    cfg = PhaseTrackerConfig(smoothing_s=0.001, dwell_s=0.1)
    sequence = SequenceConfig(baseline=35.0, target_temp=46.0)
    flat = [(i * 0.02, 35.0) for i in range(30)]  # 0.00 – 0.58 s
    jump = [(0.60, 36.0), (0.62, 37.0), (0.64, 38.0), (0.66, 39.0)]
    back = [(0.68 + i * 0.02, 35.0) for i in range(30)]
    stays = [(0.68 + i * 0.02, 39.0 + 0.02 * i) for i in range(30)]

    assert run(PhaseTracker(sequence, cfg), flat + jump + back) == []
    assert names(run(PhaseTracker(sequence, cfg), flat + jump + stays)) == [Phase.RAMP_UP]


def test_wobble_on_the_way_down_does_not_complete_early() -> None:
    """Partway down (~40 °C) the thermode climbs 0.6 °C back up at 2 °C/s,
    holds there for 0.4 s, then carries on down."""
    thermode = Thermode(noise=0.0)
    wobble_at = thermode.ramp_down_start + 2.0
    rise_s, flat_s, rise = 0.3, 0.4, 0.6
    # Back on the descent at the point that was rise °C above wobble_at's.
    rejoin = wobble_at - rise / thermode.down_rate
    delay = wobble_at + rise_s + flat_s - rejoin

    def temperature(t: float) -> float:
        if t < wobble_at:
            return thermode.temperature(t)
        if t < wobble_at + rise_s:
            return thermode.temperature(wobble_at) + rise * (t - wobble_at) / rise_s
        if t < wobble_at + rise_s + flat_s:
            return thermode.temperature(wobble_at) + rise
        return thermode.temperature(t - delay)

    samples = [(t, round(temperature(t), 2)) for t, _ in Thermode(tail_s=8.0).samples()]

    events = run(thermode.tracker(), samples)

    assert names(events) == FULL_SEQUENCE
    assert dict(events)[Phase.COMPLETE] > thermode.baseline_return + delay - 0.3


def test_completes_when_next_ramp_starts_before_baseline_return() -> None:
    """The run file says 30 °C but the thermode only comes back down to 35 °C,
    so the ramp-down never reaches the baseline band; the next ramp-up ends it."""
    first = Thermode(baseline=35.0, tail_s=2.0, undershoot=0.0)
    second = Thermode(baseline=35.0, lead_s=0.0)
    samples = first.samples() + second.samples(seed=1, start_s=first.end)
    tracker = PhaseTracker(SequenceConfig(baseline=30.0, target_temp=46.0))

    events = run(tracker, samples)

    assert names(events) == FULL_SEQUENCE
    assert first.end < dict(events)[Phase.COMPLETE] < first.end + 1.0


def test_ramp_that_turns_back_before_target_still_ramps_down() -> None:
    """MMS stops the ramp at 43 °C on the way to 46 °C and returns to baseline."""
    stopped = Thermode(target=43.0, hold_s=0.0, overshoot=0.0)
    tracker = PhaseTracker(SequenceConfig(baseline=35.0, target_temp=46.0))

    events = run(tracker, stopped.samples())

    assert names(events) == [Phase.RAMP_UP, Phase.RAMP_DOWN, Phase.COMPLETE]


def test_tracker_started_mid_ramp_down_waits_for_the_next_ramp_up() -> None:
    """A sequence can begin while the previous one's thermode is still coming
    down; the fall and the undershoot recovery must not read as its ramp-up."""
    previous = Thermode()
    leftover = [(t, v) for t, v in previous.samples() if t > previous.ramp_down_start + 0.5]
    start = leftover[0][0]
    leftover = [(t - start, v) for t, v in leftover]
    offset = leftover[-1][0] + 0.02
    nxt = Thermode()
    samples = leftover + nxt.samples(seed=1, start_s=offset)

    events = run(nxt.tracker(), samples)

    assert names(events) == FULL_SEQUENCE
    assert dict(events)[Phase.RAMP_UP] > offset + nxt.ramp_up_start


def test_hold_that_never_ends_stays_in_hold() -> None:
    thermode = Thermode(noise=0.06, overshoot=0.5, hold_s=60.0)
    samples = [(t, v) for t, v in thermode.samples() if t < thermode.ramp_down_start]

    events = run(thermode.tracker(), samples)

    assert names(events) == [Phase.RAMP_UP, Phase.HOLD]


def test_ramp_down_line_must_clear_the_hold_band() -> None:
    with pytest.raises(ValueError, match="ramp_down_delta"):
        PhaseTrackerConfig(ramp_down_delta=0.5, target_tolerance=0.5)
