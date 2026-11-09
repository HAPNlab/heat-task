"""Lock the system cursor to the task window and read the trackball's raw motion.

To the computer the trackball is just another mouse, so left alone it moves the
one system cursor anywhere — onto the experimenter's screen, the taskbar, other
apps. While the task window is open we put it in pyglet's *exclusive* mouse mode,
which confines the cursor to the window (Windows: ``ClipCursor`` + Raw Input;
macOS: the cursor is detached from the mouse). Clicks can then only land on the
task window, which ignores them.

Exclusive mode reports movement only as deltas — the absolute position pyglet
passes PsychoPy stops changing — so the slider reads the deltas collected here
instead of PsychoPy's ``Mouse.getPos``. The lock covers every mouse on the
computer, not only the trackball; pyglet drops it while the window is unfocused
(e.g. after Alt+Tab) and restores it on refocus.

Kept free of PsychoPy imports so it can be tested on the headless CI job.
"""

from __future__ import annotations

from typing import Any


class LockedPointer:
    """Confine the cursor to *win* and accumulate horizontal motion.

    ``take_dx`` returns the motion since the last call in PsychoPy "height"
    units (window height = 1.0) and resets the total. ``release`` unlocks the
    cursor; it is safe to call more than once.
    """

    def __init__(self, win: Any) -> None:
        self._win = win
        self._dx = 0.0
        self._locked = False
        # pyglet reports deltas in window coordinates, so dividing by the window
        # height in the same coordinates gives height units.
        self._per_unit = float(win.winHandle.height)
        # Pushed handlers run before PsychoPy's own and return None, so the
        # event still propagates. A held button turns motion into a drag, which
        # must count too or the slider would freeze while a button is down.
        win.winHandle.push_handlers(on_mouse_motion=self._on_motion, on_mouse_drag=self._on_drag)
        win.backend.setMouseExclusive(True)
        self._locked = True

    def _on_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        self._dx += dx

    def _on_drag(
        self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int
    ) -> None:
        self._dx += dx

    def take_dx(self) -> float:
        """Return horizontal motion since the last call, in height units."""
        dx, self._dx = self._dx, 0.0
        return dx / self._per_unit

    def release(self) -> None:
        """Let the cursor leave the window again."""
        if self._locked:
            self._locked = False
            self._win.backend.setMouseExclusive(False)
