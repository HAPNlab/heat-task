"""The locked pointer must lock on creation, collect motion and drags, and unlock once."""

import pytest

from heat_task.task.pointer import LockedPointer


class FakeWinHandle:
    height = 1000

    def __init__(self):
        self.handlers = {}

    def push_handlers(self, **handlers):
        self.handlers.update(handlers)


class FakeBackend:
    def __init__(self):
        self.exclusive_calls = []

    def setMouseExclusive(self, exclusive):
        self.exclusive_calls.append(exclusive)


class FakeWin:
    def __init__(self):
        self.winHandle = FakeWinHandle()
        self.backend = FakeBackend()


def test_locks_on_creation():
    win = FakeWin()
    LockedPointer(win)
    assert win.backend.exclusive_calls == [True]


def test_motion_and_drags_accumulate_in_height_units():
    win = FakeWin()
    pointer = LockedPointer(win)
    win.winHandle.handlers["on_mouse_motion"](0, 0, 30, 5)
    win.winHandle.handlers["on_mouse_drag"](0, 0, 20, 5, 1, 0)
    assert pointer.take_dx() == pytest.approx(50 / FakeWinHandle.height)


def test_take_dx_resets():
    win = FakeWin()
    pointer = LockedPointer(win)
    win.winHandle.handlers["on_mouse_motion"](0, 0, 30, 0)
    pointer.take_dx()
    assert pointer.take_dx() == 0.0


def test_handlers_let_the_event_propagate():
    win = FakeWin()
    LockedPointer(win)
    assert win.winHandle.handlers["on_mouse_motion"](0, 0, 1, 0) is None
    assert win.winHandle.handlers["on_mouse_drag"](0, 0, 1, 0, 1, 0) is None


def test_release_unlocks_once():
    win = FakeWin()
    pointer = LockedPointer(win)
    pointer.release()
    pointer.release()
    assert win.backend.exclusive_calls == [True, False]
