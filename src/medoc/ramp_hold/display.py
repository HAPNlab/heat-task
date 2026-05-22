"""PsychoPy visual construction and draw helpers for the ramp-and-hold task."""

from __future__ import annotations

from dataclasses import dataclass

from psychopy import visual
from psychopy.hardware.mouse import Mouse

from medoc.ramp_hold import config


@dataclass
class Stimuli:
    win: visual.Window
    crosshair_h: visual.Rect
    crosshair_v: visual.Rect
    crosshair_cap_left: visual.Circle
    crosshair_cap_right: visual.Circle
    crosshair_cap_top: visual.Circle
    crosshair_cap_bottom: visual.Circle
    ready: visual.TextStim
    rating_prompt: visual.TextStim
    slider_track: visual.Rect
    slider_marker: visual.Rect
    slider_no_pain: visual.TextStim
    slider_worst_pain: visual.TextStim
    mouse: Mouse
    instruction_text: visual.TextStim
    instruction_footer: visual.TextStim
    end: visual.TextStim


def build_stimuli(win: visual.Window) -> Stimuli:
    """Construct all visual stimuli and return a Stimuli dataclass."""
    y_scr = 1.0
    x_scr = float(win.size[0]) / float(win.size[1])
    font_h = y_scr / 25
    wrap_w = x_scr / 1.5

    # Crosshair: two Rect bars + four Circle end-caps to produce rounded arms
    arm_len = 0.14
    arm_thick = 0.018
    cap_r = arm_thick / 2
    half = arm_len / 2 - cap_r  # rect half-length; circles cover the tips
    crosshair_kw = dict(fillColor=config.TEXT_COLOR, lineColor=None, autoLog=False)
    crosshair_h = visual.Rect(win, pos=(0, 0), width=arm_len, height=arm_thick, **crosshair_kw)
    crosshair_v = visual.Rect(win, pos=(0, 0), width=arm_thick, height=arm_len, **crosshair_kw)
    crosshair_cap_left   = visual.Circle(win, pos=(-half - cap_r, 0), radius=cap_r, **crosshair_kw)
    crosshair_cap_right  = visual.Circle(win, pos=( half + cap_r, 0), radius=cap_r, **crosshair_kw)
    crosshair_cap_top    = visual.Circle(win, pos=(0,  half + cap_r), radius=cap_r, **crosshair_kw)
    crosshair_cap_bottom = visual.Circle(win, pos=(0, -half - cap_r), radius=cap_r, **crosshair_kw)

    ready = visual.TextStim(
        win,
        name="ready",
        text="Ready",
        pos=(0, 0),
        height=font_h * 4,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    rating_prompt = visual.TextStim(
        win,
        name="rating_prompt",
        text="Pain Intensity",
        pos=(0, config.SLIDER_Y + 0.14),
        height=font_h * 1.4,
        color=config.TEXT_COLOR,
        autoLog=False,
    )

    # Slider components
    slider_track = visual.Rect(
        win,
        width=config.SLIDER_HALF_W * 2,
        height=config.SLIDER_TRACK_H,
        pos=(0, config.SLIDER_Y),
        fillColor=config.TEXT_COLOR,
        lineColor=None,
        opacity=0.5,
        autoLog=False,
    )
    slider_marker = visual.Rect(
        win,
        width=0.006,
        height=config.SLIDER_MARKER_H,
        pos=(-config.SLIDER_HALF_W, config.SLIDER_Y),
        fillColor="red",
        lineColor=None,
        autoLog=False,
    )
    slider_no_pain = visual.TextStim(
        win,
        name="slider_no_pain",
        text="No Pain",
        pos=(-config.SLIDER_HALF_W, config.SLIDER_Y - 0.10),
        height=font_h,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    slider_worst_pain = visual.TextStim(
        win,
        name="slider_worst_pain",
        text="Worst Pain",
        pos=(config.SLIDER_HALF_W, config.SLIDER_Y - 0.10),
        height=font_h,
        color=config.TEXT_COLOR,
        autoLog=False,
    )
    mouse = Mouse(win=win, visible=False)

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
        crosshair_h=crosshair_h,
        crosshair_v=crosshair_v,
        crosshair_cap_left=crosshair_cap_left,
        crosshair_cap_right=crosshair_cap_right,
        crosshair_cap_top=crosshair_cap_top,
        crosshair_cap_bottom=crosshair_cap_bottom,
        ready=ready,
        rating_prompt=rating_prompt,
        slider_track=slider_track,
        slider_marker=slider_marker,
        slider_no_pain=slider_no_pain,
        slider_worst_pain=slider_worst_pain,
        mouse=mouse,
        instruction_text=instruction_text,
        instruction_footer=instruction_footer,
        end=end,
    )


def draw_crosshair(stimuli: Stimuli) -> None:
    stimuli.crosshair_h.draw()
    stimuli.crosshair_v.draw()
    stimuli.crosshair_cap_left.draw()
    stimuli.crosshair_cap_right.draw()
    stimuli.crosshair_cap_top.draw()
    stimuli.crosshair_cap_bottom.draw()


def draw_ready(stimuli: Stimuli) -> None:
    stimuli.ready.draw()


def draw_rating(stimuli: Stimuli, marker_x: float) -> None:
    stimuli.slider_marker.pos = (marker_x, config.SLIDER_Y)
    stimuli.rating_prompt.draw()
    stimuli.slider_track.draw()
    stimuli.slider_marker.draw()
    stimuli.slider_no_pain.draw()
    stimuli.slider_worst_pain.draw()


def draw_instruction_page(stimuli: Stimuli, text: str, *, is_last: bool) -> None:
    stimuli.instruction_text.text = text
    fwd = config.INSTRUCTION_KEYS["forward"][0]
    bck = config.INSTRUCTION_KEYS["back"][0]
    stimuli.instruction_footer.text = (
        f"Press {fwd} to continue to the task."
        if is_last
        else f"Press {fwd} to continue, {bck} to go back."
    )
    stimuli.instruction_text.draw()
    stimuli.instruction_footer.draw()


def draw_end(stimuli: Stimuli) -> None:
    stimuli.end.draw()
