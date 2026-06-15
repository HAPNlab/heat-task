"""All ramp-and-hold task constants."""

from __future__ import annotations

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

SMOOTHING_WINDOW = 5
TREND_WINDOW = 4
CONSECUTIVE_SAMPLES = 3
BASELINE_TOLERANCE = 0.40
TARGET_TOLERANCE = 0.50
RAMP_START_DELTA = 0.30
RAMP_DOWN_DELTA = 0.35
MIN_SLOPE_PER_SAMPLE = 0.03

RATING_TIMEOUT_S = 15.0

PRIME_WINDOW_S = 3.0

PRIMED_SMOOTHING_WINDOW = 2
PRIMED_TREND_WINDOW = 2
PRIMED_CONSECUTIVE_SAMPLES = 1
PRIMED_RAMP_START_DELTA = 0.15
PRIMED_RAMP_DOWN_DELTA = 0.20
PRIMED_MIN_SLOPE_PER_SAMPLE = 0.02

# Slider geometry (height units; window height = 1.0)
SLIDER_HALF_W = 0.4
SLIDER_TRACK_H = 0.006
SLIDER_MARKER_H = 0.10
SLIDER_Y = 0.0

# Pain rating scale: 10 discrete integer positions the marker snaps to.
RATING_MIN = 1
RATING_MAX = 10
# Cursor movement (height units) that counts as the participant interacting with
# the scale; large enough to ignore setPos/getPos jitter.
SLIDER_INTERACT_EPS = 0.004

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
        "left or right along the 1 (No Pain) to 10 (Worst Pain) scale. "
        "Your last position is recorded automatically."
    ),
]
