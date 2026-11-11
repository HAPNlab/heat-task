"""One-off MMS command helpers used to drive the run (select/start) and to
assert that the thermode accepted each command, plus the operator-facing
setup/select steps run() walks through before the task begins."""

from __future__ import annotations

import time
from collections.abc import Callable
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


def halt(host: str, port: int, command: str, rcon: Console) -> None:
    """Send a stop/abort to the MMS, swallowing any failure so the caller's
    cleanup always continues even if the thermode is unreachable or the test
    has already ended."""
    try:
        send_command(host, port, command)
    except Exception as exc:  # noqa: BLE001 — best-effort shutdown, never re-raise
        rcon.print(f"[yellow]MMS {command} failed during shutdown: {exc}[/yellow]")


class PretestError(RuntimeError):
    """The pretest did not complete; the message is shown to the operator."""


class PretestTimeout(PretestError):
    """The pretest started but did not finish in time, so MMS needs an ABORT."""


def send_pretest(host: str, port: int, rcon: Console) -> None:
    """Send the first START, which MMS runs as the pretest.

    A reply with an error code raises PretestError. No reply is tolerated, as
    for the run START: MMS can answer late, and wait_for_pretest watches STATUS
    to see the pretest through either way.
    """
    try:
        response = send_command(host, port, "start")
    except OSError as exc:
        raise PretestError(f"Could not reach MMS at {host}:{port}: {exc}") from exc
    if response is None:
        rcon.print("[yellow]MMS gave no reply to the pretest; watching its status[/yellow]")
        return
    if response.return_code != ReturnCode.OK:
        name = ReturnCode.describe(response.return_code)
        raise PretestError(
            f"MMS rejected the pretest: {name} (code {response.return_code})\n\n"
            "Check the MMS Safety indicator. Safe Mode needs a Self-Test."
        )
    rcon.print("[green]MMS pretest sent ok[/green]")


def wait_for_pretest(
    host: str,
    port: int,
    *,
    on_tick: Callable[[], None],
    on_progress: Callable[[float], None],
    clock: Callable[[], float] = time.monotonic,
) -> float:
    """Poll STATUS until the pretest is done; return how long it took.

    Done means a test state of IDLE or READY at least PRETEST_MIN_WAIT_S after
    the pretest was sent. *on_tick* runs every loop (draw a frame, check the
    quit key) and *on_progress* gets the elapsed seconds after each poll.
    Raises PretestTimeout after PRETEST_TIMEOUT_S; the caller sends the ABORT.
    """
    started = clock()
    last_poll = None
    state = None
    while True:
        on_tick()
        now = clock()
        elapsed = now - started
        if last_poll is None or now - last_poll >= config.PRETEST_POLL_S:
            last_poll = now
            try:
                status = send_command(host, port, "status")
            except OSError:
                status = None  # one dropped poll; keep trying until the timeout
            state = None if status is None else status.test_state
            if elapsed >= config.PRETEST_MIN_WAIT_S and state in (
                TestState.IDLE,
                TestState.READY,
            ):
                return elapsed
            on_progress(elapsed)
        if elapsed >= config.PRETEST_TIMEOUT_S:
            raise PretestTimeout(
                f"Pretest did not finish within {config.PRETEST_TIMEOUT_S:.0f} s "
                f"(MMS test state: {_state_name(state)}).\n\n"
                "Check MMS. PsychoPy sent ABORT."
            )


def _state_name(state: int | None) -> str:
    if state is None:
        return "no reply"
    try:
        return TestState(state).name
    except ValueError:
        return f"UNKNOWN({state})"


def print_pretest_prompt(rcon: Console) -> None:
    key = config.PRETEST_KEYS[0].upper()
    rcon.print(
        Panel(
            f"Press [bold]{key}[/bold] in the PsychoPy window to start the pretest.\n"
            "MMS brings the thermode to baseline. The terminal shows when it is done.",
            title="[bold cyan]Step 1 of 2: Pretest[/bold cyan]",
            border_style="cyan",
            expand=False,
            padding=(1, 2),
        )
    )


def print_start_prompt(rcon: Console) -> None:
    key = config.START_KEYS[0]
    rcon.print(
        Panel(
            f"Press [bold]{key}[/bold] in the PsychoPy window to start the run.\n"
            "The run starts as soon as you press it.",
            title="[bold green]Step 2 of 2: Start the Run[/bold green]",
            border_style="green",
            expand=False,
            padding=(1, 2),
        )
    )


def print_pretest_failed(rcon: Console, exc: PretestError) -> None:
    title = "Pretest Timed Out" if isinstance(exc, PretestTimeout) else "Pretest Failed"
    rcon.print(
        Panel(
            f"{exc}\nThe run has not started. Press [bold]Escape[/bold] to quit.",
            title=f"[bold red]{title}[/bold red]",
            border_style="red",
            expand=False,
            padding=(1, 2),
        )
    )


def prompt_setup(rcon: Console) -> None:
    """Walk the operator through arming the MMS, then block until they confirm."""
    rcon.print(
        Panel(
            "[bold]1.[/bold] In MMS, click [bold]Go to Test[/bold]\n"
            "[bold]2.[/bold] Confirm the status reads "
            "[italic]'External Control: TSA 2 is waiting for Test Program'[/italic]\n"
            "[bold]3.[/bold] Press [bold]Enter[/bold] here to continue\n\n"
            "After this, don't click anything in MMS. PsychoPy sends Pre-test and Start\n"
            "for you, and the mouse is locked to the task window once it opens.",
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
