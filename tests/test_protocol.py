"""Unit tests for encode/decode with hardcoded byte arrays."""

from __future__ import annotations

import struct
from unittest.mock import patch

import pytest

from heat_task.medoc.models import Command
from heat_task.medoc.protocol import RESPONSE_FORMAT, RESPONSE_HEADER_SIZE, decode_response, encode_command

_FIXED_TS = 1_000_000


def _frame(command: int, param: int | None = None) -> bytes:
    """Build the expected wire frame for a command at _FIXED_TS."""
    body = struct.pack("<I", _FIXED_TS) + bytes([command])
    if param is not None:
        body += struct.pack("<I", param)
    return struct.pack("<I", len(body)) + body


class TestEncodeCommand:
    def _encode(self, command: Command, parameter: int | None = None) -> bytes:
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            return encode_command(command, parameter)

    def test_status(self):
        assert self._encode(Command.STATUS) == _frame(0)

    def test_start(self):
        assert self._encode(Command.START) == _frame(2)

    def test_pause(self):
        assert self._encode(Command.PAUSE) == _frame(3)

    def test_trigger(self):
        assert self._encode(Command.TRIGGER) == _frame(4)

    def test_stop(self):
        assert self._encode(Command.STOP) == _frame(5)

    def test_abort(self):
        assert self._encode(Command.ABORT) == _frame(6)

    def test_yes_no(self):
        assert self._encode(Command.YES) == _frame(7)
        assert self._encode(Command.NO) == _frame(8)

    def test_covas_vas_specify_next_key_up(self):
        assert self._encode(Command.COVAS) == _frame(9)
        assert self._encode(Command.VAS) == _frame(10)
        assert self._encode(Command.SPECIFY_NEXT) == _frame(11)
        assert self._encode(Command.KEY_UP) == _frame(14)

    def test_select_test(self):
        assert self._encode(Command.SELECT_TEST, 15) == _frame(1, 15)

    def test_select_test_requires_parameter(self):
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            with pytest.raises(ValueError, match="SELECT_TEST requires"):
                encode_command(Command.SELECT_TEST)

    def test_t_up(self):
        # 500 raw units → 5.00°C via client, but protocol receives raw int
        assert self._encode(Command.T_UP, 500) == _frame(12, 500)

    def test_t_down(self):
        assert self._encode(Command.T_DOWN, 1000) == _frame(13, 1000)

    def test_t_up_requires_parameter(self):
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            with pytest.raises(ValueError, match="T_UP requires"):
                encode_command(Command.T_UP)

    def test_frame_length_field_no_param(self):
        data = self._encode(Command.STATUS)
        length = struct.unpack("<I", data[:4])[0]
        assert length == len(data) - 4  # 4 (timestamp) + 1 (command) = 5

    def test_frame_length_field_with_param(self):
        data = self._encode(Command.SELECT_TEST, 1)
        length = struct.unpack("<I", data[:4])[0]
        assert length == len(data) - 4  # 4 (timestamp) + 1 (command) + 4 (param) = 9

    def test_timestamp_embedded_in_frame(self):
        data = self._encode(Command.STATUS)
        ts = struct.unpack("<I", data[4:8])[0]
        assert ts == _FIXED_TS

    def test_command_byte_at_correct_offset(self):
        data = self._encode(Command.START)
        assert data[8] == int(Command.START)


class TestDecodeResponse:
    def _make_response_bytes(self, **overrides) -> bytes:
        defaults = {
            "response_length": RESPONSE_HEADER_SIZE,
            "timestamp": 1000,
            "command": 0,
            "system_state": 1,
            "test_state": 0,
            "return_code": 0,
            "test_time": 5000,
            "raw_temperature": 3200,  # 32.00°C
            "covas": 0,
            "yes": 0,
            "no": 0,
            "ttl": 0,
        }
        defaults.update(overrides)
        return struct.pack(
            RESPONSE_FORMAT,
            defaults["response_length"],
            defaults["timestamp"],
            defaults["command"],
            defaults["system_state"],
            defaults["test_state"],
            defaults["return_code"],
            defaults["test_time"],
            defaults["raw_temperature"],
            defaults["covas"],
            defaults["yes"],
            defaults["no"],
            defaults["ttl"],
        )

    def test_basic_decode(self):
        data = self._make_response_bytes()
        resp = decode_response(data)
        assert resp.timestamp == 1000
        assert resp.command == 0
        assert resp.system_state == 1
        assert resp.test_state == 0
        assert resp.return_code == 0
        assert resp.test_time == 5000
        assert resp.raw_temperature == 3200
        assert resp.temperature == 32.0
        assert resp.message == ""

    def test_temperature_negative(self):
        data = self._make_response_bytes(raw_temperature=-500)
        resp = decode_response(data)
        assert resp.temperature == -5.0

    def test_with_message(self):
        header = self._make_response_bytes()
        message = b"Hello MMS\x00"
        resp = decode_response(header + message)
        assert resp.message == "Hello MMS"

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_response(b"\x00" * 10)

    def test_roundtrip_header_size(self):
        assert RESPONSE_HEADER_SIZE == 23

    def test_frozen(self):
        data = self._make_response_bytes()
        resp = decode_response(data)
        with pytest.raises(AttributeError):
            resp.timestamp = 999  # type: ignore[misc]

    def test_unknown_enum_values_preserved(self):
        data = self._make_response_bytes(system_state=99, test_state=88, return_code=77)
        resp = decode_response(data)
        assert resp.system_state == 99
        assert resp.test_state == 88
        assert resp.return_code == 77
