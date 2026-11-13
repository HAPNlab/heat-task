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
# When START gets no reply, how long to poll STATUS for the test to be running
# before aborting, and the gap between those polls.
START_CONFIRM_TIMEOUT_S = 3.0
START_CONFIRM_POLL_S = 0.25
# The task sends the pretest START itself (the operator's mouse is locked to the
# task window, so they can't click Pre-test in MMS), then polls STATUS every
# PRETEST_POLL_S. The pretest is done on the first poll where MMS reports the
# test RUNNING with the thermode within BASELINE_TOLERANCE of the run's first
# baseline. Past PRETEST_TIMEOUT_S the task ABORTs and stops.
PRETEST_POLL_S = 0.1
PRETEST_TIMEOUT_S = 20.0
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
# Phase tracker  (see task/phase_tracker.py)
# ─────────────────────────────────────────────────────────────────────────────
# The tracker watches the temperature stream and walks a 5-state machine across
# the ramp-and-hold profile. It never sees the thermode's command schedule — it
# infers each transition purely from the measured curve. The constants below are
# the thresholds for those inferences.
#
#                         overshoot settles back (ignored)
#                          ╭╮
#                          │╰──────────────────────────╮   ← phase: hold
#    T ≥ target − TARGET_TOL ─▶ hold                   │
#                        ╱                             │  T ≤ target − RAMP_DOWN_
#  T(°C)              ╱                                ▼  DELTA, falling fast
#    ▲             ╱  ramp_up                          ╲   ramp_down
#    │          ╱                                        ╲
#    │       ╱                                             ╲
#    │ ─────╱                                               ╲ ╭──────
#    │ baseline                                              ╰╯ complete
#    │   ▲                                           undershoot recovers (ignored)
#    │   │ T ≥ baseline + RAMP_START_DELTA,                 ▲
#    │   │ rising fast                    T ≤ baseline + BASELINE_TOL
#    └───┴───────────────────────────────────────────────────────────────▶ time
#
#   STATE       →  NEXT        FIRES WHEN
#   baseline    →  ramp_up     rising AND T ≥ baseline + RAMP_START_DELTA
#   ramp_up     →  hold        T ≥ target − TARGET_TOLERANCE
#   ramp_up     →  ramp_down   falling AND T ≤ peak − RAMP_DOWN_DELTA
#                                (the ramp turned back before reaching target)
#   hold        →  ramp_down   falling AND T ≤ target − RAMP_DOWN_DELTA
#   ramp_down   →  complete    T ≤ baseline + BASELINE_TOLERANCE
#                                (or rising AND T ≥ lowest + RAMP_START_DELTA:
#                                 the next ramp began before baseline was reached)
#
# "rising" / "falling" = the slope is at least MIN_RAMP_RATE °C/s that way.
#
# A thermode at a plateau overshoots target by ~0.25 °C and settles, undershoots
# baseline by ~0.3 °C and recovers, and jitters by ~±0.05 °C — at well under
# 0.5 °C/s. Real ramps run at the MMS Destination / Return Rate (3–4.5 °C/s).
# So each ramp line sits clear of its plateau band (RAMP_DOWN_DELTA must exceed
# TARGET_TOLERANCE, which the tracker checks) and needs a ramp-speed slope too.
#
# Three knobs condition the raw stream for every transition above. All three are
# in seconds of sample time, so the poll rate and the repeated readings MMS
# returns between its own updates don't change them:
#
#   SMOOTHING_S   T = median of the raw readings in the last SMOOTHING_S (kills
#                 jitter; MMS updates its reading every ~60 ms, so one or two
#                 bad readings in a row can't move the median).
#   TREND_S       slope = change in T over the last TREND_S, in °C/s.
#   DWELL_S       a transition's condition must stay true this long before it
#                 fires (debounce).
#
#                raw ──▶ [ median over SMOOTHING_S ] ──▶ smoothed T
#                                                          │
#                          [ °C/s over TREND_S ] ◀─────────┘
#                                   │
#                  condition true for DWELL_S ──▶ transition

SMOOTHING_S = 0.3  # s of raw readings in the rolling median (~5 MMS updates)
TREND_S = 0.3  # s over which the slope is measured
DWELL_S = 0.1  # s a transition's condition must hold before it fires

BASELINE_TOLERANCE = 0.40  # °C from baseline counted as "at baseline" (the pretest uses it too)
TARGET_TOLERANCE = 0.50  # °C below target counted as "at target"
RAMP_START_DELTA = 0.75  # °C a ramp must climb (from baseline, or the low point) to count
RAMP_DOWN_DELTA = 0.75  # °C below target (or the ramp's peak) that marks ramp-down
MIN_RAMP_RATE = 1.0  # °C/s the slope must reach to count as rising / falling

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
#                           └ marker snaps to 11 integer stops, one tick at each
#   all centred at y = SLIDER_Y

# Slider geometry (height units; window height = 1.0)
SLIDER_HALF_W = 0.4  # half the track width (track spans ±SLIDER_HALF_W)
SLIDER_TRACK_H = 0.006  # track line thickness
SLIDER_TICK_W = 0.003  # tick thickness (one tick per integer rating)
SLIDER_TICK_H = 0.03  # tick height
SLIDER_MARKER_H = 0.10  # marker (handle) height
SLIDER_Y = 0.0  # vertical centre of the whole slider
# Track and tick colour (PsychoPy rgb, -1..1): an opaque mid-gray, so ticks
# don't stack brighter where they cross the track the way translucent white did.
SLIDER_SCALE_COLOR = (0.0, 0.0, 0.0)

# Max time the participant has to enter a rating before the sequence moves on.
RATING_TIMEOUT_S = 15.0

# Pain rating scale: 11 discrete integer positions the marker snaps to.
RATING_MIN = 0
RATING_MAX = 10
# Trackball movement (height units) that counts as the participant interacting
# with the scale; large enough to ignore a stray nudge of the ball.
SLIDER_INTERACT_EPS = 0.004
# Slider travel per unit of trackball motion. The cursor is locked to the task
# window and the slider reads raw motion (see task/pointer.py), which on Windows
# skips the OS pointer-speed setting — tune this on the stimulus PC so one
# comfortable roll crosses the scale.
SLIDER_GAIN = 1.0


INSTRUCTION_KEYS: dict[str, list[str]] = {
    "forward": ["1", "num_1"],
    "back": [],
}
# Pretest gets its own key, apart from the start key, so one key (or a double
# press) can't fire both the pretest and the run START.
PRETEST_KEYS = ["p"]
START_KEYS = ["0", "num_0"]
END_KEYS = ["0", "num_0"]
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
