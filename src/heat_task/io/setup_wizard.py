"""Terminal setup wizard: collects subject/connection/run-file info and
remembers the last MMS connection, screen and run file between runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import questionary
from psyexp_core import screen, wizard
from pydantic import BaseModel, ValidationError, field_validator

from heat_task.io.conditions import (
    conditions_dir,
    list_run_files,
    load_run_config,
    summarize_load_error,
    summarize_run_config,
)
from heat_task.medoc.transport import MedocTransport

# Persisted under data/ (already git-ignored) rather than the repo root, so the
# working tree stays clean. data/ is the project's per-run state directory.
_LAST_CONNECTION_PATH = conditions_dir().parent / "data" / ".last_connection.json"

_SUBJECT_PLACEHOLDER = "XXX000"


class LastConnection(BaseModel):
    """Wizard answers remembered between runs (MMS connection, screen, run file).
    All optional: a missing or malformed file yields an all-None instance, and
    absent fields fall back to the wizard's defaults. Replaces hand-rolled JSON +
    isinstance validation, matching the pydantic approach used for run files in
    conditions.py."""

    host: str | None = None
    port: int | None = None
    screen: int | None = None
    run_file: str | None = None

    @field_validator("host")
    @classmethod
    def _normalize_host(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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


def _run_file_choice(path: Path, *, last_used: bool) -> questionary.Choice:
    """A list entry for one run file. Each file is loaded up front so a broken
    one shows as unselectable, with the reason, instead of crashing the task
    after the wizard; a valid one carries a summary shown while it's highlighted."""
    title = f"{path.stem}  (last used)" if last_used else path.stem
    try:
        config = load_run_config(path)
    except (OSError, ValueError) as exc:  # TOMLDecodeError is a ValueError
        return questionary.Choice(
            title=title, value=path.name, disabled=f"invalid: {summarize_load_error(exc)}"
        )
    return questionary.Choice(
        title=title, value=path.name, description=summarize_run_config(config)
    )


def _ask_run_file(last_run_file: str | None) -> str:
    """Pick a run file from conditions/ with the arrow keys; the cursor starts on
    the one used last, so a repeat run is a single Enter. Returns the file name."""
    choices = [
        _run_file_choice(path, last_used=path.name == last_run_file)
        for path in list_run_files()
    ]
    selectable = [choice for choice in choices if not choice.disabled]
    if not selectable:
        problems = "".join(f"\n  {c.value}: {c.disabled}" for c in choices)
        raise SystemExit(f"No usable run files (*.toml) in {conditions_dir()}{problems}")
    default = next((c for c in selectable if c.value == last_run_file), selectable[0])
    return wizard.ask_select("Run file", choices, default=default)


def run_wizard() -> SessionInfo:
    last_connection = _load_last_connection()

    subject_id = (
        wizard.ask_text("Subject ID", placeholder=_SUBJECT_PLACEHOLDER).strip()
        or _SUBJECT_PLACEHOLDER
    )
    host = wizard.ask_text(
        "MMS host/IP",
        default=last_connection.host or "192.168.1.100",
    ).strip()
    port = int(
        wizard.ask_text(
            "MMS port",
            default=str(
                last_connection.port
                if last_connection.port is not None
                else MedocTransport.DEFAULT_PORT
            ),
            validate=_validate_port,
        ).strip()
    )
    run_file = _ask_run_file(last_connection.run_file)
    screen_index = screen.prompt_screen(default=last_connection.screen)
    show_instructions = wizard.ask_confirm("Show instructions?", default=True)

    _save_last_connection(host=host, port=port, screen=screen_index, run_file=run_file)

    return SessionInfo(
        subject_id=subject_id,
        host=host,
        port=port,
        run_file=run_file,
        screen_index=screen_index,
        show_instructions=show_instructions,
    )


def _load_last_connection() -> LastConnection:
    """Best-effort load; a missing or malformed file yields an all-None instance."""
    try:
        return LastConnection.model_validate_json(_LAST_CONNECTION_PATH.read_text())
    except (OSError, ValidationError):
        return LastConnection()


def _save_last_connection(*, host: str, port: int, screen: int, run_file: str) -> None:
    """Best-effort persist; never raise into the wizard if the write fails."""
    try:
        _LAST_CONNECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LAST_CONNECTION_PATH.write_text(
            LastConnection(
                host=host, port=port, screen=screen, run_file=run_file
            ).model_dump_json(indent=2)
        )
    except OSError:
        return
