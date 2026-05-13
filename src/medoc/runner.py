"""Runs a parsed Medoc experiment through the TSA2 serial API."""

from __future__ import annotations

import logging
import time

from medoc.experiment import Experiment, ThermodeProgram
from medoc.serial.enums import SystemState

logger = logging.getLogger(__name__)

_DEFAULT_MARGIN = 0.5


class ExperimentRunner:
    """Drives a TsaDevice (or MockTsaDevice) through an Experiment parsed from a .ats file."""

    def __init__(self, device, experiment: Experiment) -> None:
        self._device = device
        self._experiment = experiment

    def run(
        self,
        poll_hz: float = 2.0,
        program_timeout: float = 3600.0,
        inter_program_delay: float = 1.0,
        margin: float = _DEFAULT_MARGIN,
    ) -> None:
        for i, program in enumerate(self._experiment.programs):
            self._run_one(program, poll_hz, program_timeout, margin)
            if i < len(self._experiment.programs) - 1:
                time.sleep(inter_program_delay)

    def _run_one(
        self,
        program: ThermodeProgram,
        poll_hz: float,
        timeout: float,
        margin: float,
    ) -> None:
        logger.info("Starting program: %s", program.name)
        self._device.set_tcu_state(SystemState.TestInit, wait_for_state=True)

        for seq in program.sequences:
            ramp_ms = int(abs(seq.destination_temp - seq.baseline_temp) / seq.destination_rate * 1000)
            return_ms = int(abs(seq.destination_temp - seq.baseline_temp) / seq.return_rate * 1000)

            for trial in range(seq.trials):
                logger.debug(
                    "  seq %d trial %d/%d: %.1f°C → %.1f°C (ramp %dms, hold %dms, return %dms)",
                    seq.number, trial + 1, seq.trials,
                    seq.baseline_temp, seq.destination_temp,
                    ramp_ms, seq.duration_ms, return_ms,
                )
                self._device.finite_ramp_by_temperature(
                    seq.destination_temp, margin, margin, time=ramp_ms
                )
                self._device.finite_ramp_by_temperature(
                    seq.destination_temp, margin, margin, time=seq.duration_ms
                )
                self._device.finite_ramp_by_temperature(
                    seq.baseline_temp, margin, margin, time=return_ms
                )

        self._device.run_test()

        interval = 1.0 / max(poll_hz, 0.1)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._device.status_state not in (None, SystemState.TestRun):
                break
            time.sleep(interval)
        else:
            logger.warning("Program %s timed out after %.0fs", program.name, timeout)

        self._device.stop_test()
        logger.info("Program %s complete", program.name)
