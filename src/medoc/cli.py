"""Typer CLI for Medoc TSA2 direct serial control."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from medoc.ats_parser import parse_ats
from medoc.runner import ExperimentRunner
from medoc.serial import MockTsaDevice, TsaDevice

app = typer.Typer(name="medoc", help="Medoc TSA2 direct serial control CLI.")
console = Console()

PORT_OPT = Annotated[
    str | None,
    typer.Option("--port", "-p", help="Serial port (e.g. /dev/tty.usbserial-0001 or COM3). Auto-detected if omitted."),
]
MOCK_OPT = Annotated[bool, typer.Option("--mock", help="Use MockTsaDevice (no hardware required)")]


def _make_device(port: str | None, mock: bool):
    if mock:
        console.print("[yellow]Using MockTsaDevice — no hardware[/yellow]")
        return MockTsaDevice()
    prefs = "preferences.json" if Path("preferences.json").exists() else None
    if port:
        import serial as _serial
        from medoc.serial import enums as _enums
        from medoc.serial.connector import connector as _connector
        from medoc.serial.event import Event, TypedEvent
        from medoc.serial.token_holder import TokenHolder
        import time as _time

        ser = _serial.Serial(port, baudrate=9600, timeout=0.5, write_timeout=0.5)
        dev = TsaDevice.__new__(TsaDevice)
        dev.current_thermode = _enums.DEVICE_TAG.Master
        dev.token_holder = TokenHolder()
        dev.busy = False
        dev.last_safety_level = 0.0
        dev.safety_start_time = _time.time()
        dev.status_state = None
        dev.status_temp = 0.0
        dev.status_thread = None
        dev.status_thread_stop = False
        dev.event_status_updated = Event()
        dev.event_patient_response = TypedEvent(bool, bool)
        dev.event_status_updated.connect(dev._on_get_status_event)
        conn = object.__new__(_connector)
        conn.tunnel = ser
        dev.connector = conn
        return dev
    return TsaDevice(auto_connect_port=True, preferences_path=prefs or "preferences.json")


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


@app.command("run-ats")
def run_ats(
    ats_file: Annotated[Path, typer.Argument(help="Path to the .ats experiment file")],
    port: PORT_OPT = None,
    mock: MOCK_OPT = False,
    poll_hz: Annotated[float, typer.Option(help="Status poll frequency (Hz)")] = 2.0,
    timeout: Annotated[float, typer.Option(help="Max seconds per program")] = 3600.0,
    margin: Annotated[float, typer.Option(help="Temperature margin (°C) for ramp commands")] = 0.5,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    program: Annotated[
        int | None,
        typer.Option(
            "--program", "-n",
            help="1-based index of the program to run. Omit to choose interactively.",
        ),
    ] = None,
) -> None:
    """Parse a .ats experiment file and run a single program through the TSA2."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        experiment = parse_ats(ats_file)
    except (ValueError, OSError) as e:
        console.print(f"[red]Failed to parse {ats_file}: {e}[/red]")
        raise typer.Exit(1) from None

    summary = Table(title=f"Experiment: {ats_file.name}", show_lines=True)
    summary.add_column("#", style="dim")
    summary.add_column("Program")
    summary.add_column("Sequences")
    for i, prog in enumerate(experiment.programs):
        summary.add_row(str(i + 1), prog.name, str(len(prog.sequences)))
    console.print(summary)

    n = len(experiment.programs)

    if program is not None:
        if not 1 <= program <= n:
            console.print(f"[red]Program index {program} out of range (1–{n})[/red]")
            raise typer.Exit(1)
        selected_index = program - 1
    else:
        raw = typer.prompt(f"Program to run (1–{n})")
        try:
            chosen = int(raw.strip())
        except ValueError:
            console.print("[red]Invalid input — enter a single number[/red]")
            raise typer.Exit(1) from None
        if not 1 <= chosen <= n:
            console.print(f"[red]Program index {chosen} out of range (1–{n})[/red]")
            raise typer.Exit(1)
        selected_index = chosen - 1

    selected_name = experiment.programs[selected_index].name
    typer.confirm(f"Run program: {selected_name}?", abort=True)

    device = _make_device(port, mock)
    device.start_status_thread()
    runner = ExperimentRunner(device, experiment)
    try:
        runner.run(
            poll_hz=poll_hz,
            program_timeout=timeout,
            margin=margin,
            program_index=selected_index,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted — stopping[/yellow]")
        device.stop_test()
    finally:
        device.finalize()

    console.print("[green]Experiment complete.[/green]")


if __name__ == "__main__":
    app()
