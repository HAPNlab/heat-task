"""TCP socket transport for the Medoc MMS external control interface."""

from __future__ import annotations

import socket
import struct
from types import TracebackType


class MedocConnectionClosed(Exception):
    """The peer closed the connection before a full frame was received."""


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
        # Disable Nagle's algorithm: this is a small-message request/response
        # protocol, and Nagle interacting with the peer's delayed ACKs causes
        # intermittent 40–200 ms latency spikes in the status poll loop.
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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
                raise MedocConnectionClosed(
                    f"peer closed after {nbytes - remaining}/{nbytes} bytes"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def recv_frame(self) -> bytes:
        """Read one length-prefixed frame, or raise.

        Raises ``TimeoutError`` if no data arrives within ``recv_timeout`` and
        ``MedocConnectionClosed`` if the peer closes mid-frame. Callers that want
        the old "empty bytes on failure" behaviour should use :meth:`recv`.
        """
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")
        length_bytes = self._recv_exactly(4)
        response_length = struct.unpack("<I", length_bytes)[0]
        body = self._recv_exactly(response_length)
        return length_bytes + body

    def recv(self) -> bytes:
        try:
            return self.recv_frame()
        except (TimeoutError, MedocConnectionClosed):
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
