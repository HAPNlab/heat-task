"""Typer CLI for Medoc MMS external control."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from medoc.ats_parser import parse_ats
from medoc.client import MedocClient
from medoc.models import Command, MedocResponse, ReturnCode, SystemState, TestState
from medoc.runner import ExperimentRunner
from medoc.transport import MedocTransport

app = typer.Typer(name="medoc", help="Medoc MMS external control CLI.")
console = Console()

HOST_OPT = Annotated[str, typer.Option("--host", "-h", help="MMS host IP")]
PORT_OPT = Annotated[int, typer.Option("--port", "-p", help="MMS TCP port")]


def _make_client(host: str, port: int) -> MedocClient:
    transport = MedocTransport(host, port)
    transport.connect()
    return MedocClient(transport)


def _enum_name(enum_cls: type, value: int) -> str:
    try:
        return enum_cls(value).name
    except ValueError:
        return f"UNKNOWN({value})"


def _print_response(resp: MedocResponse | None) -> None:
    if resp is None:
        console.print("[yellow]No response (timeout)[/yellow]")
        return

    table = Table(title="MMS Response", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Command", _enum_name(Command, resp.command))
    table.add_row("System State", _enum_name(SystemState, resp.system_state))
    table.add_row("Test State", _enum_name(TestState, resp.test_state))
    table.add_row("Return Code", _enum_name(ReturnCode, resp.return_code))
    table.add_row("Temperature", f"{resp.temperature:.2f} °C")
    table.add_row("Test Time", str(resp.test_time))
    table.add_row("COVAS", str(resp.covas))
    table.add_row("TTL", str(resp.ttl))
    if resp.message:
        table.add_row("Message", resp.message)
    console.print(table)


@app.command()
def status(
    host: HOST_OPT = "172.16.56.128",
    port: PORT_OPT = MedocTransport.DEFAULT_PORT,
) -> None:
    """Query current MMS status."""
    with _make_client(host, port) as mc:
        _print_response(mc.status())


@app.command()
def send(
    command: Annotated[str, typer.Argument(help="Command name (e.g. START, STOP, TRIGGER)")],
    parameter: Annotated[int | None, typer.Argument(help="Optional parameter")] = None,
    host: HOST_OPT = "172.16.56.128",
    port: PORT_OPT = MedocTransport.DEFAULT_PORT,
) -> None:
    """Send an arbitrary command to the MMS."""
    try:
        cmd = Command[command.upper()]
    except KeyError:
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print(f"Valid commands: {', '.join(c.name for c in Command)}")
        raise typer.Exit(1) from None
    with _make_client(host, port) as mc:
        _print_response(mc.send_command(cmd, parameter))


def _parse_program_id(value: str) -> int:
    try:
        result = int(value, 2)
    except ValueError:
        raise typer.BadParameter(f"'{value}' is not a valid 8-bit binary string (e.g. 00001111)")
    if not (0 <= result <= 255):
        raise typer.BadParameter("Program ID must fit in 8 bits (00000000–11111111)")
    return result


@app.command()
def run(
    program: Annotated[str, typer.Argument(help="Program ID as 8-bit binary string (e.g. 00001111)", parser=_parse_program_id)],
    host: HOST_OPT = "172.16.56.128",
    port: PORT_OPT = MedocTransport.DEFAULT_PORT,
    poll_hz: Annotated[float, typer.Option(help="Status poll frequency")] = 2.0,
    duration: Annotated[float, typer.Option(help="Max run duration in seconds")] = 60.0,
    auto_start: Annotated[bool, typer.Option(help="Send START after SELECT_TEST")] = True,
) -> None:
    """Select a test program, start it, and poll status."""
    with _make_client(host, port) as mc:
        console.print(f"Selecting program {program:08b} ({program})...")
        select_resp = mc.select_test(program)
        _print_response(select_resp)

        if auto_start and select_resp is None:
            console.print("[red]SELECT_TEST got no response — aborting start[/red]")
            return

        if auto_start:
            console.print("Starting...")
            _print_response(mc.start())

        interval = 1.0 / max(poll_hz, 0.1)
        deadline = time.monotonic() + duration
        try:
            while time.monotonic() < deadline:
                resp = mc.status()
                if resp is not None:
                    console.print(
                        f"[dim]{resp.temperature:.2f}°C  "
                        f"sys={_enum_name(SystemState, resp.system_state)}  "
                        f"test={_enum_name(TestState, resp.test_state)}[/dim]"
                    )
                time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
        finally:
            console.print("Stopping...")
            _print_response(mc.stop())


@app.command("run-ats")
def run_ats(
    ats_file: Annotated[Path, typer.Argument(help="Path to the .ats experiment file")],
    start_id: Annotated[int, typer.Option(help="MMS program ID for the first experiment program")] = 0,
    host: HOST_OPT = "172.16.56.128",
    port: PORT_OPT = MedocTransport.DEFAULT_PORT,
    poll_hz: Annotated[float, typer.Option(help="Status poll frequency (Hz)")] = 2.0,
    timeout: Annotated[float, typer.Option(help="Max seconds per program")] = 3600.0,
    inter_delay: Annotated[float, typer.Option(help="Seconds between programs")] = 1.0,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Parse a .ats experiment file and run each program through MMS in order."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        experiment = parse_ats(ats_file)
    except (ValueError, OSError) as e:
        console.print(f"[red]Failed to parse {ats_file}: {e}[/red]")
        raise typer.Exit(1) from None

    table = Table(title=f"Experiment: {ats_file.name}", show_lines=True)
    table.add_column("#", style="dim")
    table.add_column("Program")
    table.add_column("Sequences")
    table.add_column("MMS ID")
    for i, prog in enumerate(experiment.programs):
        table.add_row(str(i + 1), prog.name, str(len(prog.sequences)), str(start_id + i))
    console.print(table)

    typer.confirm(f"Run {len(experiment.programs)} programs starting at MMS ID {start_id}?", abort=True)

    with _make_client(host, port) as mc:
        runner = ExperimentRunner(mc, experiment)
        try:
            runner.run(
                start_program_id=start_id,
                poll_hz=poll_hz,
                program_timeout=timeout,
                inter_program_delay=inter_delay,
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted — sending stop[/yellow]")
            mc.stop()

    console.print("[green]Experiment complete.[/green]")


@app.command("show-ats")
def show_ats(
    ats_file: Annotated[Path, typer.Argument(help="Path to the .ats experiment file")],
) -> None:
    """Show the programs and sequences in a .ats file without running them."""
    try:
        experiment = parse_ats(ats_file)
    except (ValueError, OSError) as e:
        console.print(f"[red]Failed to parse {ats_file}: {e}[/red]")
        raise typer.Exit(1) from None

    for i, prog in enumerate(experiment.programs):
        console.print(f"\n[bold]{i + 1}. {prog.name}[/bold] ({len(prog.sequences)} sequences)")
        seq_table = Table(show_header=True, show_lines=False)
        seq_table.add_column("Seq", style="dim")
        seq_table.add_column("Baseline")
        seq_table.add_column("Destination")
        seq_table.add_column("Rate (°C/s)")
        seq_table.add_column("Duration")
        seq_table.add_column("Trials")
        for s in prog.sequences:
            seq_table.add_row(
                str(s.number),
                f"{s.baseline_temp:.1f}°C",
                f"{s.destination_temp:.1f}°C",
                f"{s.destination_rate:.1f}",
                f"{s.duration_ms / 1000:.1f}s",
                str(s.trials),
            )
        console.print(seq_table)


if __name__ == "__main__":
    app()
