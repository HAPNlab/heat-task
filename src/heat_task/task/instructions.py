"""Instruction-screen presentation, paged through the shared harness pager."""

from __future__ import annotations

from psychopy import visual
from psychopy.hardware import keyboard
from psyexp_core import instructions as core_instructions

from heat_task import config
from heat_task.task.display import Stimuli, draw_instruction_page


def display_instructions(
    win: visual.Window,
    stimuli: Stimuli,
    kb: keyboard.Keyboard | None,
) -> None:
    """Page through the instruction screens via the shared harness pager."""
    core_instructions.page_through(
        win,
        config.INSTRUCTION_PAGES,
        lambda page, is_last: draw_instruction_page(stimuli, page, is_last=is_last),
        forward_keys=config.INSTRUCTION_KEYS["forward"],
        back_keys=config.INSTRUCTION_KEYS["back"],
        quit_keys=config.QUIT_KEYS,
        kb=kb,
    )
