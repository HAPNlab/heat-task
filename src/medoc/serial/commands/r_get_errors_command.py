import logging

from medoc.serial.commands.error_occurance import error_item
from medoc.serial.commands.m_message import message
from medoc.serial.commands.response import response

logger = logging.getLogger(__name__)


class get_errors_response(response):
    def __init__(self):
        response.__init__(self)
        self.m_errors = []

    def read_data(self, buffer, start_position=0):
        count = buffer[start_position]
        start_position += 1
        for _ in range(count):
            occurrence = error_item()
            occurrence.read_data(buffer, start_position)
            self.m_errors.append(occurrence)

    def response_message(self):
        logger.info(f'{str(self)}')

    def __str__(self):
        output = f'Error count: {len(self.m_errors)}\n'
        for item in self.m_errors:
            output += f'{str(item)}\n '
        return f'RESPONSE::: {message.__str__(self)} ack code {self.command_ack_code}\n\t\t\t\t\t\t\t ' + output
