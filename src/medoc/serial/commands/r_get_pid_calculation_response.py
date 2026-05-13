import logging

from medoc.serial.utilities import converters, temp_converter
from medoc.serial.commands.response import response

logger = logging.getLogger(__name__)


class get_pid_calculation_response(response):
    def __init__(self):
        self.m_thermodeID = 0
        self.m_pidID = None
        self.m_timeStamp = None
        self.m_P = False
        self.m_I = None
        self.m_D = False
        self.m_error = 0
        self.m_setPoint = 0
        self.m_oldSetPoint = 0
        self.m_temp1 = 0
        self.m_temp2 = 0
        self.m_actTemp = 0
        self.m_dac = 0
        self.m_realTemp1 = 0
        self.m_realTemp2 = 0
        self.m_pcb = 0
        self.m_water = 0
        self.m_heatsinkTemp1 = 0
        self.m_heatsinkTemp2 = 0
        self.m_tecTemp = 0
        response.__init__(self)

    def read_data(self, buffer, start_position=0):
        self.m_pidID = buffer[start_position]
        start_position += 1
        self.m_timeStamp = converters.to_uint_32(buffer, start_position)
        start_position += 4
        self.m_setPoint = converters.to_int_16(buffer, start_position)
        start_position += 2
        self.m_temp1 = converters.to_int_16(buffer, start_position)
        start_position += 2
        self.m_temp2 = converters.to_int_16(buffer, start_position)
        start_position += 2
        self.m_dac = converters.to_uint_16(buffer, start_position)
        start_position += 2
        return start_position
