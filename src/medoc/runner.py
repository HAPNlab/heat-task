"""Runs a parsed Medoc experiment through MMS external control."""

from __future__ import annotations

import logging
import time

from medoc.client import MedocClient
from medoc.experiment import Experiment, ThermodeProgram
from medoc.models import TestState

logger = logging.getLogger(__name__)

_TERMINAL_STATES = {TestState.FINISHED, TestState.STOPPED}


class ExperimentRunner:
    """Drives MMS through an Experiment parsed from a .ats file.

    Programs are executed in order. Each program maps to an MMS program ID
    starting from ``start_program_id`` and incrementing by 1.

    Programs must already be loaded in MMS (e.g. imported from the .ats file)
    in the same order they appear in the Experiment.
    """

    def __init__(self, client: MedocClient, experiment: Experiment) -> None:
        self._client = client
        self._experiment = experiment

    def run(
        self,
        start_program_id: int = 0,
        poll_hz: float = 2.0,
        program_timeout: float = 3600.0,
        inter_program_delay: float = 1.0,
    ) -> None:
        """Run all programs in the experiment sequentially.

        Args:
            start_program_id: MMS ID of the first program in the experiment.
            poll_hz: How often to poll MMS status while a program runs.
            program_timeout: Max seconds to wait for a single program to finish.
            inter_program_delay: Seconds to pause between programs.
        """
        for i, program in enumerate(self._experiment.programs):
            program_id = start_program_id + i
            self._run_one(program, program_id, poll_hz, program_timeout)
            if i < len(self._experiment.programs) - 1:
                time.sleep(inter_program_delay)

    def _run_one(
        self,
        program: ThermodeProgram,
        program_id: int,
        poll_hz: float,
        timeout: float,
    ) -> None:
        logger.info("Selecting program %d: %s", program_id, program.name)
        resp = self._client.select_test(program_id)
        if resp is None:
            logger.warning("No response to SELECT_TEST for program %s — skipping", program.name)
            return

        logger.info("Starting program %s", program.name)
        self._client.start()

        interval = 1.0 / max(poll_hz, 0.1)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            resp = self._client.status()
            if resp is not None:
                try:
                    state = TestState(resp.test_state)
                except ValueError:
                    state = None
                logger.debug(
                    "Program %s — %.2f°C  test_state=%s",
                    program.name,
                    resp.temperature,
                    state.name if state else resp.test_state,
                )
                if state in _TERMINAL_STATES:
                    logger.info("Program %s finished (state=%s)", program.name, state.name)
                    return
            time.sleep(interval)

        logger.warning("Program %s timed out after %.0fs", program.name, timeout)
        self._client.stop()
