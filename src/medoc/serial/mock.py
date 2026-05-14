"""MockTsaDevice — in-process fake for development without hardware."""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass

from medoc.serial import enums
from medoc.serial.event import Event, TypedEvent
from medoc.serial.token_holder import TokenHolder

logger = logging.getLogger(__name__)

_TRUTHY = object()


@dataclass
class _QueuedRamp:
    target_temp: float
    duration_s: float  # real-wall-clock seconds
    token: int


@dataclass
class _MockStatus:
    """Mirrors the fields the runner reads from a real get_statusTCU_response."""
    m_executingCommandToken: int
    m_waterTemperature: float
    m_pcbTemperature: float
    m_healthStatus: int


class _MockResponse:
    command_ack_code = enums.ACKCODE.Ok

    def get_state(self):
        return enums.SystemState.TestRun.value

    def get_temp(self):
        return 35.0

    m_isResponseUnitYesOn = False
    m_isResponseUnitNoOn = False


class MockTsaDevice:
    """Drop-in replacement for TsaDevice that logs calls instead of talking to hardware."""

    def __init__(self) -> None:
        self.current_thermode = enums.DEVICE_TAG.Master
        self.busy = False
        self.status_state: enums.SystemState | None = None
        self.status_temp: float = 35.0

        self.token_holder: TokenHolder = TokenHolder()

        self._command_queue: list[_QueuedRamp] = []
        self._current_ramp: _QueuedRamp | None = None
        self._ramp_start_time: float | None = None
        self._ramp_start_temp: float = 35.0
        self._current_exec_token: int = -1

        # Simulated hardware diagnostics — updated with small noise each status tick
        self._mock_water_temp: float = 22.0
        self._mock_pcb_temp: float = 38.0
        self._last_status: _MockStatus = _MockStatus(
            m_executingCommandToken=-1,
            m_waterTemperature=self._mock_water_temp,
            m_pcbTemperature=self._mock_pcb_temp,
            m_healthStatus=0,
        )

        self._status_thread: threading.Thread | None = None
        self._stop_thread = False

        self.event_status_updated: Event = Event()
        self.event_patient_response: TypedEvent = TypedEvent(bool, bool)

    # --- lifecycle ---

    def start_status_thread(self, update_rate: float = 1.0):
        self._stop_thread = False
        self._status_thread = threading.Thread(
            target=self._run_status_thread, args=(update_rate,), daemon=True
        )
        self._status_thread.start()
        logger.debug("MockTsaDevice: status thread started")

    def stop_status_thread(self):
        self._stop_thread = True

    def finalize(self):
        self.stop_status_thread()
        logger.debug("MockTsaDevice: finalized")

    # --- commands ---

    def set_tcu_state(self, state: enums.SystemState, run_self_test=True, wait_for_state=False, wait_timeout=30.0):
        logger.debug("MockTsaDevice: set_tcu_state(%s)", state)
        self.status_state = state
        return _TRUTHY

    def finite_ramp_by_temperature(self, temperature, low_margin, high_margin, time=100, **kwargs):
        token = self.token_holder.token
        self.token_holder.token += 1
        logger.debug("MockTsaDevice: queue ramp → %.1f°C for %d ms (token %d)", temperature, time, token)
        self._command_queue.append(_QueuedRamp(target_temp=temperature, duration_s=time / 1000.0, token=token))
        return _TRUTHY

    def finite_ramp_by_time(self, temperature: float, time: int, **kwargs):
        token = self.token_holder.token
        self.token_holder.token += 1
        logger.debug("MockTsaDevice: queue ramp → %.1f°C for %d ms (token %d)", temperature, time, token)
        self._command_queue.append(_QueuedRamp(target_temp=temperature, duration_s=time / 1000.0, token=token))
        return _TRUTHY

    def run_test(self, is_reset_clock=False):
        logger.debug("MockTsaDevice: run_test() — %d commands queued", len(self._command_queue))
        self.status_state = enums.SystemState.TestRun
        self._current_ramp = None
        self._ramp_start_time = None
        self._current_exec_token = -1
        return _TRUTHY

    def stop_test(self):
        logger.debug("MockTsaDevice: stop_test()")
        self.status_state = enums.SystemState.TestInit
        self._command_queue.clear()
        self._current_ramp = None
        self._ramp_start_time = None
        self._current_exec_token = -1
        return _TRUTHY

    def end_test(self):
        logger.debug("MockTsaDevice: end_test()")
        self.status_state = enums.SystemState.RestMode
        return _TRUTHY

    def clear_command_buffer(self):
        logger.debug("MockTsaDevice: clear_command_buffer()")
        self._command_queue.clear()
        return _TRUTHY

    def enable_thermode(self, thermode_type=enums.ThermodeType.TSA):
        logger.debug("MockTsaDevice: enable_thermode(%s)", thermode_type)
        return _TRUTHY

    def get_status(self):
        return _MockResponse()

    def get_version(self):
        return _TRUTHY

    def set_current_thermode(self, thermode_type: enums.DEVICE_TAG):
        self.current_thermode = thermode_type

    def get_current_thermode(self) -> enums.DEVICE_TAG:
        return self.current_thermode

    def simulate_response_unit(self, is_yes_pressed, is_no_pressed):
        logger.debug("MockTsaDevice: simulate_response_unit(yes=%s, no=%s)", is_yes_pressed, is_no_pressed)
        return _TRUTHY

    # --- internal ---

    def _run_status_thread(self, update_rate: float):
        while not self._stop_thread:
            now = time.monotonic()

            if self.status_state == enums.SystemState.TestRun:
                # Advance to next command if needed
                if self._current_ramp is None:
                    if self._command_queue:
                        self._current_ramp = self._command_queue.pop(0)
                        self._ramp_start_time = now
                        self._ramp_start_temp = self.status_temp
                        self._current_exec_token = self._current_ramp.token
                        logger.debug(
                            "MockTsaDevice: executing ramp → %.1f°C over %.2fs (token %d)",
                            self._current_ramp.target_temp, self._current_ramp.duration_s, self._current_ramp.token,
                        )
                    else:
                        self.status_state = enums.SystemState.TestInit
                        self._current_ramp = None
                        logger.debug("MockTsaDevice: all ramps done → TestInit")

                if self._current_ramp is not None and self._ramp_start_time is not None:
                    elapsed = now - self._ramp_start_time
                    frac = min(elapsed / max(self._current_ramp.duration_s, 1e-6), 1.0)
                    target = self._current_ramp.target_temp
                    self.status_temp = round(
                        self._ramp_start_temp + (target - self._ramp_start_temp) * frac
                        + random.uniform(-0.05, 0.05),
                        2,
                    )
                    if frac >= 1.0:
                        self._current_ramp = None
                        self._ramp_start_time = None
            else:
                # Idle: drift back toward 35°C with noise
                delta = 35.0 - self.status_temp
                step = min(abs(delta), 0.3) * (1 if delta >= 0 else -1)
                self.status_temp = round(self.status_temp + step + random.uniform(-0.02, 0.02), 2)

            # Update simulated diagnostics every tick
            self._mock_water_temp = round(self._mock_water_temp + random.uniform(-0.02, 0.02), 2)
            self._mock_pcb_temp = round(self._mock_pcb_temp + random.uniform(-0.03, 0.03), 2)
            self._last_status = _MockStatus(
                m_executingCommandToken=self._current_exec_token,
                m_waterTemperature=self._mock_water_temp,
                m_pcbTemperature=self._mock_pcb_temp,
                m_healthStatus=0,
            )

            logger.debug("MockTsaDevice: temp=%.2f°C  state=%s", self.status_temp, self.status_state)
            time.sleep(update_rate)
