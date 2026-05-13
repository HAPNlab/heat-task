"""Serial command encoding tests ported from unittest_command.py.

Each test has a hardcoded expected byte array from Medoc's original test suite.
These are ground truth for the wire protocol — if any of these fail after the
migration, the command encoding is broken.
"""

from __future__ import annotations

import pytest

from medoc.serial import enums
from medoc.serial.commands.m_clear_command_buffer import clear_command_buffer_command
from medoc.serial.commands.m_end_test_command import end_test_command
from medoc.serial.commands.m_finite_ramp_by_temperature_command import finite_ramp_by_temperature_command
from medoc.serial.commands.m_finite_ramp_by_time_command import finite_ramp_by_time_command
from medoc.serial.commands.m_getVersion_command import getVersion_command
from medoc.serial.commands.m_getstatusTCU_command import get_status_TCU_command
from medoc.serial.commands.m_run_test import run_test_command
from medoc.serial.commands.m_set_TCU_state import set_TCU_state_command
from medoc.serial.commands.m_simulate_response_unit import simulate_unit_response_command
from medoc.serial.commands.m_stop_test_command import stop_test_command


class TestGetVersionCommand:
    def test_encoding(self):
        expected = [73, 0, 8, 37, 0, 0, 0, 1, 0]
        com = getVersion_command()
        com.command_token = 1
        com.command_id = enums.COMMAND_ID["GetVersion"]
        com.to_bytes()
        assert com.command_array == expected


class TestSetTcuStateCommand:
    def test_rest_mode(self):
        expected = [0xAA, 0x0, 0xA, 0x29, 0x0, 0x0, 0x5, 0xC1, 0x0, 0x2, 0x1, 0x0]
        com = set_TCU_state_command()
        com.command_token = 0x5C1
        com.command_id = enums.COMMAND_ID["SetTcuState"]
        com.m_state = enums.SystemState["RestMode"]
        com.to_bytes()
        assert com.command_array == expected


class TestClearCommandBufferCommand:
    def test_encoding(self):
        expected = [0xEC, 0x0, 0x8, 0x1B, 0x0, 0x0, 0x9, 0xFA, 0x0]
        com = clear_command_buffer_command()
        com.command_token = 0x9FA
        com.command_id = enums.COMMAND_ID["ClearCommandBuffer"]
        com.to_bytes()
        assert com.command_array == expected


class TestRunTestCommand:
    def test_reset_clock_true(self):
        expected = [0xF, 0x0, 0x9, 0x16, 0x0, 0x0, 0xA, 0x0, 0x0, 0x1, 0x0]
        com = run_test_command()
        com.command_token = 0xA00
        com.command_id = enums.COMMAND_ID["RunTest"]
        com.m_isResetClock = True
        com.to_bytes()
        assert com.command_array == expected


class TestFiniteRampByTimeCommand:
    def test_encoding(self):
        expected = [
            0xCB, 0x0, 0x11, 0x1C, 0x0, 0x0, 0x11, 0xD5, 0x0,
            0xC, 0x80, 0x0, 0x0, 0x0, 0x64, 0x80, 0x0, 0x0, 0x0,
        ]
        com = finite_ramp_by_time_command()
        com.command_token = 4565
        com.command_id = enums.COMMAND_ID["FiniteRampByTime"]
        com.m_temperature = 32
        com.m_time = 100
        com.m_isWaitForTrigger = False
        com.m_isPeakDetect = False
        com.m_isCreateTimeMark = False
        com.m_isUseTimeMark = False
        com.m_isDynamicFactor = False
        com.m_isAllowEmptyBuffer = True
        com.m_isIgnoreKdPidParameter = False
        com.m_allowSafeDurationOffset = None
        com.m_isStopOnResponseUnitYes = False
        com.m_isStopOnResponseUnitNo = False
        com.to_bytes()
        assert com.command_array == expected


class TestFiniteRampByTemperatureCommand:
    def test_encoding(self):
        expected = [
            0xBC, 0x0, 0x15, 0x1D, 0x0, 0x0, 0x22, 0xA4, 0x0,
            0xD, 0x48, 0x0, 0xA, 0x0, 0x14, 0x0, 0x0, 0x0, 0x9A,
            0xA0, 0x0, 0x0, 0x0,
        ]
        com = finite_ramp_by_temperature_command()
        com.command_token = 8868
        com.command_id = enums.COMMAND_ID["FiniteRampByTemperature"]
        com.m_temperature = 34
        com.m_time = 154
        com.m_isWaitForTrigger = False
        com.m_isPeakDetect = False
        com.m_isCreateTimeMark = False
        com.m_isDynamicFactor = False
        com.m_isAllowEmptyBuffer = True
        com.m_ignoreKdPidParameter = True
        com.m_allowSafeDurationOffset = None
        com.m_lowMargin = 0.10000000000000001
        com.m_highMargin = 0.20000000000000001
        com.to_bytes()
        assert com.command_array == expected


class TestStopTestCommand:
    def test_encoding(self):
        expected = [0x25, 0x0, 0x8, 0x2F, 0x0, 0x0, 0xC, 0x67, 0x0]
        com = stop_test_command()
        com.command_token = 3175
        com.command_id = enums.COMMAND_ID["StopTest"]
        com.to_bytes()
        assert com.command_array == expected


class TestEndTestCommand:
    def test_encoding(self):
        expected = [0x68, 0x0, 0x8, 0x19, 0x0, 0x0, 0xD, 0xE8, 0x0]
        com = end_test_command()
        com.command_token = 3560
        com.command_id = enums.COMMAND_ID["EndTest"]
        com.to_bytes()
        assert com.command_array == expected


class TestSimulateResponseUnitCommand:
    def test_encoding(self):
        expected = [0x70, 0x0, 0x9, 0x2D, 0x0, 0x0, 0x48, 0x89, 0x0, 0x0, 0x0]
        com = simulate_unit_response_command()
        com.command_token = 18569
        com.command_id = enums.COMMAND_ID["SimulateResponseUnit"]
        com.m_isYesPressed = False
        com.m_isNoPressed = False
        com.to_bytes()
        assert com.command_array == expected


class TestGetStatusTcuCommand:
    def test_encoding(self):
        expected = [0xE, 0x0, 0x8, 0x21, 0x0, 0x0, 0x48, 0x8B, 0x0]
        com = get_status_TCU_command()
        com.command_token = 18571
        com.command_id = enums.COMMAND_ID["GetStatusTCU"]
        com.to_bytes()
        assert com.command_array == expected
