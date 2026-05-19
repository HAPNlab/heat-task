# ruff: noqa: E402

"""
Entry point: `python -m medoc.ramp_hold` or `medoc-ramp-hold`.
Wires the PsychoPy task modules together.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from psychopy import core

core.checkPygletDuringWait = False

from psychopy import logging
from rich.console import Console

from medoc.ramp_hold import input as task_input

task_input.configure_psychopy_backend()

from medoc.models import ReturnCode
from medoc.ramp_hold import config, display, recorder, session, trial
from medoc.ramp_hold.conditions import load_run_config


def run() -> None:
    session_info = session.show_dialog()
    run_config = load_run_config(session_info.run_file)
    session_time = datetime.now()

    _, win = session.setup_screen()
    measured_fps = win.getActualFrameRate()
    frame_rate = measured_fps if (measured_fps is not None and measured_fps < 200) else 60.0

    data_dir = Path("data")
    run_dir = session.make_run_dir(data_dir, session_info, session_time)
    logging.LogFile(str(run_dir / "experiment.log"), level=logging.EXP)
    logging.console.setLevel(logging.WARNING)

    rcon = Console(stderr=True)
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
    win.mouseVisible = False

    recorder.write_manifest(run_dir, session_info, session_time, run_config, frame_rate)

    if session_info.show_instructions:
        session.display_instructions(win, stimuli_obj, kb)

    trial.require_ok(
        rcon,
        "select",
        trial.send_command(
            session_info.host,
            session_info.port,
            "select_test",
            run_config.program_id,
        ),
    )
    rcon.print(
        "[yellow]Program selected in MMS. Click Pretest in MMS, then press "
        f"{config.START_KEYS[0]} in PsychoPy to send START.[/yellow]"
    )

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
    poller.start()
    try:
        for trial_index, trial_config in enumerate(run_config.trials, start=1):
            rcon.print(
                f"[bold]Trial {trial_index}/{len(run_config.trials)}:[/bold] "
                f"baseline={trial_config.baseline:.2f}C target={trial_config.target_temp:.2f}C"
            )
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
            )
            behavior_writer.append(record)

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
