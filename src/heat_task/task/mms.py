"""One-off MMS command helpers used to drive the run (select/start) and to
assert that the thermode accepted each command, plus the operator-facing
setup/select steps run() walks through before the task begins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from psychopy import core, gui
from rich.console import Console
from rich.panel import Panel

from heat_task import config
from heat_task.medoc.client import MedocClient
from heat_task.medoc.models import MedocResponse, ReturnCode

if TYPE_CHECKING:
    from heat_task.io.conditions import RunConfig
    from heat_task.io.setup_wizard import SessionInfo


def send_command(host: str, port: int, method_name: str, *args: object) -> MedocResponse | None:
    with MedocClient.connect(
        host,
        port,
        connect_timeout=config.CONNECT_TIMEOUT_S,
        recv_timeout=config.RECV_TIMEOUT_S,
    ) as client:
        method = getattr(client, method_name)
        return method(*args)


def require_ok(console: Console, label: str, response: MedocResponse | None) -> None:
    if response is None:
        raise RuntimeError(f"{label} failed: no response from MMS")
    # response.return_code is a raw int; ReturnCode is an IntEnum so it compares
    # directly, and describe() unpacks the bitfield into readable flag names.
    if response.return_code != ReturnCode.OK:
        flags = ReturnCode.describe(response.return_code)
        raise RuntimeError(f"{label} failed: {flags} (code {response.return_code})")
    console.print(f"[green]{label} ok[/green]")


def prompt_setup(rcon: Console) -> None:
    """Walk the operator through arming the MMS, then block until they confirm."""
    rcon.print(
        Panel(
            "[bold]1.[/bold] In MMS, click [bold]Go to Test[/bold]\n"
            "[bold]2.[/bold] Confirm the status reads "
            "[italic]'External Control: TSA 2 is waiting for Test Program'[/italic]\n"
            "[bold]3.[/bold] Press [bold]Enter[/bold] here to continue",
            title="[bold yellow]MMS Setup[/bold yellow]",
            border_style="yellow",
            expand=False,
            padding=(1, 2),
        )
    )
    input()


def select_program(
    session_info: SessionInfo, run_config: RunConfig, win, rcon: Console
) -> None:
    """Select the program on the MMS, aborting the run with a dialog if the
    thermode is unreachable or rejects the selection."""
    try:
        response = send_command(
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
        require_ok(rcon, "MMS program selected", response)
    except RuntimeError as exc:
        win.close()
        gui.warnDlg(prompt=f"MMS rejected the program selection.\n\n{exc}")
        core.quit()
