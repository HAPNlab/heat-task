"""High-level client for the Medoc MMS external control interface."""

from __future__ import annotations

from medoc.models import Command, MedocResponse
from medoc.protocol import decode_response, encode_command
from medoc.transport import MedocTransport


class MedocClient:
    """High-level API for controlling the Medoc Main Station.

    Usage::

        with MedocClient("192.168.1.100") as mc:
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

    def yes(self) -> MedocResponse | None:
        return self.send_command(Command.YES)

    def no(self) -> MedocResponse | None:
        return self.send_command(Command.NO)

    def increase_temp(self, degrees: float) -> MedocResponse | None:
        return self.send_command(Command.INCREASE_TEMP, int(degrees * 100))

    def decrease_temp(self, degrees: float) -> MedocResponse | None:
        return self.send_command(Command.DECREASE_TEMP, int(degrees * 100))

    def key_up(self) -> MedocResponse | None:
        return self.send_command(Command.KEY_UP)

    def next_sequence(self) -> MedocResponse | None:
        return self.send_command(Command.NEXT_SEQUENCE)
