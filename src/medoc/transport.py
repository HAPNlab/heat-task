"""TCP socket transport for the Medoc MMS external control interface."""

from __future__ import annotations

import socket
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

    def recv(self, bufsize: int = 4096) -> bytes:
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")
        try:
            return self._sock.recv(bufsize)
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
