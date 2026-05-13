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
    YES = 7
    NO = 8
    INCREASE_TEMP = 9
    DECREASE_TEMP = 10
    KEY_UP = 11
    NEXT_SEQUENCE = 12


class SystemState(IntEnum):
    IDLE = 0
    READY = 1
    RUNNING = 2
    PAUSED = 3
    FINISHED = 4
    ERROR = 5


class TestState(IntEnum):
    IDLE = 0
    RUNNING = 1
    PAUSED = 2
    FINISHED = 3
    STOPPED = 4


class ReturnCode(IntEnum):
    OK = 0
    ILLEGAL_COMMAND = 1
    ILLEGAL_PARAMETER = 2
    SYSTEM_ERROR = 3


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
