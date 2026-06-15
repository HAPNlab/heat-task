# ruff: noqa: E402

"""
Entry point: `python -m heat_task` or `heat-task`.
Wires the PsychoPy task modules together.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from psychopy import core

core.checkPygletDuringWait = False

from psychopy import gui, logging
from psyexp_core import rundir, screen
from rich.console import Console

from heat_task import input as task_input

task_input.configure_psychopy_backend()

from heat_task import config, display, recorder, session, trial
from heat_task.conditions import load_run_config
from heat_task.console import TrialLiveView
from heat_task.medoc.models import ReturnCode


def run() -> None:
    dev_mode = "--dev" in sys.argv
    session_info = session.show_dialog()
    run_config = load_run_config(session_info.run_file)
    session_time = datetime.now()

    rcon = Console(stderr=True)
    rcon.print(
        "[yellow]In MMS, click 'Go to Test' and confirm the status reads "
        "'External Control: TSA 2 is waiting for Test Program', "
        "then press Enter to continue.[/yellow]"
    )
    input()

    win_res, win, screen_diag = screen.setup_screen(color=config.WINDOW_COLOR)
    frame_rate = 1000.0 / screen_diag.calib_median_ms if screen_diag.calib_median_ms else 60.0
    if frame_rate >= 200:
        frame_rate = 60.0

    data_dir = Path("data")
    run_stem = Path(session_info.run_file).stem
    run_dir = rundir.make_run_dir(data_dir, f"{session_info.subject_id}_{run_stem}", session_time)
    logging.LogFile(str(run_dir / "experiment.log"), level=logging.EXP)
    logging.console.setLevel(logging.WARNING)

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

    stimuli_obj = display.build_stimuli(win)
    kb = task_input.build_keyboard()
    win.mouseVisible = dev_mode  # show cursor in dev so mouse can simulate trackball

    recorder.write_manifest(
        run_dir, session_info, session_time, run_config, frame_rate, screen_diag, win_res
    )

    # Verify MMS is reachable before showing any task UI.
    try:
        response = trial.send_command(
            session_info.host,
            session_info.port,
            "select_test",
            run_config.program_id,
        )
    except Exception as exc:
        win.close()
        gui.warnDlg(
            prompt=f"Could not reach MMS at {session_info.host}:{session_info.port}\n\n{exc}"
        )
        core.quit()
        return

    try:
        trial.require_ok(rcon, "MMS program selected", response)
    except RuntimeError as exc:
        win.close()
        gui.warnDlg(prompt=f"MMS rejected the program selection.\n\n{exc}")
        core.quit()

    rcon.print(
        f"[yellow]Press {config.START_KEYS[0]} in PsychoPy to send START to MMS.[/yellow]"
    )

    if session_info.show_instructions:
        session.display_instructions(win, stimuli_obj, kb)

    trial.wait_for_start(win, stimuli_obj, kb)

    start_response = trial.send_command(session_info.host, session_info.port, "start")
    if start_response is not None and start_response.return_code != int(ReturnCode.OK):
        raise RuntimeError(f"MMS START failed with return code {start_response.return_code}")

    task_start = time.monotonic()
    file_stem = f"{session_info.subject_id}_{Path(session_info.run_file).stem}"
    behavior_writer = recorder.BehaviorWriter(run_dir / f"behavioral_{file_stem}.csv")
    trace_writer = recorder.TraceWriter(run_dir / f"temperature_trace_{file_stem}.csv")

    poller = trial.StatusPoller(session_info.host, session_info.port)
    trace_index = 0
    prev_baseline_return_s: float | None = None
    poller.start()
    try:
        with TrialLiveView(rcon, len(run_config.trials)) as view:
            for trial_index, trial_config in enumerate(run_config.trials, start=1):
                view.start_trial(trial_index, trial_config.baseline, trial_config.target_temp)
                record, trace_index = trial.run_trial(
                    win=win,
                    stimuli=stimuli_obj,
                    kb=kb,
                    task_start=task_start,
                    trial_n=trial_index,
                    trial_config=trial_config,
                    trace_index=trace_index,
                    trace_writer=trace_writer,
                    poller=poller,
                    initial_delay_s=run_config.initial_delay_s,
                    prev_baseline_return_s=prev_baseline_return_s,
                    view=view,
                )
                behavior_writer.append(record)
                prev_baseline_return_s = record.baseline_return_s if isinstance(record.baseline_return_s, float) else None

        rcon.print("[bold green]Run complete[/bold green]")
        trial.run_end_screen(win, stimuli_obj, kb)
    finally:
        poller.stop()
        behavior_writer.close()
        trace_writer.close()
        logging.flush()
        win.close()
        core.quit()


if __name__ == "__main__":
    run()
