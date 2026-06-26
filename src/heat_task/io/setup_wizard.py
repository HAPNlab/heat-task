"""Terminal setup wizard: collects subject/connection/run-file info and
remembers the last MMS connection between runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TypedDict

from psyexp_core import screen, wizard

from heat_task.io.conditions import conditions_dir
from heat_task.medoc.transport import MedocTransport

# Persisted under data/ (already git-ignored) rather than the repo root, so the
# working tree stays clean. data/ is the project's per-run state directory.
_LAST_CONNECTION_PATH = conditions_dir().parent / "data" / ".last_connection.json"

_SUBJECT_PLACEHOLDER = "XXX000"


class _LastConnection(TypedDict, total=False):
    """The subset of last-connection fields we persist between runs."""

    host: str
    port: int
    screen: int


@dataclass(frozen=True, slots=True)
class SessionInfo:
    subject_id: str
    host: str
    port: int
    run_file: str
    screen_index: int
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


def run_wizard() -> SessionInfo:
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
    screen_index = screen.prompt_screen(default=last_connection.get("screen"))
    show_instructions = wizard.ask_confirm("Show instructions?", default=True)

    _save_last_connection(host=host, port=port, screen=screen_index)

    return SessionInfo(
        subject_id=subject_id,
        host=host,
        port=port,
        run_file=run_file,
        screen_index=screen_index,
        show_instructions=show_instructions,
    )


def _load_last_connection() -> _LastConnection:
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
    screen = payload.get("screen")
    connection: _LastConnection = {}
    if isinstance(host, str) and host.strip():
        connection["host"] = host.strip()
    if isinstance(port, int):
        connection["port"] = port
    if isinstance(screen, int):
        connection["screen"] = screen
    return connection


def _save_last_connection(*, host: str, port: int, screen: int) -> None:
    payload = {"host": host, "port": port, "screen": screen}
    try:
        _LAST_CONNECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LAST_CONNECTION_PATH, "w") as handle:
            json.dump(payload, handle, indent=2)
    except OSError:
        return
