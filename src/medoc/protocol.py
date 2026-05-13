"""Pure encode/decode functions for the Medoc MMS wire protocol.

No I/O — only struct.pack / struct.unpack. Fully testable with byte literals.
"""

from __future__ import annotations

import struct

from medoc.models import Command, MedocResponse

# Little-endian: uint32 uint32 uint8 uint8 uint8 uint16 uint32 int16 uint8 uint8 uint8 uint8
RESPONSE_FORMAT = "<IIBBBHIhBBBB"
RESPONSE_HEADER_SIZE = struct.calcsize(RESPONSE_FORMAT)  # 23 bytes


def encode_command(command: Command, parameter: int | None = None) -> bytes:
    """Encode a command into bytes to send to the MMS.

    - Most commands are a single byte.
    - SELECT_TEST appends a program ID byte.
    - INCREASE_TEMP / DECREASE_TEMP append a uint16 LE parameter (degrees × 100).
    """
    buf = bytes([int(command)])

    if command == Command.SELECT_TEST:
        if parameter is None:
            raise ValueError("SELECT_TEST requires a program ID parameter")
        buf += struct.pack("<B", parameter)

    elif command in (Command.INCREASE_TEMP, Command.DECREASE_TEMP):
        if parameter is None:
            raise ValueError(f"{command.name} requires a temperature parameter (degrees × 100)")
        buf += struct.pack("<H", parameter)

    return buf


def decode_response(data: bytes) -> MedocResponse:
    """Decode a raw byte response from the MMS into a MedocResponse."""
    if len(data) < RESPONSE_HEADER_SIZE:
        raise ValueError(
            f"Response too short: got {len(data)} bytes, need at least {RESPONSE_HEADER_SIZE}"
        )

    (
        response_length,
        timestamp,
        command,
        system_state,
        test_state,
        return_code,
        test_time,
        raw_temperature,
        covas,
        yes,
        no_val,
        ttl,
    ) = struct.unpack(RESPONSE_FORMAT, data[:RESPONSE_HEADER_SIZE])

    message = ""
    if len(data) > RESPONSE_HEADER_SIZE:
        message = data[RESPONSE_HEADER_SIZE:].decode("utf-8", errors="replace").rstrip("\x00")

    return MedocResponse(
        response_length=response_length,
        timestamp=timestamp,
        command=command,
        system_state=system_state,
        test_state=test_state,
        return_code=return_code,
        test_time=test_time,
        raw_temperature=raw_temperature,
        covas=covas,
        yes=yes,
        no=no_val,
        ttl=ttl,
        message=message,
    )
