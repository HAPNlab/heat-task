"""Keyboard helpers that work with either PTB or PsychoPy's event backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import psychtoolbox  # noqa: F401
except ImportError:
    KEYBOARD_BACKEND = "event"
else:
    KEYBOARD_BACKEND = "ptb"

from psychopy import event, prefs

if TYPE_CHECKING:
    from psychopy.hardware.keyboard import Keyboard


def configure_psychopy_backend() -> None:
    prefs.hardware["keyboardBackend"] = KEYBOARD_BACKEND


def build_keyboard() -> Keyboard | None:
    if KEYBOARD_BACKEND == "ptb":
        from psychopy.hardware import keyboard

        return keyboard.Keyboard()
    return None


def clear_events(kb: Keyboard | None) -> None:
    if KEYBOARD_BACKEND == "ptb":
        if kb is not None:
            kb.clearEvents()
        return
    event.clearEvents(eventType="keyboard")


def wait_for_keys(kb: Keyboard | None, key_list: list[str]) -> list[str]:
    if KEYBOARD_BACKEND == "ptb":
        if kb is None:
            return []
        return [key_press.name for key_press in kb.waitKeys(keyList=key_list, waitRelease=False)]
    pressed = event.waitKeys(keyList=key_list)
    return [str(key_name) for key_name in (pressed or [])]


def get_keys(kb: Keyboard | None, key_list: list[str]) -> list[str]:
    if KEYBOARD_BACKEND == "ptb":
        if kb is None:
            return []
        return [key_press.name for key_press in kb.getKeys(keyList=key_list, waitRelease=False)]
    return [str(key_name) for key_name in event.getKeys(keyList=key_list)]
