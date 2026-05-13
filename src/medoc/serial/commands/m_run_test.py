import logging

from medoc.serial import enums
from medoc.serial.commands.m_command import command

logger = logging.getLogger(__name__)


class run_test_command(command):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        command.__init__(self, command_tag)
        self.response = None
        self.m_isResetClock = True
        self.command_id = enums.COMMAND_ID.RunTest

    def build_command(self, data):
        if 'm_isResetClock' in data:
            self.m_isResetClock = data['m_isResetClock']

    def write_data(self):
        command.write_data(self)
        return [0x1 if self.m_isResetClock else 0x0]

    def send_message(self):
        logger.info(str(self))
