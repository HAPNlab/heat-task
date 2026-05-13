from medoc.serial import enums
from medoc.serial.commands.m_finite_ramp_command import finite_ramp_command


class finite_ramp_safe_duration_command(finite_ramp_command):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        finite_ramp_command.__init__(self, command_tag)
        self.m_allowSafeDurationOffset = None
