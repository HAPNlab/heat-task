"""Terminal output helpers for the medoc CLI: response formatting and the
return-code checks shared by the commands."""

from __future__ import annotations

import sys
import time
from enum import IntEnum
from typing import TextIO

from heat_task.medoc.models import MedocResponse, ReturnCode, SystemState, TestState


def write_line(message: str, *, file: TextIO | None = None) -> None:
    stream = sys.stdout if file is None else file
    stream.write(f"\r{message}\r\n")
    stream.flush()


def enum_name(enum_type: type[IntEnum], value: int) -> str:
    try:
        return enum_type(value).name
    except ValueError:
        return str(value)


def format_response(response: MedocResponse) -> str:
    system_state = enum_name(SystemState, response.system_state)
    test_state = enum_name(TestState, response.test_state)
    return_code = enum_name(ReturnCode, response.return_code)

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


def print_response(label: str, response: MedocResponse) -> None:
    timestamp = time.strftime("%H:%M:%S")
    write_line(f"{timestamp} {label}: {format_response(response)}")


def require_ok(label: str, response: MedocResponse | None) -> bool:
    if response is None:
        write_line(f"{label}: no response from MMS", file=sys.stderr)
        return False

    print_response(label, response)
    if response.return_code != int(ReturnCode.OK):
        write_line(
            f"{label}: MMS returned {enum_name(ReturnCode, response.return_code)}", file=sys.stderr
        )
        return False
    return True


def accept_command_response(label: str, response: MedocResponse | None, *, strict: bool) -> bool:
    if response is None:
        message = f"{label}: no immediate response from MMS"
        if strict:
            write_line(message, file=sys.stderr)
            return False
        write_line(f"{message}; continuing")
        return True

    return require_ok(label, response)
