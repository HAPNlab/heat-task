"""All ramp-and-hold task constants."""

from __future__ import annotations

POLL_INTERVAL_S = 0.0
CONNECT_TIMEOUT_S = 5.0
RECV_TIMEOUT_S = 2.0

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

INSTRUCTION_KEYS: dict[str, list[str]] = {
    "forward": ["4"],
    "back": ["3"],
}
START_KEYS = ["0", "num_0"]
RATING_KEYS: dict[str, list[str]] = {
    "left": ["left"],
    "right": ["right"],
    "confirm": ["space", "return", "num_enter"],
}
END_KEYS = ["space", *START_KEYS]
QUIT_KEYS = ["escape", "l"]

WINDOW_COLOR = (-1, -1, -1)
TEXT_COLOR = "white"
INSTRUCTION_PAGES = [
    "Keep your eyes on the crosshair throughout the task.",
    "When the temperature starts ramping up, the word READY will appear.",
    (
        "When the temperature ramps down, rate the pain intensity by moving the trackball "
        "left or right, then click the trackball button or press space to confirm."
    ),
]
