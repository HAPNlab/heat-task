"""Operator-gated phase screens (pretest, wait-for-start, end screen) over the
shared psyexp_core keyboard helpers."""

from __future__ import annotations

from psychopy import core, logging, visual
from psychopy.hardware import keyboard
from psyexp_core.keyboard import check_quit, clear_events, wait_for_key
from rich.console import Console

from heat_task import config
from heat_task.task import display, mms


def run_pretest(
    win: visual.Window,
    stimuli: display.Stimuli,
    kb: keyboard.Keyboard | None,
    host: str,
    port: int,
    rcon: Console,
) -> None:
    """Send the MMS pretest when the operator presses the pretest key, and
    return once MMS reports it done.

    The crosshair stays onscreen throughout. The start key is ignored (with a
    note on the terminal) until the pretest has been sent. If the pretest fails
    or times out, the failure is shown and the task waits for the quit key; an
    Escape after the pretest was sent ABORTs it first.
    """
    pretest_key = config.PRETEST_KEYS[0].upper()
    clear_events(kb)
    while True:
        display.draw_crosshair(stimuli)
        win.flip()
        key_name = wait_for_key(
            kb,
            [*config.PRETEST_KEYS, *config.START_KEYS],
            quit_keys=config.QUIT_KEYS,
            clear_first=False,
        )
        if key_name in config.PRETEST_KEYS:
            break
        rcon.print(f"[dim]{key_name} ignored: run the pretest first (press {pretest_key})[/dim]")

    def abort_and_quit() -> None:
        mms.halt(host, port, "abort", rcon)
        core.quit()

    def tick() -> None:
        display.draw_crosshair(stimuli)
        win.flip()
        check_quit(kb, config.QUIT_KEYS, on_quit=abort_and_quit)

    try:
        mms.send_pretest(host, port, rcon)
        with rcon.status("Pretest running... 0 s") as status:
            elapsed = mms.wait_for_pretest(
                host,
                port,
                on_tick=tick,
                on_progress=lambda s: status.update(f"Pretest running... {s:.0f} s"),
            )
    except mms.PretestError as exc:
        logging.error(f"MMS pretest failed: {exc}")
        logging.flush()
        if isinstance(exc, mms.PretestTimeout):
            mms.halt(host, port, "abort", rcon)
        mms.print_pretest_failed(rcon, exc)
        display.draw_crosshair(stimuli)
        win.flip()
        wait_for_key(kb, [], quit_keys=config.QUIT_KEYS)
        return  # unreachable: the quit key ends the session
    logging.exp(f"MMS pretest done in {elapsed:.1f} s")
    rcon.print(f"[green]Pretest done in {elapsed:.0f} s. MMS is ready.[/green]")


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
