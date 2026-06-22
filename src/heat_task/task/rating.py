"""The pain-rating slider: a small controller that owns the slider's per-trial
state so the trial loop only has to begin it, tick it, and draw it."""

from __future__ import annotations

from psychopy.hardware import keyboard
from psyexp_core.keyboard import clear_events

from heat_task import config
from heat_task.task import display
from heat_task.task.display import Stimuli


def snap_rating(raw_x: float) -> tuple[int, float]:
    """Snap a raw mouse x to an integer rating (0..10) and its marker x."""
    clamped = max(-config.SLIDER_HALF_W, min(config.SLIDER_HALF_W, raw_x))
    frac = (clamped + config.SLIDER_HALF_W) / (2 * config.SLIDER_HALF_W)
    span = config.RATING_MAX - config.RATING_MIN
    value = config.RATING_MIN + round(frac * span)
    marker_x = -config.SLIDER_HALF_W + (value - config.RATING_MIN) / span * (
        2 * config.SLIDER_HALF_W
    )
    return value, marker_x


class RatingController:
    """Drives the rating slider for one trial.

    ``begin`` arms the slider when ramp-down starts; ``update`` is called each
    frame and returns True on the frame the rating is finalised (after the
    timeout); ``draw`` renders the current marker. The final ``rating`` and
    ``no_response`` flag are read off the controller once ``complete`` is set.
    """

    def __init__(self, stimuli: Stimuli) -> None:
        self._stimuli = stimuli
        self.active = False
        self.complete = False
        self.rating: float = config.RATING_MIN
        self.no_response = 0
        self.marker_x = -config.SLIDER_HALF_W
        self._started_at_s = 0.0
        self._interacted = False
        self._start_x = 0.0

    def begin(self, started_at_s: float, kb: keyboard.Keyboard | None) -> None:
        self.active = True
        self._started_at_s = started_at_s
        self._interacted = False
        self.marker_x = -config.SLIDER_HALF_W
        self._stimuli.mouse.setPos([-config.SLIDER_HALF_W, 0])
        self._start_x = self._stimuli.mouse.getPos()[0]
        clear_events(kb)

    def update(self, now_s: float) -> bool:
        """Advance the slider; return True only on the frame it finalises."""
        if not self.active:
            return False
        raw_x = self._stimuli.mouse.getPos()[0]
        if abs(raw_x - self._start_x) > config.SLIDER_INTERACT_EPS:
            self._interacted = True
        selected_rating, self.marker_x = snap_rating(raw_x)

        if now_s - self._started_at_s >= config.RATING_TIMEOUT_S:
            self.rating = selected_rating
            self.no_response = 0 if self._interacted else 1
            self.active = False
            self.complete = True
            return True
        return False

    def draw(self) -> None:
        display.draw_rating(self._stimuli, self.marker_x)
