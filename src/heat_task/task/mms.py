"""One-off MMS command helpers used to drive the run (select/start) and to
assert that the thermode accepted each command, plus the operator-facing
setup/select steps run() walks through before the task begins."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from psychopy import core, gui, logging
from rich.console import Console
from rich.panel import Panel

from heat_task import config
from heat_task.medoc.client import MedocClient
from heat_task.medoc.models import MedocResponse, ReturnCode, TestState

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


def confirm_started(host: str, port: int, rcon: Console, response: MedocResponse | None) -> None:
    """Make sure START actually started the test on MMS; raise if it didn't.

    If MMS replied to START, the reply's return code says whether it worked.

    If START got no reply, that alone isn't treated as a failure, because MMS
    can answer late (the medoc CLI tolerates this too). Instead we ask MMS with
    STATUS whether the test is running. This matters because in Safe Mode MMS
    ignores START (and every command except STATUS): without this check the
    task would carry on as if the run had started while the thermode stays
    unpowered.
    """
    # MMS replied: the reply itself says whether START worked.
    if response is not None:
        require_ok(rcon, "MMS START", response)
        return

    # No reply: poll STATUS until the test shows as running, giving up after
    # START_CONFIRM_TIMEOUT_S.
    deadline = time.monotonic() + config.START_CONFIRM_TIMEOUT_S
    while True:
        status = send_command(host, port, "status")
        if status is not None and status.test_state == TestState.RUNNING:
            rcon.print("[yellow]MMS START gave no reply, but the test is running[/yellow]")
            return
        if time.monotonic() >= deadline:
            state = "no reply" if status is None else f"test_state={status.test_state}"
            raise RuntimeError(
                "MMS START gave no reply and the test is not running "
                f"({state}). Check the MMS Safety indicator; Safe Mode needs a Self-Test."
            )
        time.sleep(config.START_CONFIRM_POLL_S)


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
        logging.error(
            f"Aborting run: could not reach MMS at "
            f"{session_info.host}:{session_info.port}: {exc!r}"
        )
        logging.flush()
        win.close()
        gui.warnDlg(
            prompt=f"Could not reach MMS at {session_info.host}:{session_info.port}\n\n{exc}"
        )
        core.quit()
        return

    try:
        require_ok(rcon, "MMS program selected", response)
    except RuntimeError as exc:
        logging.error(f"Aborting run: MMS rejected the program selection: {exc!r}")
        logging.flush()
        win.close()
        gui.warnDlg(prompt=f"MMS rejected the program selection.\n\n{exc}")
        core.quit()
