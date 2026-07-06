"""Operator-gated phase screens (wait-for-start, end screen) over the shared
psyexp_core keyboard helpers."""

from __future__ import annotations

from psychopy import visual
from psychopy.hardware import keyboard
from psyexp_core.keyboard import clear_events, wait_for_key

from heat_task import config
from heat_task.task import display


def wait_for_start(
    win: visual.Window,
    stimuli: display.Stimuli,
    kb: keyboard.Keyboard | None,
) -> None:
    """Keep the participant crosshair onscreen until the experimenter starts."""
    clear_events(kb)
    while True:
        display.draw_crosshair(stimuli)
        win.flip()
        key_name = wait_for_key(
            kb, config.START_KEYS, quit_keys=config.QUIT_KEYS, clear_first=False
        )
        if key_name in config.START_KEYS:
            return


def run_end_screen(
    win: visual.Window,
    stimuli: display.Stimuli,
    kb: keyboard.Keyboard | None,
) -> None:
    """Show the closing screen until the operator dismisses it."""
    clear_events(kb)
    while True:
        display.draw_end(stimuli)
        win.flip()
        key_name = wait_for_key(
            kb, config.END_KEYS, quit_keys=config.QUIT_KEYS, clear_first=False
        )
        if key_name in config.END_KEYS:
            return
