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

On macOS the detached cursor stays wherever it was parked, and clicks land
there. pyglet 1.5 parks it at the window centre, but gets the maths wrong for a
window on a secondary display, leaving it outside the window, so clicks hit the
desktop (and "click wallpaper to reveal desktop" fires). We re-park it at the
true centre after locking and after every refocus.

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
        win.winHandle.push_handlers(
            on_mouse_motion=self._on_motion,
            on_mouse_drag=self._on_drag,
            # pyglet re-locks on refocus, re-parking the cursor (wrongly) first.
            on_activate=self._on_activate,
        )
        win.backend.setMouseExclusive(True)
        self._locked = True
        self._center_cursor()

    def _on_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        self._dx += dx

    def _on_drag(
        self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int
    ) -> None:
        self._dx += dx

    def _on_activate(self) -> None:
        if self._locked:
            self._center_cursor()

    def _center_cursor(self) -> None:
        """macOS only: park the detached cursor at the window's centre."""
        nswindow = getattr(self._win.winHandle, "_nswindow", None)
        if nswindow is None:
            return  # not a Cocoa window; Windows' ClipCursor keeps it inside
        from pyglet.libs.darwin import cocoapy

        quartz = cocoapy.quartz
        frame = nswindow.frame()
        main_h = quartz.CGDisplayBounds(quartz.CGMainDisplayID()).size.height
        x, y = cocoa_to_quartz_center(
            frame.origin.x, frame.origin.y, frame.size.width, frame.size.height, main_h
        )
        self._win.winHandle.set_mouse_position(x, y, absolute=True)

    def take_dx(self) -> float:
        """Return horizontal motion since the last call, in height units."""
        dx, self._dx = self._dx, 0.0
        return dx / self._per_unit

    def release(self) -> None:
        """Let the cursor leave the window again."""
        if self._locked:
            self._locked = False
            self._win.backend.setMouseExclusive(False)


def cocoa_to_quartz_center(
    origin_x: float, origin_y: float, width: float, height: float, main_height: float
) -> tuple[float, float]:
    """Centre of a window frame, from Cocoa to Quartz global coordinates.

    Cocoa puts (0, 0) at the main display's bottom-left with y up; Quartz (the
    cursor warp) puts it at the main display's top-left with y down.
    """
    return origin_x + width / 2, main_height - (origin_y + height / 2)
