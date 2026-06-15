"""High-level client for the Medoc MMS external control interface."""

from __future__ import annotations

from heat_task.medoc.models import Command, MedocResponse
from heat_task.medoc.protocol import decode_response, encode_command
from heat_task.medoc.transport import MedocTransport


class MedocClient:
    """High-level API for controlling the Medoc Main Station over TCP.

    Usage::

        with MedocClient.connect("192.168.1.100") as mc:
            print(mc.status())
            mc.select_test(15)
            mc.start()
            ...
            mc.stop()
    """

    def __init__(self, transport: MedocTransport) -> None:
        self._transport = transport

    @classmethod
    def connect(
        cls,
        host: str,
        port: int = MedocTransport.DEFAULT_PORT,
        **kwargs: float,
    ) -> MedocClient:
        """Create a connected MedocClient."""
        transport = MedocTransport(host, port, **kwargs)
        transport.connect()
        return cls(transport)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> MedocClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def send_command(
        self, command: Command, parameter: int | None = None
    ) -> MedocResponse | None:
        """Send a command and return the parsed response, or None on timeout."""
        payload = encode_command(command, parameter)
        self._transport.send(payload)
        data = self._transport.recv()
        if not data:
            return None
        try:
            return decode_response(data)
        except ValueError:
            return None

    def status(self) -> MedocResponse | None:
        return self.send_command(Command.STATUS)

    def select_test(self, program_id: int) -> MedocResponse | None:
        return self.send_command(Command.SELECT_TEST, program_id)

    def start(self) -> MedocResponse | None:
        return self.send_command(Command.START)

    def pause(self) -> MedocResponse | None:
        return self.send_command(Command.PAUSE)

    def trigger(self) -> MedocResponse | None:
        return self.send_command(Command.TRIGGER)

    def stop(self) -> MedocResponse | None:
        return self.send_command(Command.STOP)

    def abort(self) -> MedocResponse | None:
        return self.send_command(Command.ABORT)

    def yes(self) -> MedocResponse | None:
        return self.send_command(Command.YES)

    def no(self) -> MedocResponse | None:
        return self.send_command(Command.NO)

    def covas(self) -> MedocResponse | None:
        return self.send_command(Command.COVAS)

    def vas(self) -> MedocResponse | None:
        return self.send_command(Command.VAS)

    def specify_next(self) -> MedocResponse | None:
        return self.send_command(Command.SPECIFY_NEXT)

    def t_up(self, degrees: float) -> MedocResponse | None:
        """Increase temperature by the given number of degrees (×100 on wire)."""
        return self.send_command(Command.T_UP, int(degrees * 100))

    def t_down(self, degrees: float) -> MedocResponse | None:
        """Decrease temperature by the given number of degrees (×100 on wire)."""
        return self.send_command(Command.T_DOWN, int(degrees * 100))

    def key_up(self) -> MedocResponse | None:
        """Stop the current temperature gradient."""
        return self.send_command(Command.KEY_UP)
