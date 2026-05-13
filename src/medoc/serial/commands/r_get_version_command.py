import logging

from medoc.serial.utilities import converters
from medoc.serial.commands.m_message import message
from medoc.serial.commands.response import response

logger = logging.getLogger(__name__)


class get_version_response(response):
    def __init__(self):
        response.__init__(self)
        self.m_version = None

    def read_data(self, buffer, start_position=0):
        self.m_version = converters.to_string(buffer, start_position)

    def response_message(self):
        logger.info(f'{str(self)}')

    def __str__(self):
        base = message.__str__(self)
        return (
            f'RESPONSE::: {base} ack code {self.command_ack_code}'
            f'\n\t\t\t\t\t\t\t Version: {self.m_version}\n'
        )
