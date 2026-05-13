import logging

from medoc.serial import enums
from medoc.serial.utilities import converters
from medoc.serial.commands.m_command import command

logger = logging.getLogger(__name__)


class simulate_unit_response_command(command):
    BIT_YES = 0
    BIT_NO = 1

    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        command.__init__(self, command_tag)
        self.response = None
        self.m_isYesPressed = False
        self.m_isNoPressed = False
        self.command_id = enums.COMMAND_ID.SimulateResponseUnit

    def build_command(self, data):
        if 'm_isYesPressed' in data:
            self.m_isYesPressed = data['m_isYesPressed']
        if 'm_isNoPressed' in data:
            self.m_isNoPressed = data['m_isNoPressed']

    def write_data(self):
        command.write_data(self)
        options_byte = 0
        options_byte = converters.set_bit(options_byte, self.BIT_YES, self.m_isYesPressed)
        options_byte = converters.set_bit(options_byte, self.BIT_NO, self.m_isNoPressed)
        return [options_byte]

    def send_message(self):
        logger.info(str(self))
