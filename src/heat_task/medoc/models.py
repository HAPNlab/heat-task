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
    ACTIVE = 2


class TestState(IntEnum):
    """Pathway test state (TEST_STATE field in response)."""
    IDLE = 0
    RUNNING = 1
    PAUSED = 2
    READY = 3


class ReturnCode(IntEnum):
    """Result code returned by MMS after each command (TSA 2 manual, Table 46).

    These are plain values, not bit flags: 3 is ILLEGAL_TEST_STATE (not
    ILLEGAL_ARG | ILLEGAL_STATE) and 0x3000 is WAITING_MANUAL_OPERATION (not
    DEVICE_COMM_ERROR | SAFETY_WARNING). Decode a raw value with :meth:`describe`.
    """
    OK = 0x0000
    ILLEGAL_ARG = 0x0001
    ILLEGAL_STATE = 0x0002
    ILLEGAL_TEST_STATE = 0x0003
    DEVICE_COMM_ERROR = 0x1000
    SAFETY_WARNING = 0x2000
    WAITING_MANUAL_OPERATION = 0x3000
    SAFETY_ERROR = 0x4000

    @staticmethod
    def describe(code: int) -> str:
        """Name a raw return code. An unlisted value is split into its device
        (high nibble) and command (low bits) parts in case MMS combines one of
        each; anything else is reported as UNKNOWN."""
        known = {int(member): member.name for member in ReturnCode}
        if code in known:
            return known[code]
        device, command = code & 0xF000, code & 0x0FFF
        if device in known and command in known and device and command:
            return f"{known[device]} | {known[command]}"
        return f"UNKNOWN({code})"


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
