import logging

from medoc.serial import enums
from medoc.serial.commands.m_message import message

logger = logging.getLogger(__name__)


class response(message):
    def __init__(self, command_id=None):
        message.__init__(self, enums.DEVICE_TAG.Master)
        self.command_ack_code = None

    def read_data(self, buffer, start_position=0):
        pass

    def __str__(self):
        base = message.__str__(self)
        return f'{base} ack code {self.command_ack_code}:::'

    def response_message(self):
        logger.info(f'RESPONSE::: {str(self)}\n')
