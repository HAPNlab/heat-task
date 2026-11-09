"""The pain-rating slider: a small controller that owns the slider's per-sequence
state so the sequence loop only has to begin it, tick it, and draw it."""

from __future__ import annotations

from psychopy.hardware import keyboard
from psyexp_core.keyboard import clear_events

from heat_task import config
from heat_task.task import display
from heat_task.task.display import Stimuli
from heat_task.task.rating_scale import move_along_track, snap_rating


class RatingController:
    """Drives the rating slider for one sequence.

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
        self._x = -config.SLIDER_HALF_W
        # Net movement since begin(), unclamped, so pushing against the "No Pain"
        # end still counts as interacting even though the marker can't move.
        self._travel = 0.0

    def begin(self, started_at_s: float, kb: keyboard.Keyboard | None) -> None:
        self.active = True
        self._started_at_s = started_at_s
        self._interacted = False
        self.marker_x = -config.SLIDER_HALF_W
        self._x = -config.SLIDER_HALF_W
        self._travel = 0.0
        # Drop movement made before the slider appeared.
        self._stimuli.pointer.take_dx()
        clear_events(kb)

    def update(self, now_s: float) -> bool:
        """Advance the slider; return True only on the frame it finalises."""
        if not self.active:
            return False
        dx = self._stimuli.pointer.take_dx() * config.SLIDER_GAIN
        self._travel += dx
        if abs(self._travel) > config.SLIDER_INTERACT_EPS:
            self._interacted = True
        self._x = move_along_track(self._x, dx)
        selected_rating, self.marker_x = snap_rating(self._x)

        if now_s - self._started_at_s >= config.RATING_TIMEOUT_S:
            self.rating = selected_rating
            self.no_response = 0 if self._interacted else 1
            self.active = False
            self.complete = True
            return True
        return False

    def draw(self) -> None:
        display.draw_rating(self._stimuli, self.marker_x)
