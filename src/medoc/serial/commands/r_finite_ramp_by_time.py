import logging

from medoc.serial.commands.m_message import message
from medoc.serial.commands.response import response

logger = logging.getLogger(__name__)


class finite_ramp_by_time_response(response):
    def __init__(self):
        self.m_temperature = 0
        self.m_time = 0
        self.m_isUseTimeMark = False
        self.m_isWaitForTrigger = False
        self.m_isPeakDetect = False
        self.m_isCreateTimeMark = False
        self.m_isDynamicFactor = False
        self.m_isAllowEmptyBuffer = None
        self.m_ignoreKdPidParameter = False
        self.m_isStopOnResponseUnitYes = False
        self.m_isStopOnResponseUnitNo = False

    def read_data(self, buffer, start_position=0):
        pass

    def __str__(self):
        return f"RESPONSE::: {message.__str__(self)} ack code {self.command_ack_code} "

    def response_message(self):
        logger.info(f'{str(self)}\n')
