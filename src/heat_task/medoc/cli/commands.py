"""The medoc CLI subcommands: connect/send plumbing plus the ``run`` and
``monitor`` command implementations."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from typing import Literal, overload

from heat_task.medoc.cli.formatting import (
    accept_command_response,
    print_response,
    write_line,
)
from heat_task.medoc.client import MedocClient
from heat_task.medoc.models import MedocResponse, TestState

CommandCall = str | tuple[str, int]


@overload
def selected_program_id(args: argparse.Namespace, *, required: Literal[True]) -> int: ...
@overload
def selected_program_id(args: argparse.Namespace, *, required: Literal[False]) -> int | None: ...
def selected_program_id(args: argparse.Namespace, *, required: bool) -> int | None:
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
    write_line("waiting for pretest to finish; press Ctrl-C to abort")
    deadline = time.monotonic() + args.pretest_timeout

    while True:
        response = _send(args, "status")
        if response is None:
            write_line("pretest status: no response from MMS", file=sys.stderr)
            return 1

        print_response("pretest status", response)
        if response.test_state in (int(TestState.IDLE), int(TestState.READY)):
            return 0

        if time.monotonic() >= deadline:
            write_line(
                f"pretest did not finish within {args.pretest_timeout:.1f}s", file=sys.stderr
            )
            return 1

        time.sleep(args.poll_interval)


def run_program(args: argparse.Namespace) -> int:
    started = False
    signal.signal(signal.SIGINT, signal.default_int_handler)
    program_id = selected_program_id(args, required=True)

    if not accept_command_response(
        "select", _send(args, ("select_test", program_id)), strict=args.strict_responses
    ):
        return 1
    time.sleep(args.select_delay)

    if args.pretest:
        if not accept_command_response(
            "pretest", _send(args, "start"), strict=args.strict_responses
        ):
            return 1
        time.sleep(args.pretest_delay)
        if args.wait_for_pretest:
            pretest_exit_code = _wait_for_pretest(args)
            if pretest_exit_code != 0:
                return pretest_exit_code

    if not accept_command_response("start", _send(args, "start"), strict=args.strict_responses):
        return 1

    write_line("monitoring status; press Ctrl-C to abort")
    try:
        while True:
            response = _send(args, "status")
            if response is None:
                write_line("status: no response from MMS", file=sys.stderr)
                return 1

            print_response("status", response)

            if response.test_state in (int(TestState.RUNNING), int(TestState.PAUSED)):
                started = True
            elif started and response.test_state in (int(TestState.IDLE), int(TestState.READY)):
                write_line("program finished")
                return 0

            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        write_line("interrupted; aborting program", file=sys.stderr)
        response = _send(args, "abort")
        if response is not None:
            print_response("abort", response)
        return 130


def monitor_status(args: argparse.Namespace) -> int:
    program_id = selected_program_id(args, required=False)
    if program_id is not None:
        if not accept_command_response(
            "select", _send(args, ("select_test", program_id)), strict=args.strict_responses
        ):
            return 1
        time.sleep(args.select_delay)

    write_line("monitoring status; press Ctrl-C to stop")
    count = 0
    try:
        while True:
            response = _send(args, "status")
            if response is None:
                write_line("status: no response from MMS", file=sys.stderr)
                return 1

            print_response("status", response)
            count += 1
            if args.count is not None and count >= args.count:
                return 0
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        write_line("monitor stopped")
        return 130
