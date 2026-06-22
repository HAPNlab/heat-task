"""All ramp-and-hold task constants."""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Network / MMS polling
# ─────────────────────────────────────────────────────────────────────────────
# We talk to the MMS thermode over a socket: one short-lived request/response per
# command, plus one long-lived socket that polls temperature status in a loop.
#
#   POLL_INTERVAL_S   gap between status polls
#   CONNECT_TIMEOUT_S how long to wait for the initial connection
#   RECV_TIMEOUT_S    reply deadline for one-off commands
#   POLL_RECV_TIMEOUT_S reply deadline for the status poller's socket

# Min gap between status polls (~100 Hz). Caps load on MMS — hammering it at the
# raw link rate provokes dropped/late responses and floods the trace with
# near-duplicate rows — while staying well above the thermode's update rate.
POLL_INTERVAL_S = 0.01
CONNECT_TIMEOUT_S = 5.0
RECV_TIMEOUT_S = 2.0
# Shorter receive timeout for the status poller's long-lived socket. A status
# query returns in milliseconds on a healthy link, so a stall past this bounds
# the freeze before we drop and reconnect to resynchronise the stream.
POLL_RECV_TIMEOUT_S = 0.5
# Backoff between failed reconnect attempts in the status poller. The common case
# is a single dropped poll that reconnects instantly, so we start small to keep
# that freeze short (a flat 1 s sleep here was the source of the rare ~1 s lag
# spikes); repeated failures back off exponentially up to the cap so a truly down
# MMS doesn't get hammered.
RECONNECT_BACKOFF_S = 0.05
RECONNECT_BACKOFF_MAX_S = 1.0

# ─────────────────────────────────────────────────────────────────────────────
# Phase detector  (see detector.py)
# ─────────────────────────────────────────────────────────────────────────────
# The detector watches the temperature stream and walks a 5-state machine across
# the ramp-and-hold profile. It never sees the thermode's command schedule — it
# infers each transition purely from the measured curve. The constants below are
# the thresholds for those inferences.
#
#                                   target_temp
#                          ┌──────────────────────────┐   ← phase: hold
#         near_target:     │                          │
#    |T-target|≤TARGET_TOL │                          │  fall TARGET_TOL/2 below
#                        ╱ │                          │ │ target, OR RAMP_DOWN_
#  T(°C)              ╱    │                          │ ▼ DELTA below the peak,
#    ▲             ╱       │                          │   while trending down
#    │          ╱  ramp_up │                          │ ╲  ramp_down
#    │       ╱             │                          │    ╲
#    │ ─────╱              │                          │      ╲──────────
#    │ baseline                                                complete
#    │   ▲                                                       ▲
#    │   │ rise ≥ RAMP_START_DELTA above baseline,               │ back within
#    │   │ while trending up                          |T-baseline|≤BASELINE_TOL
#    └───┴───────────────────────────────────────────────────────────────▶ time
#
#   STATE       →  NEXT        FIRES WHEN
#   baseline    →  ramp_up     upward trend AND T ≥ baseline + RAMP_START_DELTA
#   ramp_up     →  hold        T within TARGET_TOLERANCE of target_temp
#   hold        →  ramp_down   downward trend AND (T ≤ target − TARGET_TOL/2
#                                OR T ≤ peak − RAMP_DOWN_DELTA)
#   ramp_down   →  complete    T within BASELINE_TOLERANCE of baseline
#                                (or a fresh upward ramp begins → next trial)
#
# Three knobs shape *every* transition above by conditioning the raw stream:
#
#   SMOOTHING_WINDOW   T = mean of the last N raw samples (kills sensor jitter).
#   TREND_WINDOW       slope = mean of the last N sample-to-sample changes in T.
#                      "trending up/down" = |slope| ≥ MIN_SLOPE_PER_SAMPLE.
#   CONSECUTIVE_SAMPLES a transition's condition must hold this many polls in a
#                      row before it fires (debounce — one stray sample can't
#                      trip a state change).
#
#                raw ──▶ [ avg of SMOOTHING_WINDOW ] ──▶ smoothed T
#                                                          │
#                         [ avg slope over TREND_WINDOW ] ◀┘
#                                   │
#                  condition true for CONSECUTIVE_SAMPLES polls ──▶ transition

