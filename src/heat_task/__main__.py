# ruff: noqa: E402

"""
Entry point: `python -m heat_task` or `heat-task`.
Wires the PsychoPy task modules together; the real work lives in heat_task.task
and heat_task.io, so run() stays a readable top-to-bottom script of the run.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

# Parse before PsychoPy imports — PsychoPy registers its own argparser at import time,
# so our parser must run first to own --help.
_parser = argparse.ArgumentParser(prog="heat-task", description="Heat pain task runner")
_parser.add_argument(
    "--save-net-events",
    action="store_true",
    help="Write net_events_*.csv alongside behavioral data for network diagnostics",
)
_args, _ = _parser.parse_known_args()

from psychopy import core

core.checkPygletDuringWait = False

from psychopy import logging
from psyexp_core import rundir, screen
from psyexp_core.keyboard import build_keyboard, configure_psychopy_backend
from rich.console import Console
from rich.panel import Panel

configure_psychopy_backend()

from heat_task import config
from heat_task.io import recording
from heat_task.io.conditions import load_run_config
from heat_task.io.setup_wizard import run_wizard
from heat_task.medoc.models import ReturnCode
from heat_task.task import display, instructions, mms
from heat_task.task.console import TrialLiveView
from heat_task.task.framerate import resolve_frame_rate
from heat_task.task.phases import run_end_screen, wait_for_start
from heat_task.task.status import StatusPoller
from heat_task.task.trial import TrialRuntime, run_trials


def run() -> None:
    # ── SESSION & CONFIG ──────────────────────────────────────────────────────
    session_info = run_wizard()
    run_config = load_run_config(session_info.run_file)
    session_time = datetime.now()

    # ── MMS SETUP ─────────────────────────────────────────────────────────────
    # Walk the operator through arming the MMS before we open the window.
    rcon = Console(stderr=True)
    mms.prompt_setup(rcon)

    # ── SCREEN & FRAME RATE ───────────────────────────────────────────────────
    win_res, win, screen_diag = screen.setup_screen(color=config.WINDOW_COLOR)
    frame_rate = resolve_frame_rate(screen_diag.calib_median_ms)

    # ── LOGGING ───────────────────────────────────────────────────────────────
    data_dir = Path("data")
    run_stem = Path(session_info.run_file).stem
    run_dir = rundir.make_run_dir(data_dir, f"{session_info.subject_id}_{run_stem}", session_time)
    logging.LogFile(str(run_dir / "experiment.log"), level=logging.EXP)
    logging.console.setLevel(logging.WARNING)

    # ── SESSION SUMMARY ───────────────────────────────────────────────────────
    rcon.print(
        f"[bold]Session:[/bold] subject=[cyan]{session_info.subject_id}[/cyan]  "
        f"run-file=[cyan]{session_info.run_file}[/cyan]"
    )
    rcon.print(
        f"[bold]MMS:[/bold] host=[cyan]{session_info.host}[/cyan]  "
        f"program-word=[cyan]{run_config.program_word}[/cyan]"
    )
    rcon.print(f"[bold]Frame rate:[/bold] {frame_rate:.1f} Hz")
    logging.exp(
        f"Session: subject={session_info.subject_id}  run-file={session_info.run_file}  "
        f"host={session_info.host}"
    )
    logging.exp(f"Frame rate: {frame_rate:.1f} Hz")

    # ── BUILD STIMULI & KEYBOARD ──────────────────────────────────────────────
    stimuli_obj = display.build_stimuli(win)
    kb = build_keyboard()
    win.mouseVisible = False

    # ── MANIFEST ──────────────────────────────────────────────────────────────
    # Snapshot all run parameters before anything can fail.
    recording.write_manifest(
        run_dir, session_info, session_time, run_config, frame_rate, screen_diag, win_res
    )

    # ── SELECT MMS PROGRAM ────────────────────────────────────────────────────
    mms.select_program(session_info, run_config, win, rcon)

    # ── INSTRUCTIONS ──────────────────────────────────────────────────────────
    if session_info.show_instructions:
        instructions.display_instructions(win, stimuli_obj, kb)

    # ── START THE RUN ─────────────────────────────────────────────────────────
    # Block on the start key, then fire START so PsychoPy and the MMS begin together.
    start_key = config.START_KEYS[0]
    rcon.print(
        Panel(
            f"[bold]1.[/bold] In MMS, click [bold]Pre-test[/bold] "
            "— [bold red]do NOT click Start[/bold red]\n"
            f"[bold]2.[/bold] Press [bold]{start_key}[/bold] in the PsychoPy window when ready\n"
            f"[dim]PsychoPy sends START automatically on [/dim][bold]{start_key}[/bold]"
            "[dim], so both systems begin at the same time.[/dim]",
            title="[bold green]Start the Run[/bold green]",
            border_style="green",
            expand=False,
            padding=(1, 2),
        )
    )
    wait_for_start(win, stimuli_obj, kb)

    start_response = mms.send_command(session_info.host, session_info.port, "start")
    if start_response is not None and start_response.return_code != ReturnCode.OK:
        raise RuntimeError(f"MMS START failed with return code {start_response.return_code}")

    # ── RUN CLOCK & OUTPUT FILES ──────────────────────────────────────────────
    # The run clock reads 0 at the START instant; constructing a core.Clock resets
    # it to now. Both the poller and the trial loop read this one object, so every
    # recorded time_s is already relative to START with no offset arithmetic.
    run_clock = core.Clock()
    file_stem = f"{session_info.subject_id}_{Path(session_info.run_file).stem}"
    behavior_writer, trace_writer, net_event_writer = recording.make_writers(
        run_dir, file_stem, save_net_events=_args.save_net_events
    )

    # ── POLLER & TRIAL LOOP ───────────────────────────────────────────────────
    # Start the background status poller and run the trial loop, tearing
    # everything down in the finally block whatever happens.
    poller = StatusPoller(session_info.host, session_info.port, run_clock)
    poller.start()
    try:
        with TrialLiveView(rcon, len(run_config.trials)) as view:
            runtime = TrialRuntime(
                win=win,
                stimuli=stimuli_obj,
                kb=kb,
                clock=run_clock,
                trace_writer=trace_writer,
                net_event_writer=net_event_writer,
                poller=poller,
                view=view,
            )
            run_trials(runtime, run_config, view, behavior_writer)

        rcon.print("[bold green]Run complete[/bold green]")
        exit_key = config.END_KEYS[0]
        rcon.print(f"[bold yellow]Press '{exit_key}' to exit the experiment...[/bold yellow]")
        run_end_screen(win, stimuli_obj, kb)
    finally:
        # ── CLEANUP ───────────────────────────────────────────────────────────
        poller.stop()
        behavior_writer.close()
        trace_writer.close()
        if net_event_writer is not None:
            net_event_writer.close()
        logging.flush()
        win.close()
        core.quit()


if __name__ == "__main__":
    run()
