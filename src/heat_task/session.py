"""Session initialisation: setup wizard, last-connection persistence, and
instruction presentation. Screen setup and run-directory creation now come from
psyexp_core (see __main__)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from psychopy.hardware import keyboard
from psyexp_core import instructions as core_instructions
from psyexp_core import wizard

from heat_task import config
from heat_task.conditions import conditions_dir
from heat_task.display import Stimuli, draw_instruction_page
from heat_task.medoc.transport import MedocTransport

_LAST_CONNECTION_PATH = conditions_dir().parent / ".ramp_hold_last_connection.json"

_SUBJECT_PLACEHOLDER = "XXX000"


@dataclass(frozen=True, slots=True)
class SessionInfo:
    subject_id: str
    host: str
    port: int
    run_file: str
    show_instructions: bool


def _validate_port(text: str) -> bool | str:
    try:
        int(text.strip())
    except ValueError:
        return "MMS port must be an integer"
    return True


def _validate_run_file(text: str) -> bool | str:
    name = text.strip()
    if not name:
        return "Run file is required"
    if not (conditions_dir() / name).exists():
        return f"Not found in conditions/: {name}"
    return True


def show_dialog() -> SessionInfo:
    last_connection = _load_last_connection()

    subject_id = (
        wizard.ask_text("Subject ID", placeholder=_SUBJECT_PLACEHOLDER).strip()
        or _SUBJECT_PLACEHOLDER
    )
    host = wizard.ask_text(
        "MMS host/IP",
        default=str(last_connection.get("host", "192.168.1.100")),
    ).strip()
    port = int(
        wizard.ask_text(
            "MMS port",
            default=str(last_connection.get("port", MedocTransport.DEFAULT_PORT)),
            validate=_validate_port,
        ).strip()
    )
    run_file = wizard.ask_text(
        "Run file",
        default="example.toml",
        validate=_validate_run_file,
    ).strip()
    show_instructions = wizard.ask_confirm("Show instructions?", default=True)

    _save_last_connection(host=host, port=port)

    return SessionInfo(
        subject_id=subject_id,
        host=host,
        port=port,
        run_file=run_file,
        show_instructions=show_instructions,
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


def display_instructions(
    win,
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
