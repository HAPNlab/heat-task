import logging

from medoc.serial import enums
from medoc.serial.utilities import converters, temp_converter
from medoc.serial.commands.m_message import message
from medoc.serial.enums import COMMAND_ID
from medoc.serial.commands.r_get_pid_calculation_response import get_pid_calculation_response
from medoc.serial.commands.r_status import get_status_response

logger = logging.getLogger(__name__)


class get_statusTCU_response(get_status_response):
    SYSTEM_STATUS_BIT_WAIT_FOR_TRIGGER = 4
    IO_STATE_BIT_RESPONSE_UNIT_YES_ON = 0
    IO_STATE_BIT_RESPONSE_UNIT_NO_ON = 1
    IO_STATE_BIT_EXTERNAL_TRIGGER_ON = 2
    IO_STATE_BIT_CONDITION_EVENT = 7

    def __init__(self):
        get_status_response.__init__(self)
        self.m_isWaitForTrigger = False
        self.m_covas = None
        self.m_isResponseUnitYesOn = False
        self.m_isResponseUnitNoOn = False
        self.m_isExternalTriggerOn = False
        self.m_externalTriggerTimestamp = None
        self.m_isConditionEvent = False
        self.m_conditionEvents = None
        self.m_eventBufferFreeSpace = None
        self.m_heaterTemperature = None
        self.m_tecTemperature = None
        self.m_waterTemperature = 0.0
        self.m_pcbTemperature = 0.0
        self.m_heatsink1Temperature = 0.0
        self.m_heatsink2Temperature = 0.0
        self.m_stateWord = 0
        self.m_chepsResponse = 0.0
        self.m_atsResponse = 0.0
        self.response = None
        self.command_id = COMMAND_ID.GetStatusTCU
        self.m_thermodeDetection = None
        self.m_slaveDeviceStatus = None
        self.m_slave_tecTemperature = None
        self.m_slave_waterTemperature = 0.0
        self.m_slave_isWaitForTrigger = False
        self.m_pid_data = None
        self.m_slave_pid_data = None
        self.m_slave_eventBufferFreeSpace = False
        self.m_healthStatus = None
        self.m_mainThermodeModel = None
        self.m_refThermodeModel = None

    def read_data(self, buffer, start_position):
        current_position = start_position
        get_status_response.read_data(self, buffer, current_position)

        self.m_timestamp = converters.to_uint_32(buffer, start_position)
        start_position += 4
        self.m_temperatureBufferStartTime = converters.to_uint_32(buffer, start_position)
        start_position += 4
        self.m_executingCommandToken = converters.to_uint_32(buffer, start_position)
        start_position += 4
        m_system_status_byte = buffer[start_position]
        start_position += 1
        self.m_systemState = m_system_status_byte & self.SYSTEM_STATE_MASK
        self.m_isWaitForTrigger = converters.get_bit(m_system_status_byte, self.SYSTEM_STATUS_BIT_WAIT_FOR_TRIGGER)
        self.m_currentThermode = converters.get_bit(m_system_status_byte, self.SYSTEM_STATUS_BIT_CURRENT_THERMODE1)
        self.m_isError = converters.get_bit(m_system_status_byte, self.SYSTEM_STATUS_BIT_ERROR)
        self.m_covas = buffer[start_position]
        start_position += 1
        io_state_byte = buffer[start_position]
        start_position += 1
        self.m_isResponseUnitYesOn = converters.get_bit(io_state_byte, self.IO_STATE_BIT_RESPONSE_UNIT_YES_ON)
        self.m_isResponseUnitNoOn = converters.get_bit(io_state_byte, self.IO_STATE_BIT_RESPONSE_UNIT_NO_ON)
        self.m_isExternalTriggerOn = converters.get_bit(io_state_byte, self.IO_STATE_BIT_EXTERNAL_TRIGGER_ON)
        self.m_isConditionEvent = converters.get_bit(io_state_byte, self.IO_STATE_BIT_CONDITION_EVENT)
        self.m_commandBufferFreeSpace = buffer[start_position]
        start_position += 1
        self.m_eventBufferFreeSpace = buffer[start_position]
        start_position += 1
        heater_quantity = buffer[start_position]
        start_position += 1

        self.m_heaterTemperature = []
        for _ in range(heater_quantity):
            temp = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_heaterTemperature.append(temp_converter.tcu2pc(temp))

        tec_quantity = buffer[start_position]
        start_position += 1
        self.m_tecTemperature = []
        for _ in range(tec_quantity):
            tec = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_tecTemperature.append(temp_converter.tcu2pc(tec))

        if self.m_currentThermode == enums.ThermodeType['AirTSA']:
            val = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_heatsink1Temperature = temp_converter.tcu2pc(val)
            val = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_heatsink2Temperature = temp_converter.tcu2pc(val)
            self.m_stateWord = converters.to_u_int_16_ex(buffer, start_position)
            start_position += 2
            self.m_isSafetyStatusOn = bool(self.m_stateWord & 16)
        else:
            val = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_waterTemperature = temp_converter.tcu2pc(val)
            val = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_pcbTemperature = temp_converter.tcu2pc(val)
            self.m_thermodeDetection = buffer[start_position]
            start_position += 1
            self.m_isSafetyStatusOn = converters.get_bit(m_system_status_byte, self.SYSTEM_STATUS_BIT_SAFETY_STATUS_ON)

        self.m_version = buffer[start_position]
        start_position += 1
        if self.m_version == 5:
            val = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_chepsResponse = temp_converter.tcu2pc(val)
            val = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_atsResponse = temp_converter.tcu2pc(val)

        self.m_mainThermodeModel = buffer[start_position]
        start_position += 1
        self.m_refThermodeModel = buffer[start_position]
        start_position += 1

        cnt = buffer[start_position]
        start_position += 1
        self.m_slave_tecTemperature = []
        for _ in range(cnt):
            temp = converters.to_int_16(buffer, start_position)
            start_position += 2
            self.m_slave_tecTemperature.append(temp_converter.tcu2pc(temp))

        temp = converters.to_int_16(buffer, start_position)
        start_position += 2
        self.m_slave_waterTemperature = temp_converter.tcu2pc(temp)

        cnt = buffer[start_position]
        start_position += 1
        self.m_pid_data = []
        for _ in range(cnt):
            pid_response = get_pid_calculation_response()
            start_position = pid_response.read_data(buffer, start_position)
            self.m_pid_data.append(pid_response)

        cnt = buffer[start_position]
        start_position += 1
        self.m_slave_pid_data = []
        for _ in range(cnt):
            slave_pid_response = get_pid_calculation_response()
            start_position = slave_pid_response.read_data(buffer, start_position)
            self.m_slave_pid_data.append(slave_pid_response)

        self.m_slave_temperatureBufferStartTime = converters.to_uint_32(buffer, start_position)
        start_position += 4
        self.m_slave_executingCommandToken = converters.to_uint_32(buffer, start_position)
        start_position += 4
        self.m_slave_commandBufferFreeSpace = buffer[start_position]
        start_position += 1
        self.m_slave_eventBufferFreeSpace = buffer[start_position]
        start_position += 1
        self.m_healthStatus = converters.to_uint_16(buffer, start_position)
        start_position += 2
        self.m_slave_isWaitForTrigger = buffer[start_position]
        start_position += 1
        return start_position - current_position

    def get_state(self):
        return self.m_systemState

    def get_temp(self):
        if not self.m_heaterTemperature:
            return 0.0
        return sum(self.m_heaterTemperature) / len(self.m_heaterTemperature)

    def get_temp_slave(self):
        if not self.m_slave_tecTemperature:
            return 0.0
        return sum(self.m_slave_tecTemperature) / len(self.m_slave_tecTemperature)

    def response_message(self):
        logger.info(f'{str(self)}')

    def __str__(self):
        base = message.__str__(self)
        return (
            f"RESPONSE::: {base}\n"
            f"\t\t\t\t\t\t\t TCU state: {enums.SystemState(self.m_systemState) if self.m_systemState is not None else None}\n"
            f"\t\t\t\t\t\t\t Temperature: {self.get_temp()}\n"
            f"\t\t\t\t\t\t\t Patient Response Yes: {self.m_isResponseUnitYesOn}\n"
            f"\t\t\t\t\t\t\t Patient Response No: {self.m_isResponseUnitNoOn}\n"
        )
