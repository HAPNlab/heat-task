from medoc.serial.utilities import converters
from medoc.serial.enums import DeviceType, TcuErrorCode


class error_item:
    WARNING_FLAG = 0x2000
    TEST_ERROR_FLAG = 0x4000
    FATAL_ERROR_FLAG = 0x8000
    m_deviceType = DeviceType.TSA3

    def __init__(self):
        self.m_errorCode = None
        self.m_timestamp = None
        self.m_temperature = None
        self.m_time = None
        self.m_tag = None
        self.Param1 = None
        self.Param2 = None
        self.Param3 = None
        self.Param4 = None

    def read_data(self, buffer, start_position=0):
        error = converters.to_uint_16(buffer, start_position)
        start_position += 2
        self.m_errorCode = TcuErrorCode(error)
        self.m_timestamp = converters.to_uint_32(buffer, start_position)
        start_position += 4
        self.m_temperature = converters.to_int_16(buffer, start_position)
        start_position += 2
        self.m_time = converters.to_uint_32(buffer, start_position)
        start_position += 4
        self.Param1 = buffer[start_position]
        start_position += 1
        self.Param2 = converters.to_int_16(buffer, start_position)
        start_position += 2
        self.Param3 = converters.to_int_16(buffer, start_position)
