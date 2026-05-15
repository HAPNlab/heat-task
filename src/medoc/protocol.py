"""Pure encode/decode functions for the Medoc MMS wire protocol.

Wire format (little-endian):
  Command frame: [uint32 length] [uint32 timestamp] [uint8 command] [uint32 parameter, optional]
  Where length = byte count of everything after the length field.

  Response frame:  [uint32 length] [uint32 timestamp] [uint8 command]
                   [uint8 system_state] [uint8 test_state] [uint16 return_code]
                   [uint32 test_time] [int16 temperature×100]
                   [uint8 covas] [uint8 yes] [uint8 no] [uint8 ttl]
                   [optional error string]

No I/O — only struct.pack / struct.unpack. Fully testable with byte literals.
"""

from __future__ import annotations

import struct
import time as _time

from medoc.models import Command, MedocResponse

# Little-endian: uint32 uint32 uint8 uint8 uint8 uint16 uint32 int16 uint8 uint8 uint8 uint8
RESPONSE_FORMAT = "<IIBBBHIhBBBB"
RESPONSE_HEADER_SIZE = struct.calcsize(RESPONSE_FORMAT)  # 23 bytes

_PARAMETRIC_COMMANDS = {Command.SELECT_TEST, Command.T_UP, Command.T_DOWN}


def encode_command(command: Command, parameter: int | None = None) -> bytes:
    """Encode a command into wire bytes to send to the MMS.

    Frame: [4B length LE] [4B unix timestamp LE] [1B command] [4B parameter LE, optional]

    Parameters are required for SELECT_TEST, T_UP, and T_DOWN.
    """
    if command in _PARAMETRIC_COMMANDS and parameter is None:
        raise ValueError(f"{command.name} requires a parameter")

    timestamp = int(_time.time())
    body = struct.pack("<I", timestamp) + bytes([int(command)])

    if command in _PARAMETRIC_COMMANDS:
        body += struct.pack("<I", parameter)  # type: ignore[arg-type]

    return struct.pack("<I", len(body)) + body


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
