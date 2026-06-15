"""Command line interface for Medoc MMS external control."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from collections.abc import Sequence
from enum import IntEnum
from typing import TextIO

from heat_task.medoc.client import MedocClient
from heat_task.medoc.models import MedocResponse, ReturnCode, SystemState, TestState
from heat_task.medoc.transport import MedocTransport

CommandCall = str | tuple[str, int]


def _write_line(message: str, *, file: TextIO | None = None) -> None:
    stream = sys.stdout if file is None else file
    stream.write(f"\r{message}\r\n")
    stream.flush()


def _enum_name(enum_type: type[IntEnum], value: int) -> str:
    try:
        return enum_type(value).name
    except ValueError:
        return str(value)


def _format_response(response: MedocResponse) -> str:
    system_state = _enum_name(SystemState, response.system_state)
    test_state = _enum_name(TestState, response.test_state)
    return_code = _enum_name(ReturnCode, response.return_code)

    parts = [
        f"system={system_state}",
        f"test={test_state}",
        f"return={return_code}",
        f"time={response.test_time}ms",
        f"temp={response.temperature:.2f}C",
        f"covas={response.covas}",
        f"yes={response.yes}",
        f"no={response.no}",
        f"ttl={response.ttl}",
    ]
    if response.message:
        parts.append(f"message={response.message!r}")
    return " ".join(parts)


def _print_response(label: str, response: MedocResponse) -> None:
    timestamp = time.strftime("%H:%M:%S")
    _write_line(f"{timestamp} {label}: {_format_response(response)}")


def _require_ok(label: str, response: MedocResponse | None) -> bool:
    if response is None:
        _write_line(f"{label}: no response from MMS", file=sys.stderr)
        return False

    _print_response(label, response)
    if response.return_code != int(ReturnCode.OK):
        _write_line(
            f"{label}: MMS returned {_enum_name(ReturnCode, response.return_code)}", file=sys.stderr
        )
        return False
    return True


def _accept_command_response(label: str, response: MedocResponse | None, *, strict: bool) -> bool:
    if response is None:
        message = f"{label}: no immediate response from MMS"
        if strict:
            _write_line(message, file=sys.stderr)
            return False
        _write_line(f"{message}; continuing")
        return True

    return _require_ok(label, response)


def _program_word(value: str) -> int:
    if len(value) != 8 or any(bit not in "01" for bit in value):
        raise argparse.ArgumentTypeError("program word must be exactly 8 bits, e.g. 00001111")
    return int(value, 2)


def _selected_program_id(args: argparse.Namespace, *, required: bool) -> int | None:
    if args.program_id is not None and args.program_word is not None:
        raise ValueError("use either program_id or --program-word, not both")
    program_id = args.program_word if args.program_word is not None else args.program_id
    if required and program_id is None:
        raise ValueError("program_id or --program-word is required")
    return program_id


def _connect(args: argparse.Namespace) -> MedocClient:
    return MedocClient.connect(
        args.host,
        args.port,
        connect_timeout=args.connect_timeout,
        recv_timeout=args.recv_timeout,
    )


def _send(args: argparse.Namespace, call: CommandCall) -> MedocResponse | None:
    with _connect(args) as client:
        if isinstance(call, tuple):
            method_name, parameter = call
            return getattr(client, method_name)(parameter)
        return getattr(client, call)()


def _wait_for_pretest(args: argparse.Namespace) -> int:
    _write_line("waiting for pretest to finish; press Ctrl-C to abort")
    deadline = time.monotonic() + args.pretest_timeout

    while True:
        response = _send(args, "status")
        if response is None:
            _write_line("pretest status: no response from MMS", file=sys.stderr)
            return 1

        _print_response("pretest status", response)
        if response.test_state in (int(TestState.IDLE), int(TestState.READY)):
            return 0

        if time.monotonic() >= deadline:
            _write_line(
                f"pretest did not finish within {args.pretest_timeout:.1f}s", file=sys.stderr
            )
            return 1

        time.sleep(args.poll_interval)


def run_program(args: argparse.Namespace) -> int:
    started = False
    signal.signal(signal.SIGINT, signal.default_int_handler)
    program_id = _selected_program_id(args, required=True)

    if not _accept_command_response(
        "select", _send(args, ("select_test", program_id)), strict=args.strict_responses
    ):
        return 1
    time.sleep(args.select_delay)

    if args.pretest:
        if not _accept_command_response(
            "pretest", _send(args, "start"), strict=args.strict_responses
        ):
            return 1
        time.sleep(args.pretest_delay)
        if args.wait_for_pretest:
            pretest_exit_code = _wait_for_pretest(args)
            if pretest_exit_code != 0:
                return pretest_exit_code

    if not _accept_command_response("start", _send(args, "start"), strict=args.strict_responses):
        return 1

    _write_line("monitoring status; press Ctrl-C to abort")
    try:
        while True:
            response = _send(args, "status")
            if response is None:
                _write_line("status: no response from MMS", file=sys.stderr)
                return 1

            _print_response("status", response)

            if response.test_state in (int(TestState.RUNNING), int(TestState.PAUSED)):
                started = True
            elif started and response.test_state in (int(TestState.IDLE), int(TestState.READY)):
                _write_line("program finished")
                return 0

            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        _write_line("interrupted; aborting program", file=sys.stderr)
        response = _send(args, "abort")
        if response is not None:
            _print_response("abort", response)
        return 130


def monitor_status(args: argparse.Namespace) -> int:
    program_id = _selected_program_id(args, required=False)
    if program_id is not None:
        if not _accept_command_response(
            "select", _send(args, ("select_test", program_id)), strict=args.strict_responses
        ):
            return 1
        time.sleep(args.select_delay)

    _write_line("monitoring status; press Ctrl-C to stop")
    count = 0
    try:
        while True:
            response = _send(args, "status")
            if response is None:
                _write_line("status: no response from MMS", file=sys.stderr)
                return 1

            _print_response("status", response)
            count += 1
            if args.count is not None and count >= args.count:
                return 0
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        _write_line("monitor stopped")
        return 130


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
