import glob
import json
import logging
import os
import sys

import serial

from medoc.serial.token_holder import TokenHolder
from medoc.serial.commands.m_getVersion_command import getVersion_command
from medoc.serial.command_api import CommandAPI
from medoc.serial.commands.response import response
from medoc.serial import enums

logger = logging.getLogger(__name__)


class connector:
    MAX_PORT_DEFAULT = 20

    def __init__(self, path_to_preferences=None, auto_detect=False, token_holder: TokenHolder = None):
        self.tunnel = self.create_com_port(path_to_preferences, auto_detect=auto_detect, token_holder=token_holder)
        if not self.tunnel.is_open:
            self.tunnel.open()
        logger.info(f"Connector to {self.tunnel.port} port was successfully created")

    def finalize(self):
        if self.tunnel is not None and self.tunnel.is_open:
            self.tunnel.close()

    def get_com_port(self):
        return self.tunnel

    def _serial_for_port(self, port: str, settings: dict = None, timeout: float = 0.2) -> serial.Serial:
        if settings:
            return serial.Serial(
                port=port,
                baudrate=settings['baudrate'],
                timeout=timeout,
                write_timeout=timeout,
            )
        return serial.Serial(port=port, timeout=timeout)

    def _candidate_ports(self, com: int) -> list[str]:
        if sys.platform == "win32":
            return [f"COM{com}"]
        if "linux" in sys.platform:
            return [f"/dev/ttyUSB{com}"]
        if sys.platform == "darwin":
            return glob.glob("/dev/tty.usbserial-*") + glob.glob("/dev/tty.usbmodem*")
        return []

    def find_com_port(self, token_holder: TokenHolder, min_port=0, max_port=MAX_PORT_DEFAULT, settings: dict = None):
        com = min_port
        while com < max_port:
            for port_path in self._candidate_ports(com):
                try:
                    ser = self._serial_for_port(port_path, settings, timeout=0.2)
                except serial.SerialException:
                    continue

                get_version_cmd = getVersion_command()
                res = CommandAPI.send_command_immediate(ser, token_holder, get_version_cmd, inc_token=True)
                if res is not None and res.command_ack_code == enums.ACKCODE.Ok:
                    if ser.is_open:
                        ser.close()
                    final_timeout = settings.get('timeout', 2.0) if settings else 2.0
                    return self._serial_for_port(port_path, settings, timeout=final_timeout)

                if ser.is_open:
                    ser.close()

            # On darwin we enumerate all ports in one pass, no need to increment
            if sys.platform == "darwin":
                break
            com += 1

        return None

    def create_com_port(self, path_to_preferences=None, auto_detect=False, token_holder: TokenHolder = None):
        data = self._read_preferences(path_to_preferences)

        if auto_detect and token_holder:
            if sys.platform not in ("win32",) and "linux" not in sys.platform and sys.platform != "darwin":
                logger.error("`auto_detect` not supported on this platform; set port in preferences.json")
            else:
                found = self.find_com_port(token_holder, settings=data)
                if found is not None:
                    return found

        if data:
            return serial.Serial(
                port=data['port'],
                baudrate=data['baudrate'],
                timeout=data['timeout'],
                write_timeout=data['write_timeout'],
            )

        # Sensible platform defaults when no preferences file
        if sys.platform == "win32":
            return serial.Serial(port='COM5', baudrate=9600, timeout=0.5, write_timeout=0.5)
        if "linux" in sys.platform:
            return serial.Serial(port='/dev/ttyUSB0', baudrate=9600, timeout=0.5, write_timeout=0.5)
        # darwin
        candidates = glob.glob("/dev/tty.usbserial-*") + glob.glob("/dev/tty.usbmodem*")
        port = candidates[0] if candidates else '/dev/tty.usbserial-0'
        return serial.Serial(port=port, baudrate=9600, timeout=0.5, write_timeout=0.5)

    def _read_preferences(self, path) -> dict | None:
        if path is None or not os.path.isfile(path):
            return None
        logger.info("Reading port preferences from %s", path)
        with open(path) as f:
            data = json.load(f)
        return {
            'port': data['port'],
            'baudrate': data['baudrate'],
            'parity': data.get('parity'),
            'write_timeout': data['write_timeout'],
            'bytesize': data.get('bytesize'),
            'timeout': data['timeout'],
        }
