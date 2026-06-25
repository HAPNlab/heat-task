"""Resolve a frame rate to record from the screen's VSYNC calibration."""

from __future__ import annotations

# Frame rate is informational here (manifest + logging): sequence timing is driven by
# the Medoc temperature stream, not by counting frames. The VSYNC calibration can
# occasionally report an implausibly high rate, so we fall back to a safe default
# rather than record a bogus value. Genuine >200 Hz displays exist, but telling
# them apart from a bad measurement isn't worth it for a value we only log.
FALLBACK_FRAME_RATE_HZ = 60.0
MAX_PLAUSIBLE_FRAME_RATE_HZ = 200.0


def resolve_frame_rate(calib_median_ms: float) -> float:
    if not calib_median_ms:
        return FALLBACK_FRAME_RATE_HZ
    rate = 1000.0 / calib_median_ms
    if rate >= MAX_PLAUSIBLE_FRAME_RATE_HZ:
        return FALLBACK_FRAME_RATE_HZ
    return rate
