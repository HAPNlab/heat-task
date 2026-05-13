import logging

from medoc.serial import enums
from medoc.serial.commands.m_command import command
from medoc.serial.commands.m_finite_ramp_safe_duration_command import finite_ramp_safe_duration_command
from medoc.serial.utilities import converters, temp_converter

logger = logging.getLogger(__name__)


class finite_ramp_by_temperature_command(finite_ramp_safe_duration_command):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        finite_ramp_safe_duration_command.__init__(self, command_tag)
        self.m_lowMargin = 0
        self.m_highMargin = 0
        self.response = None
        self.command_id = enums.COMMAND_ID.FiniteRampByTemperature

    def build_command(self, data):
        for attr in (
            'm_allowSafeDurationOffset', 'm_isWaitForTrigger', 'm_isPeakDetect',
            'm_isCreateTimeMark', 'm_isDynamicFactor', 'm_isAllowEmptyBuffer',
            'm_ignoreKdPidParameter', 'm_isStopOnResponseUnitNo', 'm_isStopOnResponseUnitYes',
            'm_temperature', 'm_time',
        ):
            if attr in data:
                setattr(self, attr, data[attr])

    def write_data(self):
        extra_data = [0x00] * 13
        command.write_data(self)
        position = 0

        temp = converters.get_bytes16(temp_converter.pc2tcu(self.m_temperature))
        extra_data[position] = temp[1]
        extra_data[position + 1] = temp[0]
        position += 2

        low = converters.get_bytes16(temp_converter.pc2tcu(self.m_lowMargin))
        extra_data[position] = low[1]
        extra_data[position + 1] = low[0]
        position += 2

        high = converters.get_bytes16(temp_converter.pc2tcu(self.m_highMargin))
        extra_data[position] = high[1]
        extra_data[position + 1] = high[0]
        position += 2

        tok = converters.get_bytes32(self.m_time)
        extra_data[position] = tok[3]
        extra_data[position + 1] = tok[2]
        extra_data[position + 2] = tok[1]
        extra_data[position + 3] = tok[0]
        position += 4

        options_byte = 0
        options_byte = converters.set_bit(options_byte, self.WAIT_TRIGGER_BIT, self.m_isWaitForTrigger)
        options_byte = converters.set_bit(options_byte, self.PEAK_DETECT_BIT, self.m_isPeakDetect)
        options_byte = converters.set_bit(options_byte, self.CREATE_TIME_MARK_BIT, self.m_isCreateTimeMark)
        options_byte = converters.set_bit(options_byte, self.USE_DYNAMIC_FACTOR, self.m_isDynamicFactor)
        options_byte = converters.set_bit(options_byte, self.ALLOW_EMPTY_BUFFER_BIT, self.m_isAllowEmptyBuffer)
        options_byte = converters.set_bit(options_byte, self.IGNORE_KD_PID_PARAMETER_BIT, self.m_ignoreKdPidParameter)
        if self.m_allowSafeDurationOffset is not None:
            options_byte = converters.set_bit(options_byte, self.ALLOW_SAFE_DURATION_OFFSET, self.m_allowSafeDurationOffset)
        extra_data[position] = options_byte
        position += 1

        stop_condition_byte = 0
        stop_condition_byte = converters.set_bit(stop_condition_byte, self.STOP_ON_YES_BIT, self.m_isStopOnResponseUnitYes)
        stop_condition_byte = converters.set_bit(stop_condition_byte, self.STOP_ON_NO_BIT, self.m_isStopOnResponseUnitNo)
        extra_data[position] = stop_condition_byte
        position += 1

        extra_data[position] = self.m_conditionEventsLength
        return extra_data

    def send_message(self):
        logger.info(str(self))
