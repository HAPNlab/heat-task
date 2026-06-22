"""Enums and data models for the Medoc MMS external control protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Command(IntEnum):
    STATUS = 0
    SELECT_TEST = 1
    START = 2
    PAUSE = 3
    TRIGGER = 4
    STOP = 5
    ABORT = 6
    YES = 7
    NO = 8
    COVAS = 9
    VAS = 10
    SPECIFY_NEXT = 11
    T_UP = 12
    T_DOWN = 13
    KEY_UP = 14


class SystemState(IntEnum):
    """Pathway system state (SYSTEM_STATE field in response)."""
    IDLE = 0
    READY = 1
    TEST = 2


class TestState(IntEnum):
    """Pathway test state (TEST_STATE field in response)."""
    IDLE = 0
    RUNNING = 1
    PAUSED = 2
    READY = 3


class ReturnCode(IntEnum):
    """Result code returned by MMS after each command.

    The non-zero codes are bit flags that can combine, so a raw value is decoded
    with :meth:`describe` rather than a plain ``ReturnCode(value)`` lookup.
    """
    OK = 0
    ILLEGAL_ARG = 1
    ILLEGAL_STATE = 2
    ILLEGAL_TEST_STATE = 3
    DEVICE_COMM_ERROR = 4096
    SAFETY_WARNING = 8192
    SAFETY_ERROR = 16384

    @staticmethod
    def describe(code: int) -> str:
        """Decode a bitfield return code into human-readable flag names."""
        flags = [
            member.name
            for member in ReturnCode
            if member is not ReturnCode.OK and code & int(member)
        ]
        return " | ".join(flags) if flags else f"UNKNOWN({code})"


@dataclass(frozen=True, slots=True)
class MedocResponse:
    """Parsed response from the Medoc MMS.

    Raw integer fields are stored for system_state, test_state, and return_code
    to avoid crashes on unknown enum values.
    """

    response_length: int
    timestamp: int
    command: int
    system_state: int
    test_state: int
    return_code: int
    test_time: int
    raw_temperature: int
    covas: int
    yes: int
    no: int
    ttl: int
    message: str = ""

    @property
    def temperature(self) -> float:
        """Temperature in degrees Celsius (wire value is ×100)."""
        return self.raw_temperature / 100.0
