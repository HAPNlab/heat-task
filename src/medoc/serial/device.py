"""TsaDevice — serial API for the Medoc TSA2 thermode."""

from __future__ import annotations

import logging
import sys
import threading
import time

from medoc.serial import enums
from medoc.serial.command_api import CommandAPI
from medoc.serial.commands.m_clear_command_buffer import clear_command_buffer_command
from medoc.serial.commands.m_enable_termode import enable_termode_command
from medoc.serial.commands.m_end_test_command import end_test_command
from medoc.serial.commands.m_finite_ramp_by_temperature_command import finite_ramp_by_temperature_command
from medoc.serial.commands.m_finite_ramp_by_time_command import finite_ramp_by_time_command
from medoc.serial.commands.m_get_active_thermode import get_active_thermode_command
from medoc.serial.commands.m_getVersion_command import getVersion_command
from medoc.serial.commands.m_getstatusTCU_command import get_status_TCU_command
from medoc.serial.commands.m_run_test import run_test_command
from medoc.serial.commands.m_set_TCU_state import set_TCU_state_command
from medoc.serial.commands.m_set_active_thermode import set_active_thermode_command
from medoc.serial.commands.m_simulate_response_unit import simulate_unit_response_command
from medoc.serial.commands.m_stop_test_command import stop_test_command
from medoc.serial.commands.response import response
from medoc.serial.connector import connector
from medoc.serial.event import Event, TypedEvent
from medoc.serial.token_holder import TokenHolder
from medoc.safety import get_safety_level, get_safety_ms

logger = logging.getLogger(__name__)


