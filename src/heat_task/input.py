"""Keyboard helpers — re-exported from psyexp_core so the task code keeps using
the ``heat_task.input`` path while the implementation lives in the shared
harness."""

from __future__ import annotations

from psyexp_core.keyboard import (
    KEYBOARD_BACKEND,
    build_keyboard,
    clear_events,
    configure_psychopy_backend,
    get_keys,
    wait_for_keys,
)

__all__ = [
    "KEYBOARD_BACKEND",
    "build_keyboard",
    "clear_events",
    "configure_psychopy_backend",
    "get_keys",
    "wait_for_keys",
]
