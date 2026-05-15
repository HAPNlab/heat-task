"""TCP socket transport for the Medoc MMS external control interface."""

from __future__ import annotations

import socket
import struct
from types import TracebackType


class MedocTransport:
    """Low-level TCP wrapper for communicating with the Medoc MMS.

    Usage::

        with MedocTransport("192.168.1.100", 20121) as t:
            t.send(payload)
            data = t.recv()
    """

    DEFAULT_PORT = 20121

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        connect_timeout: float = 5.0,
        recv_timeout: float = 2.0,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.recv_timeout = recv_timeout
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.connect_timeout
        )
        self._sock.settimeout(self.recv_timeout)

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def send(self, data: bytes) -> None:
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")
        self._sock.sendall(data)

    def _recv_exactly(self, nbytes: int) -> bytes:
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")
        chunks: list[bytes] = []
        remaining = nbytes
        while remaining > 0:
            chunk = self._sock.recv(remaining)
            if not chunk:
                return b""
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def recv(self) -> bytes:
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")
        try:
            length_bytes = self._recv_exactly(4)
            if not length_bytes:
                return b""
            response_length = struct.unpack("<I", length_bytes)[0]
            body = self._recv_exactly(response_length)
            if not body:
                return b""
            return length_bytes + body
        except TimeoutError:
            return b""

    def __enter__(self) -> MedocTransport:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