class TsaDevice:
    """Communicates with a Medoc TSA-based device over serial."""

    def __init__(self, auto_connect_port=True, preferences_path="preferences.json") -> None:
        self.current_thermode: enums.DEVICE_TAG = enums.DEVICE_TAG.Master
        self.token_holder: TokenHolder = TokenHolder()

        if auto_connect_port and sys.platform not in ("win32", "darwin") and "linux" not in sys.platform:
            logger.error("`auto_connect_port` not available on this platform; set port in preferences.json")
            auto_connect_port = False

        self.connector: connector = connector(
            path_to_preferences=preferences_path,
            auto_detect=auto_connect_port,
            token_holder=self.token_holder,
        )

        self.event_status_updated: Event = Event()
        self.event_patient_response: TypedEvent = TypedEvent(bool, bool)

        self.busy: bool = False
        self.last_safety_level = 0.0
        self.safety_start_time = time.time()

        self.status_state = None
        self.status_temp = 0.0
        self._last_status = None

        self.status_thread = None
        self.status_thread_stop = False

        self.event_status_updated.connect(self._on_get_status_event)

    @staticmethod
    def validate_response(res: response):
        return res if (res is not None and res.command_ack_code == enums.ACKCODE.Ok) else None

    def _on_get_status_event(self, status_res):
        self.status_state = enums.SystemState(status_res.get_state())
        self.status_temp = status_res.get_temp()
        self._last_status = status_res

        safety_level = get_safety_level(self.status_temp)
        if safety_level != self.last_safety_level:
            self.last_safety_level = safety_level
            self.safety_start_time = time.time()

        safety_ms = get_safety_ms(self.status_temp)
        if time.time() >= self.safety_start_time + (safety_ms / 1000):
            self._safety_failure()

        yes_press = status_res.m_isResponseUnitYesOn
        no_press = status_res.m_isResponseUnitNoOn
        if no_press or yes_press:
            self.event_patient_response.emit(yes_press, no_press)

    def _safety_failure(self):
        self.end_test()
        self.stop_status_thread()
        self.finalize()
        logger.error("TEMPERATURE SAFETY FAILURE — temperature reached %.2f°C", self.status_temp)
        raise RuntimeError(f"TEMPERATURE SAFETY FAILURE — temperature reached {self.status_temp}°C")

    def start_status_thread(self, update_rate=1.0):
        self.status_thread_stop = False
        self.status_thread = threading.Thread(target=self._status_thread, args=[update_rate], daemon=True)
        self.status_thread.start()

    def stop_status_thread(self):
        self.status_thread_stop = True

    def send_command(self, com, data=None):
        while self.busy:
            pass
        self.busy = True
        res = CommandAPI.send_command_immediate(
            self.connector.tunnel,
            self.token_holder,
            com,
            data,
            inc_token=True,
        )
        self.busy = False
        return res

    def set_current_thermode(self, thermode_type: enums.DEVICE_TAG):
        self.current_thermode = thermode_type

    def get_current_thermode(self) -> enums.DEVICE_TAG:
        return self.current_thermode

    def finalize(self):
        while self.busy:
            pass
        self.stop_status_thread()
        self.connector.finalize()

    def get_version(self):
        com = getVersion_command(self.current_thermode)
        res = self.send_command(com, {"name": "GetVersion", "commandId": 37})
        return self.validate_response(res)

    def get_status(self):
        com = get_status_TCU_command(self.current_thermode)
        res = self.send_command(com, {"name": "GetStatusTCU", "commandId": 33})
        return self.validate_response(res)

    def enable_thermode(self, thermode_type: enums.ThermodeType = enums.ThermodeType.TSA):
        com = enable_termode_command(self.current_thermode)
        res = self.send_command(com, {"name": "EnableTermode", "commandId": 83, "m_thermodeType": thermode_type, "m_isEnabled": True})
        return self.validate_response(res)

    def disable_thermode(self, thermode_type: enums.ThermodeType = enums.ThermodeType.TSA):
        com = enable_termode_command(self.current_thermode)
        res = self.send_command(com, {"name": "EnableTermode", "commandId": 83, "m_thermodeType": thermode_type, "m_isEnabled": False})
        return self.validate_response(res)

    def set_tcu_state(self, state: enums.SystemState, run_self_test=True, wait_for_state=False, wait_timeout=30.0):
        if wait_for_state and self.status_thread_stop:
            raise ValueError("wait_for_state requires the status thread to be running")
        start_time = time.time()
        com = set_TCU_state_command(self.current_thermode)
        res = self.send_command(com, {"name": "SetTcuState", "commandId": 41, "m_state": state, "m_runSelfTest": run_self_test})
        valid = self.validate_response(res)
        if valid and wait_for_state:
            while self.status_state != state and time.time() <= start_time + wait_timeout:
                pass
        time.sleep(0.5)
        return valid

    def get_active_thermode(self, thermode_id=enums.ThermodeType.TSA):
        if isinstance(thermode_id, enums.ThermodeType):
            thermode_id = thermode_id.value
        com = get_active_thermode_command(self.current_thermode)
        res = self.send_command(com, {"name": "GetActiveThermode", "commandId": 19, "m_thermodeId": thermode_id})
        return self.validate_response(res)

    def set_active_thermode(self, thermode_id=enums.ThermodeType.TSA):
        if isinstance(thermode_id, enums.ThermodeType):
            thermode_id = thermode_id.value
        com = set_active_thermode_command(self.current_thermode)
        res = self.send_command(com, {"name": "SetActiveThermode", "commandId": 18, "m_thermodeId": thermode_id})
        return self.validate_response(res)

    def clear_command_buffer(self):
        com = clear_command_buffer_command(self.current_thermode)
        res = self.send_command(com, {"name": "ClearCommandBuffer", "commandId": 27})
        return self.validate_response(res)

    def run_test(self, is_reset_clock=False):
        com = run_test_command(self.current_thermode)
        res = self.send_command(com, {"name": "RunTest", "commandId": 22, "m_isResetClock": is_reset_clock})
        return self.validate_response(res)

    def finite_ramp_by_temperature(
        self,
        temperature,
        low_margin,
        high_margin,
        allow_safe_duration_offset=False,
        is_wait_for_trigger=False,
        is_peak_detect=False,
        is_create_time_mark=False,
        is_dynamic_factor=False,
        is_allow_empty_buffer=True,
        ignore_kd_pid_parameter=False,
        is_stop_on_response_unit_no=False,
        is_stop_on_response_unit_yes=False,
        time=100,
    ):
        data = {
            "name": "FiniteRampByTemperature",
            "commandId": 29,
            "m_allowSafeDurationOffset": allow_safe_duration_offset,
            "m_isWaitForTrigger": is_wait_for_trigger,
            "m_isPeakDetect": is_peak_detect,
            "m_isCreateTimeMark": is_create_time_mark,
            "m_isDynamicFactor": is_dynamic_factor,
            "m_isAllowEmptyBuffer": is_allow_empty_buffer,
            "m_ignoreKdPidParameter": ignore_kd_pid_parameter,
            "m_isStopOnResponseUnitNo": is_stop_on_response_unit_no,
            "m_isStopOnResponseUnitYes": is_stop_on_response_unit_yes,
            "m_temperature": temperature,
            "m_time": time,
        }
        com = finite_ramp_by_temperature_command(self.current_thermode)
        com.m_lowMargin = low_margin
        com.m_highMargin = high_margin
        res = self.send_command(com, data=data)
        return self.validate_response(res)

    def finite_ramp_by_time(self, temperature: float, time: int, **kwargs):
        data = {
            "commandId": 28,
            "name": "FiniteRampByTime",
            "m_temperature": temperature,
            "m_time": time,
            **{f"m_{k}" if not k.startswith("m_") else k: v for k, v in kwargs.items()},
        }
        com = finite_ramp_by_time_command(self.current_thermode)
        res = self.send_command(com, data=data)
        return self.validate_response(res)

    def stop_test(self):
        com = stop_test_command(self.current_thermode)
        res = self.send_command(com, {"name": "StopTest", "commandId": 47})
        return self.validate_response(res)

    def end_test(self):
        com = end_test_command(self.current_thermode)
        res = self.send_command(com, {"name": "EndTest", "commandId": 25})
        return self.validate_response(res)

    def simulate_response_unit(self, is_yes_pressed, is_no_pressed):
        com = simulate_unit_response_command(self.current_thermode)
        res = self.send_command(com, {"name": "SimulateResponseUnit", "commandId": 45, "m_isYesPressed": is_yes_pressed, "m_isNoPressed": is_no_pressed})
        return self.validate_response(res)

    def _status_thread(self, update_rate):
        while not self.status_thread_stop:
            while self.busy:
                pass
            res = self.get_status()
            if res:
                self.event_status_updated.emit(res)
            time.sleep(update_rate)