SMOOTHING_WINDOW = 5  # samples averaged for the smoothed temperature
TREND_WINDOW = 4  # samples averaged for the slope / trend direction
CONSECUTIVE_SAMPLES = 3  # debounce: polls a condition must hold before firing

BASELINE_TOLERANCE = 0.40  # °C window around baseline counted as "at baseline"
TARGET_TOLERANCE = 0.50  # °C window around target counted as "at target"
RAMP_START_DELTA = 0.30  # °C rise above baseline that marks ramp-up onset
RAMP_DOWN_DELTA = 0.35  # °C fall below peak that marks ramp-down onset
MIN_SLOPE_PER_SAMPLE = 0.03  # °C/sample slope needed to count as trending

# ── Primed overrides ─────────────────────────────────────────────────────────
# When we *know* a transition is imminent (within PRIME_WINDOW_S of the scheduled
# event), the detector swaps to these tighter, twitchier values so it reacts to
# the real change fast instead of waiting out the conservative debounce. Same
# meanings as above — just smaller windows and thresholds for higher sensitivity.
PRIME_WINDOW_S = 3.0  # how far ahead of a scheduled event the prime kicks in

PRIMED_SMOOTHING_WINDOW = 2
PRIMED_TREND_WINDOW = 2
PRIMED_CONSECUTIVE_SAMPLES = 1
PRIMED_RAMP_START_DELTA = 0.15
PRIMED_RAMP_DOWN_DELTA = 0.20
PRIMED_MIN_SLOPE_PER_SAMPLE = 0.02

# ─────────────────────────────────────────────────────────────────────────────
# Pain-rating slider
# ─────────────────────────────────────────────────────────────────────────────
# Horizontal trackball slider, drawn in PsychoPy "height" units (window height =
# 1.0, so width spans ±aspect/2 and these values are fractions of the height).
#
#        SLIDER_HALF_W                 SLIDER_HALF_W
#   ◀──────────────────────┬──────────────────────▶
#   ┌──┐                 ┌──┐                    ┌──┐   ▲
#   │  │  ───────────────│▓▓│──────────────────  │  │   │ SLIDER_MARKER_H
#   └──┘                 └──┘                    └──┘   ▼ (marker height)
#    0          track ────┘ ▲                     10
#  RATING_MIN  (SLIDER_TRACK_H thick)          RATING_MAX
#                           └ marker snaps to 11 integer stops
#   all centred at y = SLIDER_Y

# Slider geometry (height units; window height = 1.0)
SLIDER_HALF_W = 0.4  # half the track width (track spans ±SLIDER_HALF_W)
SLIDER_TRACK_H = 0.006  # track line thickness
SLIDER_MARKER_H = 0.10  # marker (handle) height
SLIDER_Y = 0.0  # vertical centre of the whole slider

# Max time the participant has to enter a rating before the trial moves on.
RATING_TIMEOUT_S = 15.0

# Pain rating scale: 11 discrete integer positions the marker snaps to.
RATING_MIN = 0
RATING_MAX = 10
# Cursor movement (height units) that counts as the participant interacting with
# the scale; large enough to ignore setPos/getPos jitter.
SLIDER_INTERACT_EPS = 0.004

SAVE_NET_EVENTS = False  # set True to write net_events_*.csv for network diagnostics

INSTRUCTION_KEYS: dict[str, list[str]] = {
    "forward": ["1", "num_1"],
    "back": [],
}
START_KEYS = ["0", "num_0"]
END_KEYS = ["space", *START_KEYS]
QUIT_KEYS = ["escape"]

WINDOW_COLOR = (-1, -1, -1)
TEXT_COLOR = "white"
INSTRUCTION_PAGES = [
    "Keep your eyes on the crosshair throughout the task.",
    "When the temperature starts ramping up, the word READY will appear.",
    (
        "When the temperature ramps down, rate the pain intensity by moving the trackball "
        "left or right along the 0 (No Pain) to 10 (Worst Pain) scale. "
        "Your last position is recorded automatically."
    ),
]
