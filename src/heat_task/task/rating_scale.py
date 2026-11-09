"""Pain-scale geometry: mapping between integer ratings and slider x positions.

Kept free of PsychoPy so it can be tested on the headless CI job.
"""

from __future__ import annotations

from heat_task import config


def rating_to_x(value: int) -> float:
    """Return the slider x of an integer rating (where its tick and marker sit)."""
    span = config.RATING_MAX - config.RATING_MIN
    return -config.SLIDER_HALF_W + (value - config.RATING_MIN) / span * (
        2 * config.SLIDER_HALF_W
    )


def move_along_track(x: float, dx: float) -> float:
    """Move a slider position by *dx*, stopping at the ends of the track.

    Clamping as we go (rather than only when snapping) means pushing past an
    end and then reversing moves the marker straight away, with no dead zone.
    """
    return max(-config.SLIDER_HALF_W, min(config.SLIDER_HALF_W, x + dx))


def snap_rating(raw_x: float) -> tuple[int, float]:
    """Snap a slider x to an integer rating (0..10) and its marker x."""
    clamped = max(-config.SLIDER_HALF_W, min(config.SLIDER_HALF_W, raw_x))
    frac = (clamped + config.SLIDER_HALF_W) / (2 * config.SLIDER_HALF_W)
    span = config.RATING_MAX - config.RATING_MIN
    value = config.RATING_MIN + round(frac * span)
    return value, rating_to_x(value)
