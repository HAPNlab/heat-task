"""One-off MMS command helpers used to drive the run (select/start) and to
assert that the thermode accepted each command."""

from __future__ import annotations

from rich.console import Console

from heat_task import config
from heat_task.medoc.client import MedocClient
from heat_task.medoc.models import MedocResponse, ReturnCode


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
