import logging

from medoc.serial import enums
from medoc.serial.commands.m_command import command

logger = logging.getLogger(__name__)


class end_test_command(command):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        command.__init__(self, command_tag)
        self.response = None
        self.command_id = enums.COMMAND_ID.EndTest

    def send_message(self):
        logger.info(str(self))
