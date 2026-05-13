import logging

from medoc.serial.commands.m_message import message
from medoc.serial.commands.response import response

logger = logging.getLogger(__name__)


class finite_ramp_by_temperature_response(response):
    def __init__(self):
        self.m_isStopOnResponseUnitNo = None
        self.m_isStopOnResponseUnitYes = None
        self.m_ignoreKdPidParameter = None
        self.m_isAllowEmptyBuffer = None
        self.m_isDynamicFactor = None
        self.m_isCreateTimeMark = None
        self.m_isWaitForTrigger = None
        self.m_time = None
        self.m_high = None
        self.m_low = None
        self.m_temperature = None
        self.m_isPeakDetect = None
        self.m_condEventsNo = None

    def read_data(self, buffer, start_position=0):
        pass

    def __str__(self):
        return f"RESPONSE::: {message.__str__(self)} ack code {self.command_ack_code} "

    def response_message(self):
        logger.info(f'{str(self)}\n')
