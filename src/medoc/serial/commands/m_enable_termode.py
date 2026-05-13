import logging

from medoc.serial import enums
from medoc.serial.commands.m_command import command

logger = logging.getLogger(__name__)


class enable_termode_command(command):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        command.__init__(self, command_tag)
        self.response = None
        self.m_isEnabled = True
        self.m_thermodeType = enums.ThermodeType.TSA
        self.command_id = enums.COMMAND_ID.EnableThermode

    def build_command(self, data):
        if 'm_isEnabled' in data:
            self.m_isEnabled = data['m_isEnabled']
        if 'm_thermodeType' in data:
            self.m_thermodeType = enums.ThermodeType(data['m_thermodeType'])

    def write_data(self):
        command.write_data(self)
        extra_data = [0x00] * 2
        extra_data[0] = self.m_thermodeType.value
        extra_data[1] = 1 if self.m_isEnabled else 0
        return extra_data

    def send_message(self):
        logger.info(str(self))
