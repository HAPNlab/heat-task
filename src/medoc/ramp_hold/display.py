"""PsychoPy visual construction and draw helpers for the ramp-and-hold task."""

from __future__ import annotations

from dataclasses import dataclass

from psychopy import visual

from medoc.ramp_hold import config


@dataclass
class Stimuli:
    win: visual.Window
    crosshair: visual.TextStim
    ready: visual.TextStim
    rating_prompt: visual.TextStim
    rating_scale: visual.TextStim
    instruction_text: visual.TextStim
    instruction_footer: visual.TextStim
    end: visual.TextStim


def build_stimuli(win: visual.Window) -> Stimuli:
    """Construct all visual stimuli and return a Stimuli dataclass."""
    y_scr = 1.0
    x_scr = float(win.size[0]) / float(win.size[1])
    font_h = y_scr / 25
    wrap_w = x_scr / 1.5

    crosshair = visual.TextStim(
        win,
        name="crosshair",
        text="+",
        pos=(0, 0),
        height=font_h * 2,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    ready = visual.TextStim(
        win,
        name="ready",
        text="READY",
        pos=(0, 0),
        height=font_h * 1.5,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    rating_prompt = visual.TextStim(
        win,
        name="rating_prompt",
        text="How painful was that?",
        pos=(0, font_h * 3),
        height=font_h,
        wrapWidth=wrap_w,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    rating_scale = visual.TextStim(
        win,
        name="rating_scale",
        text="",
        pos=(0, -font_h),
        height=font_h,
        wrapWidth=wrap_w,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    instruction_text = visual.TextStim(
        win,
        name="instruction_text",
        text="",
        pos=(0, y_scr / 10),
        height=font_h,
        wrapWidth=wrap_w,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    instruction_footer = visual.TextStim(
        win,
        name="instruction_footer",
        text="Press Right to continue, Left to go back.",
        pos=(0, -y_scr / 4),
        height=font_h * 0.9,
        wrapWidth=wrap_w,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    end = visual.TextStim(
        win,
        name="end",
        text="Thank you!",
        pos=(0, 0),
        height=font_h,
        wrapWidth=wrap_w,
        color=config.TEXT_COLOR,
        autoLog=False,
    )

    return Stimuli(
        win=win,
        crosshair=crosshair,
        ready=ready,
        rating_prompt=rating_prompt,
        rating_scale=rating_scale,
        instruction_text=instruction_text,
        instruction_footer=instruction_footer,
        end=end,
    )


def draw_crosshair(stimuli: Stimuli) -> None:
    stimuli.crosshair.draw()


def draw_ready(stimuli: Stimuli) -> None:
    stimuli.ready.draw()


def draw_rating(stimuli: Stimuli, selected_rating: int) -> None:
    options = []
    for value in range(11):
        if value == selected_rating:
            options.append(f"[{value}]")
        else:
            options.append(str(value))
    stimuli.rating_scale.text = "  ".join(options)
    stimuli.rating_prompt.draw()
    stimuli.rating_scale.draw()


def draw_instruction_page(stimuli: Stimuli, text: str, *, is_last: bool) -> None:
    stimuli.instruction_text.text = text
    stimuli.instruction_footer.text = (
        "Press Right to continue to the task."
        if is_last
        else "Press Right to continue, Left to go back."
    )
    stimuli.instruction_text.draw()
    stimuli.instruction_footer.draw()


def draw_end(stimuli: Stimuli) -> None:
    stimuli.end.draw()
