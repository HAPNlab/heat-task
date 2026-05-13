"""Tests for MedocClient with mocked transport."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

from medoc.client import MedocClient
from medoc.protocol import RESPONSE_FORMAT, RESPONSE_HEADER_SIZE


def _make_response_bytes(**overrides) -> bytes:
    defaults = {
        "response_length": RESPONSE_HEADER_SIZE,
        "timestamp": 1000,
        "command": 0,
        "system_state": 1,
        "test_state": 0,
        "return_code": 0,
        "test_time": 0,
        "raw_temperature": 3200,
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


def _mock_transport(response_bytes: bytes = b"") -> MagicMock:
    transport = MagicMock()
    transport.recv.return_value = response_bytes
    return transport


class TestMedocClient:
    def test_status_sends_correct_bytes(self):
        transport = _mock_transport(_make_response_bytes(command=0))
        client = MedocClient(transport)
        resp = client.status()
        transport.send.assert_called_once_with(b"\x00")
        assert resp is not None
        assert resp.command == 0

    def test_select_test(self):
        transport = _mock_transport(_make_response_bytes(command=1))
        client = MedocClient(transport)
        resp = client.select_test(15)
        transport.send.assert_called_once_with(b"\x01\x0f")
        assert resp is not None

    def test_start(self):
        transport = _mock_transport(_make_response_bytes(command=2))
        client = MedocClient(transport)
        client.start()
        transport.send.assert_called_once_with(b"\x02")

    def test_stop(self):
        transport = _mock_transport(_make_response_bytes(command=5))
        client = MedocClient(transport)
        client.stop()
        transport.send.assert_called_once_with(b"\x05")

    def test_increase_temp(self):
        transport = _mock_transport(_make_response_bytes(command=9))
        client = MedocClient(transport)
        client.increase_temp(1.5)  # 150
        expected = b"\x09" + struct.pack("<H", 150)
        transport.send.assert_called_once_with(expected)

    def test_decrease_temp(self):
        transport = _mock_transport(_make_response_bytes(command=10))
        client = MedocClient(transport)
        client.decrease_temp(2.0)  # 200
        expected = b"\x0a" + struct.pack("<H", 200)
        transport.send.assert_called_once_with(expected)

    def test_timeout_returns_none(self):
        transport = _mock_transport(b"")
        client = MedocClient(transport)
        assert client.status() is None

    def test_context_manager(self):
        transport = _mock_transport()
        client = MedocClient(transport)
        with client:
            pass
        transport.close.assert_called_once()

    def test_trigger(self):
        transport = _mock_transport(_make_response_bytes(command=4))
        client = MedocClient(transport)
        client.trigger()
        transport.send.assert_called_once_with(b"\x04")

    def test_yes_no(self):
        transport = _mock_transport(_make_response_bytes(command=7))
        client = MedocClient(transport)
        client.yes()
        transport.send.assert_called_once_with(b"\x07")

        transport = _mock_transport(_make_response_bytes(command=8))
        client = MedocClient(transport)
        client.no()
        transport.send.assert_called_once_with(b"\x08")
