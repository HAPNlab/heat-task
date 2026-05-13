"""Tests for the experiment runner's mapping of .ats sequences to device calls."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from medoc.experiment import RampAndHoldSequence, ThermodeProgram, Experiment
from medoc.runner import ExperimentRunner


def _make_seq(
    baseline=35.0,
    destination=46.0,
    dest_rate=4.5,
    return_rate=4.5,
    duration_ms=30_000,
    trials=1,
    number=1,
) -> RampAndHoldSequence:
    return RampAndHoldSequence(
        number=number,
        trials=trials,
        baseline_temp=baseline,
        destination_temp=destination,
        destination_rate=dest_rate,
        return_rate=return_rate,
        duration_ms=duration_ms,
        time_before_ms=0,
        inter_trials_min_ms=0,
        inter_trials_max_ms=0,
    )


def _make_device():
    dev = MagicMock()
    dev.status_state = None
    dev.status_temp = 35.0
    return dev


class TestSequenceToDeviceCalls:
    def test_single_sequence_single_trial_call_count(self):
        """One trial → three finite_ramp_by_temperature calls: ramp up, hold, return."""
        seq = _make_seq(baseline=35.0, destination=46.0, dest_rate=4.5, return_rate=4.5, duration_ms=30_000)
        prog = ThermodeProgram(name="Test", sequences=(seq,))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        assert device.finite_ramp_by_temperature.call_count == 3

    def test_ramp_up_time_calculation(self):
        """Ramp-up time = |dest - baseline| / rate * 1000 ms."""
        seq = _make_seq(baseline=35.0, destination=46.0, dest_rate=4.5)
        prog = ThermodeProgram(name="Test", sequences=(seq,))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        calls = device.finite_ramp_by_temperature.call_args_list
        ramp_up_call = calls[0]
        expected_time = int(abs(46.0 - 35.0) / 4.5 * 1000)
        assert ramp_up_call.kwargs["time"] == expected_time or ramp_up_call.args[3] == expected_time

    def test_hold_at_destination(self):
        """Second call is a hold: destination temp, duration_ms as time."""
        seq = _make_seq(baseline=35.0, destination=46.0, duration_ms=30_000)
        prog = ThermodeProgram(name="Test", sequences=(seq,))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        calls = device.finite_ramp_by_temperature.call_args_list
        hold_call = calls[1]
        # The hold should target the destination temperature
        temp_arg = hold_call.args[0] if hold_call.args else hold_call.kwargs.get("temperature")
        assert temp_arg == pytest.approx(46.0)

    def test_return_to_baseline(self):
        """Third call returns to baseline temperature."""
        seq = _make_seq(baseline=35.0, destination=46.0)
        prog = ThermodeProgram(name="Test", sequences=(seq,))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        calls = device.finite_ramp_by_temperature.call_args_list
        return_call = calls[2]
        temp_arg = return_call.args[0] if return_call.args else return_call.kwargs.get("temperature")
        assert temp_arg == pytest.approx(35.0)

    def test_two_trials_six_calls(self):
        """Two trials → six finite_ramp_by_temperature calls."""
        seq = _make_seq(trials=2)
        prog = ThermodeProgram(name="Test", sequences=(seq,))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        assert device.finite_ramp_by_temperature.call_count == 6

    def test_two_sequences_six_calls(self):
        """Two sequences × 1 trial each → six calls total."""
        seq1 = _make_seq(destination=46.0, number=1)
        seq2 = _make_seq(destination=47.0, number=2)
        prog = ThermodeProgram(name="Test", sequences=(seq1, seq2))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        assert device.finite_ramp_by_temperature.call_count == 6

    def test_run_test_called_per_program(self):
        prog = ThermodeProgram(name="Test", sequences=(_make_seq(),))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        device.run_test.assert_called_once()

    def test_stop_test_called_per_program(self):
        prog = ThermodeProgram(name="Test", sequences=(_make_seq(),))
        experiment = Experiment(programs=(prog,))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        device.stop_test.assert_called_once()

    def test_two_programs_run_test_called_twice(self):
        prog1 = ThermodeProgram(name="P1", sequences=(_make_seq(),))
        prog2 = ThermodeProgram(name="P2", sequences=(_make_seq(),))
        experiment = Experiment(programs=(prog1, prog2))
        device = _make_device()

        runner = ExperimentRunner(device, experiment)
        runner.run()

        assert device.run_test.call_count == 2
