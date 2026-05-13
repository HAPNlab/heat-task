import logging

from medoc.serial import crc8, enums
from medoc.serial.commands import m_message
from medoc.serial.utilities import converters
from medoc.serial.commands.r_finite_ramp_by_temperature import finite_ramp_by_temperature_response
from medoc.serial.commands.r_finite_ramp_by_time import finite_ramp_by_time_response
from medoc.serial.commands.r_get_errors_command import get_errors_response
from medoc.serial.commands.r_get_status_TCU import get_statusTCU_response
from medoc.serial.commands.r_get_version_command import get_version_response
from medoc.serial.commands.response import response

logger = logging.getLogger(__name__)

CRC_INDEX = 0
LENGTH_INDEX = 1
ID_INDEX = LENGTH_INDEX + 2
TOKEN_INDEX = ID_INDEX + 1
TAG_INDEX = TOKEN_INDEX + 4
LENGTH_EXTRA_DATA_COMMAND = TAG_INDEX + 1
ACK_CODE_INDEX = TAG_INDEX + 1
EXTRA_DATA_RESPONSE_INDEX = ACK_CODE_INDEX + 1


class command(m_message.message):
    def __init__(self, command_tag: enums.DEVICE_TAG = enums.DEVICE_TAG.Master):
        m_message.message.__init__(self, command_tag)
        self.response = None

    def to_bytes(self):
        if self.command_id == enums.COMMAND_ID.Undefined:
            raise ValueError("Invalid command id")
        array1 = [0x00] * m_message.MAX_LENGTH
        array1[ID_INDEX] = self.command_id.value
        if self.command_token is not None:
            tok = converters.get_bytes32(self.command_token)
            array1[TOKEN_INDEX] = tok[3]
            array1[TOKEN_INDEX + 1] = tok[2]
            array1[TOKEN_INDEX + 2] = tok[1]
            array1[TOKEN_INDEX + 3] = tok[0]
        array1[TAG_INDEX] = 0 if self.command_tag is None else self.command_tag.value
        extra_data = self.write_data()
        write_len = len(extra_data)
        for i, byte in enumerate(extra_data):
            array1[LENGTH_EXTRA_DATA_COMMAND + i] = byte
        command_length = TAG_INDEX + write_len + 1
        array_length = converters.get_bytes16(command_length - 1)
        array1[LENGTH_INDEX] = array_length[1]
        array1[LENGTH_INDEX + 1] = array_length[0]
        crc = crc8.calculate(array1, CRC_INDEX + 1, command_length - 1)
        array1[CRC_INDEX] = crc
        self.command_array = array1[0:command_length]

    def send_message(self):
        pass

    def build_command(self, data):
        pass

    def write_data(self):
        return []

    def header_length_from_bytes(self, header):
        return converters.to_int_16(header, LENGTH_INDEX)

    def receive_response(self, header_buffer, body_buffer):
        command_length = converters.to_u_int_16_ex(header_buffer, LENGTH_INDEX) - len(header_buffer) + 1
        buf = list(header_buffer)
        buf.extend(body_buffer[0:command_length])
        self.get_message(buf)

    def get_message(self, buffer):
        crc = buffer[CRC_INDEX]
        length = converters.to_uint_16(buffer, LENGTH_INDEX)
        if length + 1 > len(buffer):
            raise ValueError(
                f"Invalid length of input buffer: {length + 1}  len(buffer): {len(buffer)}"
            )
        crc_calculated = crc8.calculate(buffer, CRC_INDEX + 1, length)
        if crc != crc_calculated:
            raise ValueError("Invalid crc code")
        if self.command_id.value != buffer[ID_INDEX]:
            raise ValueError("Invalid command id")
        self.create_response(buffer)

    def create_response(self, buffer):
        length = converters.to_uint_16(buffer, LENGTH_INDEX)
        self.build_response(self.command_id.value)
        self.response.command_id = enums.COMMAND_ID(buffer[ID_INDEX])
        self.response.command_token = converters.to_uint_32(buffer, TOKEN_INDEX)
        self.response.command_tag = enums.DEVICE_TAG(buffer[TAG_INDEX])
        self.response.command_ack_code = enums.ACKCODE(buffer[ACK_CODE_INDEX])
        if self.response.command_ack_code == enums.ACKCODE.Ok:
            self.response.read_data(buffer, EXTRA_DATA_RESPONSE_INDEX)

    def build_response(self, command_id) -> object:
        if command_id in (18, 19):
            self.response = response()
        elif command_id == 22:
            self.response = response()
        elif command_id == 25:
            self.response = response()
        elif command_id == 27:
            self.response = response()
        elif command_id == 28:
            self.response = finite_ramp_by_time_response()
        elif command_id == 29:
            self.response = finite_ramp_by_temperature_response()
        elif command_id == 33:
            self.response = get_statusTCU_response()
        elif command_id == 35:
            self.response = get_errors_response()
        elif command_id == 36:
            self.response = response()
        elif command_id == 37:
            self.response = get_version_response()
        elif command_id == 41:
            self.response = response()
        elif command_id == 45:
            self.response = response()
        elif command_id == 47:
            self.response = response()
        elif command_id == 83:
            self.response = response()
