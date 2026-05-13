"""Unit tests for encode/decode with hardcoded byte arrays."""

from __future__ import annotations

import struct

import pytest

from medoc.models import Command
from medoc.protocol import RESPONSE_FORMAT, RESPONSE_HEADER_SIZE, decode_response, encode_command


class TestEncodeCommand:
    def test_status(self):
        assert encode_command(Command.STATUS) == b"\x00"

    def test_start(self):
        assert encode_command(Command.START) == b"\x02"

    def test_stop(self):
        assert encode_command(Command.STOP) == b"\x05"

    def test_trigger(self):
        assert encode_command(Command.TRIGGER) == b"\x04"

    def test_select_test(self):
        assert encode_command(Command.SELECT_TEST, 15) == b"\x01\x0f"

    def test_select_test_requires_parameter(self):
        with pytest.raises(ValueError, match="SELECT_TEST requires"):
            encode_command(Command.SELECT_TEST)

    def test_increase_temp(self):
        # 1.5°C = 150 = 0x0096 little-endian
        result = encode_command(Command.INCREASE_TEMP, 150)
        assert result == b"\x09" + struct.pack("<H", 150)

    def test_decrease_temp(self):
        result = encode_command(Command.DECREASE_TEMP, 200)
        assert result == b"\x0a" + struct.pack("<H", 200)

    def test_increase_temp_requires_parameter(self):
        with pytest.raises(ValueError, match="INCREASE_TEMP requires"):
            encode_command(Command.INCREASE_TEMP)

    def test_yes_no_key_up_next(self):
        assert encode_command(Command.YES) == b"\x07"
        assert encode_command(Command.NO) == b"\x08"
        assert encode_command(Command.KEY_UP) == b"\x0b"
        assert encode_command(Command.NEXT_SEQUENCE) == b"\x0c"


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
