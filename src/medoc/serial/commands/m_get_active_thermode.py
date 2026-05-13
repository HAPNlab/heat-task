import logging

from medoc.serial import enums
from medoc.serial.commands.m_command import command

logger = logging.getLogger(__name__)


class get_active_thermode_command(command):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        command.__init__(self, command_tag)
        self.m_thermodeId = 0
        self.response = None
        self.command_id = enums.COMMAND_ID.GetActiveThermode

    def write_data(self):
        command.write_data(self)
        return [self.m_thermodeId]

    def build_command(self, data):
        if 'm_thermodeId' in data:
            self.m_thermodeId = data['m_thermodeId']

    def send_message(self):
        logger.info(f'{str(self)}\n')
