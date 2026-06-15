"""Tests for MedocClient with mocked transport."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

from heat_task.medoc.client import MedocClient
from heat_task.medoc.protocol import RESPONSE_FORMAT, RESPONSE_HEADER_SIZE

_FIXED_TS = 1_000_000


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


def _frame(command: int, param: int | None = None) -> bytes:
    body = struct.pack("<I", _FIXED_TS) + bytes([command])
    if param is not None:
        body += struct.pack("<I", param)
    return struct.pack("<I", len(body)) + body


class TestMedocClient:
    def test_status_sends_correct_bytes(self):
        transport = _mock_transport(_make_response_bytes(command=0))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            resp = client.status()
        transport.send.assert_called_once_with(_frame(0))
        assert resp is not None
        assert resp.command == 0

    def test_select_test(self):
        transport = _mock_transport(_make_response_bytes(command=1))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            resp = client.select_test(15)
        transport.send.assert_called_once_with(_frame(1, 15))
        assert resp is not None

    def test_start(self):
        transport = _mock_transport(_make_response_bytes(command=2))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.start()
        transport.send.assert_called_once_with(_frame(2))

    def test_stop(self):
        transport = _mock_transport(_make_response_bytes(command=5))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.stop()
        transport.send.assert_called_once_with(_frame(5))

    def test_abort(self):
        transport = _mock_transport(_make_response_bytes(command=6))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.abort()
        transport.send.assert_called_once_with(_frame(6))

    def test_t_up(self):
        transport = _mock_transport(_make_response_bytes(command=12))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.t_up(1.5)  # 150 on wire
        transport.send.assert_called_once_with(_frame(12, 150))

    def test_t_down(self):
        transport = _mock_transport(_make_response_bytes(command=13))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.t_down(2.0)  # 200 on wire
        transport.send.assert_called_once_with(_frame(13, 200))

    def test_key_up(self):
        transport = _mock_transport(_make_response_bytes(command=14))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.key_up()
        transport.send.assert_called_once_with(_frame(14))

    def test_timeout_returns_none(self):
        transport = _mock_transport(b"")
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
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
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.trigger()
        transport.send.assert_called_once_with(_frame(4))

    def test_yes_no(self):
        transport = _mock_transport(_make_response_bytes(command=7))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.yes()
        transport.send.assert_called_once_with(_frame(7))

        transport = _mock_transport(_make_response_bytes(command=8))
        client = MedocClient(transport)
        with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
            client.no()
        transport.send.assert_called_once_with(_frame(8))

    def test_covas_vas_specify_next(self):
        for cmd_method, cmd_code in [("covas", 9), ("vas", 10), ("specify_next", 11)]:
            transport = _mock_transport(_make_response_bytes(command=cmd_code))
            client = MedocClient(transport)
            with patch("heat_task.medoc.protocol._time.time", return_value=float(_FIXED_TS)):
                getattr(client, cmd_method)()
            transport.send.assert_called_once_with(_frame(cmd_code))
