"""Session initialisation: dialog, screen setup, output directory, and instructions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyglet
from psychopy import core, gui, monitors, visual
from psychopy.hardware import keyboard

from medoc.ramp_hold import config
from medoc.ramp_hold.conditions import conditions_dir
from medoc.ramp_hold.display import Stimuli, draw_instruction_page
from medoc.ramp_hold.input import clear_events, wait_for_keys
from medoc.transport import MedocTransport

_LAST_CONNECTION_PATH = conditions_dir().parent / ".ramp_hold_last_connection.json"


@dataclass(frozen=True, slots=True)
class SessionInfo:
    subject_id: str
    host: str
    port: int
    run_file: str
    show_instructions: bool


def show_dialog() -> SessionInfo:
    last_connection = _load_last_connection()
    defaults = {
        "Subject ID": "XXX000",
        "MMS host/IP": last_connection.get("host", "192.168.1.100"),
        "MMS port": str(last_connection.get("port", MedocTransport.DEFAULT_PORT)),
        "Run file": "example.toml",
        "Show instructions? (yes/no)": "yes",
    }

    while True:
        dlg = gui.DlgFromDict(dictionary=defaults, title="Medoc Ramp/Hold Task")
        if not dlg.OK:
            core.quit()

        port_raw = str(defaults["MMS port"]).strip()
        try:
            port = int(port_raw)
        except ValueError:
            gui.warnDlg(prompt=f"MMS port must be an integer (got {port_raw!r}).")
            continue

        run_file = str(defaults["Run file"]).strip()
        if not run_file:
            gui.warnDlg(prompt="Run file is required.")
            continue
        if not (conditions_dir() / run_file).exists():
            gui.warnDlg(prompt=f"Run file not found in conditions/: {run_file}")
            continue

        host = str(defaults["MMS host/IP"]).strip()
        _save_last_connection(host=host, port=port)

        return SessionInfo(
            subject_id=str(defaults["Subject ID"]).strip(),
            host=host,
            port=port,
            run_file=run_file,
            show_instructions=str(defaults["Show instructions? (yes/no)"]).strip().lower()
            == "yes",
        )


def _load_last_connection() -> dict[str, str | int]:
    if not _LAST_CONNECTION_PATH.exists():
        return {}

    try:
        with open(_LAST_CONNECTION_PATH) as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    host = payload.get("host")
    port = payload.get("port")
    connection: dict[str, str | int] = {}
    if isinstance(host, str) and host.strip():
        connection["host"] = host.strip()
    if isinstance(port, int):
        connection["port"] = port
    return connection


def _save_last_connection(*, host: str, port: int) -> None:
    payload = {"host": host, "port": port}
    try:
        with open(_LAST_CONNECTION_PATH, "w") as handle:
            json.dump(payload, handle, indent=2)
    except OSError:
        return


def setup_screen() -> tuple[list[int], visual.Window]:
    display = pyglet.canvas.get_display()
    screens = display.get_screens()
    win_res = [screens[-1].width, screens[-1].height]
    exp_mon = monitors.Monitor("exp_mon")
    exp_mon.setSizePix(win_res)
    win = visual.Window(
        size=win_res,
        screen=len(screens) - 1,
        allowGUI=True,
        fullscr=True,
        monitor=exp_mon,
        units="height",
        color=config.WINDOW_COLOR,
    )
    return win_res, win


def make_run_dir(data_dir: Path, session_info: SessionInfo, session_time: datetime) -> Path:
    ts = session_time.strftime("%Y%m%dT%H%M%S")
    run_stem = Path(session_info.run_file).stem
    run_dir = data_dir / f"{session_info.subject_id}_{run_stem}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def display_instructions(
    win: visual.Window,
    stimuli: Stimuli,
    kb: keyboard.Keyboard | None,
) -> None:
    """Display instruction pages one at a time."""
    clear_events(kb)
    page_idx = 0

    while True:
        draw_instruction_page(
            stimuli,
            config.INSTRUCTION_PAGES[page_idx],
            is_last=page_idx == len(config.INSTRUCTION_PAGES) - 1,
        )
        win.flip()
        pressed = wait_for_keys(
            kb,
            [
                *config.INSTRUCTION_KEYS["forward"],
                *config.INSTRUCTION_KEYS["back"],
                *config.QUIT_KEYS,
            ],
        )
        key_name = pressed[0]
        if key_name in config.QUIT_KEYS:
            core.quit()
        if key_name in config.INSTRUCTION_KEYS["back"] and page_idx > 0:
            page_idx -= 1
        elif (
            key_name in config.INSTRUCTION_KEYS["forward"]
            and page_idx == len(config.INSTRUCTION_PAGES) - 1
        ):
            return
        elif key_name in config.INSTRUCTION_KEYS["forward"]:
            page_idx += 1
