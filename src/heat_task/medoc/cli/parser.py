"""Argument parser for the medoc CLI."""

from __future__ import annotations

import argparse

from heat_task.medoc.cli.commands import monitor_status, run_program
from heat_task.medoc.transport import MedocTransport


def _program_word(value: str) -> int:
    if len(value) != 8 or any(bit not in "01" for bit in value):
        raise argparse.ArgumentTypeError("program word must be exactly 8 bits, e.g. 00001111")
    return int(value, 2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medoc", description="Control Medoc MMS over TCP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_connection_args(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("host", help="MMS host or IP address")
        command_parser.add_argument(
            "--port",
            type=int,
            default=MedocTransport.DEFAULT_PORT,
            help=f"MMS TCP port (default: {MedocTransport.DEFAULT_PORT})",
        )
        command_parser.add_argument(
            "--poll-interval",
            type=float,
            default=1.0,
            help="seconds between status requests (default: 1.0)",
        )
        command_parser.add_argument(
            "--connect-timeout",
            type=float,
            default=5.0,
            help="socket connect timeout in seconds (default: 5.0)",
        )
        command_parser.add_argument(
            "--recv-timeout",
            type=float,
            default=5.0,
            help="socket receive timeout in seconds (default: 5.0)",
        )

    monitor_parser = subparsers.add_parser("monitor", help="monitor MMS status only")
    add_connection_args(monitor_parser)
    monitor_parser.add_argument(
        "program_id",
        type=int,
        nargs="?",
        help="optional MMS program/test ID to select before monitoring",
    )
    monitor_parser.add_argument(
        "--program-word",
        type=_program_word,
        help="optional 8-bit MMS program word to select before monitoring, e.g. 00001111",
    )
    monitor_parser.add_argument(
        "--select-delay",
        type=float,
        default=0.5,
        help="seconds to wait after selecting a program (default: 0.5)",
    )
    monitor_parser.add_argument(
        "--count",
        type=int,
        help="stop after this many status responses",
    )
    monitor_parser.add_argument(
        "--strict-responses",
        action="store_true",
        help="fail if select does not return an immediate response",
    )
    monitor_parser.set_defaults(func=monitor_status)

    run_parser = subparsers.add_parser("run", help="select, start, and monitor a program")
    add_connection_args(run_parser)
    run_parser.add_argument("program_id", type=int, nargs="?", help="MMS program/test ID to run")
    run_parser.add_argument(
        "--program-word",
        type=_program_word,
        help="8-bit MMS program word to run, e.g. 00001111",
    )
    run_parser.add_argument(
        "--select-delay",
        type=float,
        default=0.5,
        help="seconds to wait between select and pretest/start (default: 0.5)",
    )
    run_parser.add_argument(
        "--pretest-delay",
        type=float,
        default=1.0,
        help="seconds to wait between pretest START and run START (default: 1.0)",
    )
    run_parser.add_argument(
        "--wait-for-pretest",
        action="store_true",
        help="poll until pretest returns to idle/ready before sending run START",
    )
    run_parser.add_argument(
        "--pretest-timeout",
        type=float,
        default=120.0,
        help="maximum seconds for --wait-for-pretest (default: 120.0)",
    )
    run_parser.add_argument(
        "--no-pretest",
        action="store_false",
        dest="pretest",
        help="skip the initial START command used by MMS as pretest",
    )
    run_parser.add_argument(
        "--strict-responses",
        action="store_true",
        help="fail if select/pretest/start do not return an immediate response",
    )
    run_parser.set_defaults(func=run_program)

    return parser
