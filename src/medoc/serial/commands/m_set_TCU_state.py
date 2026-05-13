import logging

from medoc.serial import enums
from medoc.serial.commands.m_command import command

logger = logging.getLogger(__name__)


class set_TCU_state_command(command):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        command.__init__(self, command_tag)
        self.m_state = enums.SystemState.SafeMode
        self.m_runSelfTest = True
        self.response = None
        self.command_id = enums.COMMAND_ID.SetTcuState

    def write_data(self):
        command.write_data(self)
        extra_data = [0x00] * 2
        extra_data[0] = self.m_state.value
        extra_data[1] = 1 if self.m_runSelfTest else 0
        return extra_data

    def build_command(self, data):
        if 'm_state' in data:
            self.m_state = enums.SystemState(data['m_state'])
        if 'm_runSelfTest' in data:
            self.m_runSelfTest = data['m_runSelfTest']

    def send_message(self):
        logger.info(str(self))
