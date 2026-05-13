import logging
import time

import serial

from medoc.serial.token_holder import TokenHolder
from medoc.serial.commands.m_command import command
from medoc.serial.commands.response import response

logger = logging.getLogger(__name__)


class CommandAPI:
    @staticmethod
    def send_command_immediate(ser, token_holder: TokenHolder, com: command, data=None, inc_token=False) -> response:
        com_processed = CommandAPI.process_command(token_holder.token, com, data)
        res = CommandAPI._write_command(ser, com_processed)
        if inc_token:
            token_holder.token += 1
        return res

    @staticmethod
    def process_command(token_raw: int, com: command, data=None) -> command:
        if data is not None:
            com.build_command(data)
        com.command_token = token_raw
        com.send_message()
        com.to_bytes()
        return com

    @staticmethod
    def _write_command(ser: serial.Serial, processed_command: command) -> response:
        try:
            send_length = ser.write(processed_command.command_array)
            if send_length == 0:
                logger.error("Send command failed - Wrote 0 bytes")
                return None
        except serial.SerialTimeoutException:
            logger.error("Send command failed - Write timeout")
            return None

        ser.flush()

        timeout_start = time.time()
        while ser.in_waiting < 4:
            if time.time() >= timeout_start + 0.2:
                break

        try:
            header = ser.read(4)
            if len(header) < 4:
                logger.error("Read response failed - Read less than expected (4) bytes")
                return None
        except serial.SerialTimeoutException:
            logger.error("Read response failed - Read timeout")
            return None

        command_length = processed_command.header_length_from_bytes(header)

        while ser.in_waiting:
            data = ser.read(command_length)
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            try:
                processed_command.receive_response(header, data)
                processed_command.response.response_message()
            except ValueError:
                logger.error("Invalid command id for command: `%s`", processed_command)
                return None

        return processed_command.response
