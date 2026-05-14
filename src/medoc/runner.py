"""Runs a parsed Medoc experiment through the TSA2 serial API."""

from __future__ import annotations

import logging
import random
import time
from collections import deque

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from medoc.experiment import Experiment, ThermodeProgram
from medoc.serial.enums import SystemState

logger = logging.getLogger(__name__)

_DEFAULT_MARGIN = 0.5

_STATE_STYLE = {
    SystemState.TestRun: "bold green",
    SystemState.TestInit: "cyan",
    SystemState.RestMode: "dim",
    SystemState.SafeMode: "bold red",
    SystemState.SelfTest: "yellow",
}

_BAR_WIDTH = 20


class ExperimentRunner:
    """Drives a TsaDevice (or MockTsaDevice) through an Experiment parsed from a .ats file."""

    def __init__(self, device, experiment: Experiment) -> None:
        self._device = device
        self._experiment = experiment
        self._console = Console()
        # rolling (monotonic_time, temp) pairs for rate / activity
        self._temp_history: deque[tuple[float, float]] = deque(maxlen=10)

    def run(
        self,
        poll_hz: float = 2.0,
        program_timeout: float = 3600.0,
        margin: float = _DEFAULT_MARGIN,
        program_index: int | None = None,
    ) -> None:
        program = (
            self._experiment.programs[program_index]
            if program_index is not None
            else self._experiment.programs[0]
        )
        with Live(console=self._console, refresh_per_second=4, transient=False) as live:
            self._temp_history.clear()
            self._run_one(program, poll_hz, program_timeout, margin, live, 1, 1)

    def _run_one(
        self,
        program: ThermodeProgram,
        poll_hz: float,
        timeout: float,
        margin: float,
        live: Live,
        prog_idx: int,
        total_progs: int,
    ) -> None:
        logger.info("Starting program: %s", program.name)

        total_trials = sum(seq.trials for seq in program.sequences)
        total_duration_s = (
            sum(
                seq.time_before_ms / 1000.0
                + seq.trials * (
                    abs(seq.destination_temp - seq.baseline_temp) / seq.destination_rate
                    + seq.duration_ms / 1000.0
                    + abs(seq.destination_temp - seq.baseline_temp) / seq.return_rate
                )
                for seq in program.sequences
            )
            # ISI fires between every consecutive trial pair (total_trials - 1 gaps)
            + max(0, total_trials - 1) * (
                sum(
                    (seq.inter_trials_min_ms + seq.inter_trials_max_ms) / 2 * seq.trials
                    for seq in program.sequences
                ) / max(total_trials, 1) / 1000.0
            )
        )
        has_isi = lambda s: s.inter_trials_min_ms > 0 or s.inter_trials_max_ms > 0
        has_response = lambda s: s.waiting_time_for_response_ms > 0
        # Representative ISI gap counts (one per inter-trial gap)
        total_commands = (
            sum(
                (1 if seq.time_before_ms > 0 else 0) + seq.trials * 3
                for seq in program.sequences
            )
            + max(0, total_trials - 1) * (
                (1 if any(has_response(s) for s in program.sequences) else 0)
                + (1 if any(has_isi(s) for s in program.sequences) else 0)
            )
        )

        live.update(self._make_panel(
            program.name, prog_idx, total_progs, 0, total_duration_s,
            total_commands=total_commands, status="Initialising…",
        ))
        self._device.set_tcu_state(SystemState.TestInit, wait_for_state=True)

        sequences = self._apply_randomization(list(program.sequences), program.randomize_sequences)

        # Flatten to (seq, trial_index, is_first_in_seq, has_next_trial) tuples so the
        # ISI fires between ALL consecutive trials, including across sequence boundaries.
        all_trials: list[tuple] = []
        for seq in sequences:
            for t in range(seq.trials):
                all_trials.append((seq, t, t == 0))

        for idx, (seq, trial, is_first_in_seq) in enumerate(all_trials):
            has_next = idx < len(all_trials) - 1
            ramp_ms = int(abs(seq.destination_temp - seq.baseline_temp) / seq.destination_rate * 1000)
            return_ms = int(abs(seq.destination_temp - seq.baseline_temp) / seq.return_rate * 1000)
            is_ttl_trigger = seq.trigger == 1
            use_time_criterion = seq.destination_criterion == 1
            end_to_onset = seq.inter_trials_time_option == 1

            # Hold at baseline before the first trial of this sequence
            if is_first_in_seq and seq.time_before_ms > 0:
                logger.debug("  seq %d: time-before hold %d ms", seq.number, seq.time_before_ms)
                self._device.finite_ramp_by_temperature(
                    seq.baseline_temp, margin, margin, time=seq.time_before_ms
                )

            logger.debug(
                "  seq %d trial %d/%d: %.1f°C → %.1f°C (ramp %dms, hold %dms, return %dms)",
                seq.number, trial + 1, seq.trials,
                seq.baseline_temp, seq.destination_temp,
                ramp_ms, seq.duration_ms, return_ms,
            )

            # Ramp to destination — onset time mark + optional TTL trigger wait
            if use_time_criterion:
                self._device.finite_ramp_by_time(
                    seq.destination_temp, time=ramp_ms,
                    is_wait_for_trigger=is_ttl_trigger,
                    is_create_time_mark=seq.mark_onset,
                )
            else:
                self._device.finite_ramp_by_temperature(
                    seq.destination_temp, margin, margin, time=ramp_ms,
                    is_wait_for_trigger=is_ttl_trigger,
                    is_create_time_mark=seq.mark_onset,
                )

            # Hold at destination — destination time mark
            self._device.finite_ramp_by_temperature(
                seq.destination_temp, margin, margin, time=seq.duration_ms,
                is_create_time_mark=seq.mark_destination,
            )

            # Return to baseline — end-of-duration time mark
            self._device.finite_ramp_by_temperature(
                seq.baseline_temp, margin, margin, time=return_ms,
                is_create_time_mark=seq.mark_end_of_duration,
            )

            # ISI between this trial and the next (including across sequence boundaries)
            if has_next:
                isi_ms = random.randint(
                    seq.inter_trials_min_ms,
                    max(seq.inter_trials_min_ms, seq.inter_trials_max_ms),
                )
                if end_to_onset:
                    response_ms = min(seq.waiting_time_for_response_ms, isi_ms)
                    rest_ms = isi_ms - response_ms
                else:
                    # Onset-to-Onset: subtract time already elapsed in this trial
                    trial_ms = ramp_ms + seq.duration_ms + return_ms
                    response_ms = seq.waiting_time_for_response_ms
                    rest_ms = max(0, isi_ms - trial_ms - response_ms)

                if response_ms > 0:
                    logger.debug("  seq %d: response window %d ms", seq.number, response_ms)
                    self._device.finite_ramp_by_temperature(
                        seq.baseline_temp, margin, margin, time=response_ms,
                        is_create_time_mark=seq.mark_end_of_trial,
                        is_stop_on_response_unit_yes=True,
                        is_stop_on_response_unit_no=True,
                    )
                if rest_ms > 0:
                    logger.debug("  seq %d: ISI remainder %d ms", seq.number, rest_ms)
                    self._device.finite_ramp_by_temperature(
                        seq.baseline_temp, margin, margin, time=rest_ms,
                    )

        self._device.run_test()

        interval = 1.0 / max(poll_hz, 0.1)
        deadline = time.monotonic() + timeout
        start = time.monotonic()
        while time.monotonic() < deadline:
            elapsed = time.monotonic() - start
            live.update(self._make_panel(
                program.name, prog_idx, total_progs, elapsed, total_duration_s,
                total_commands=total_commands,
            ))
            if self._device.status_state not in (None, SystemState.TestRun):
                break
            time.sleep(interval)
        else:
            logger.warning("Program %s timed out after %.0fs", program.name, timeout)

        self._device.stop_test()
        elapsed = time.monotonic() - start
        live.update(self._make_panel(
            program.name, prog_idx, total_progs, elapsed, total_duration_s,
            total_commands=total_commands, status="Complete",
        ))
        logger.info("Program %s complete", program.name)

    # ------------------------------------------------------------------

    @staticmethod
    def _apply_randomization(sequences: list, randomize_all: bool) -> list:
        if randomize_all:
            random.shuffle(sequences)
            return sequences
        # Pair-wise randomisation: swap each adjacent pair where the first has randomize_with_next set
        i = 0
        while i < len(sequences) - 1:
            if sequences[i].randomize_with_next and random.random() < 0.5:
                sequences[i], sequences[i + 1] = sequences[i + 1], sequences[i]
            i += 2
        return sequences

    def _rate_and_activity(self, temp: float) -> tuple[str, Text]:
        now = time.monotonic()
        self._temp_history.append((now, temp))

        if len(self._temp_history) < 4:
            return "—", Text("—", style="dim")

        t0, tmp0 = self._temp_history[0]
        t1, tmp1 = self._temp_history[-1]
        dt = t1 - t0
        if dt < 0.1:
            return "—", Text("—", style="dim")

        rate = (tmp1 - tmp0) / dt  # °C/s
        rate_str = f"{rate:+.2f} °C/s"

        if rate > 0.3:
            return rate_str, Text("Heating ↑", style="bold red")
        if rate < -0.3:
            return rate_str, Text("Cooling ↓", style="bold blue")
        return rate_str, Text("Maintaining", style="green")

    def _make_panel(
        self,
        program_name: str,
        prog_idx: int,
        total_progs: int,
        elapsed: float,
        total_duration_s: float,
        *,
        total_commands: int,
        status: str | None = None,
    ) -> Panel:
        state = self._device.status_state
        temp = self._device.status_temp

        rate_str, activity_text = self._rate_and_activity(temp)

        # Progress bar
        if total_duration_s > 0:
            frac = min(elapsed / total_duration_s, 1.0)
        else:
            frac = 0.0
        filled = int(_BAR_WIDTH * frac)
        bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
        remaining_s = max(total_duration_s - elapsed, 0.0)
        progress_str = f"{bar}  {frac * 100:.0f}%  (~{remaining_s:.0f}s left)"

        # Temperature + target
        target = getattr(self._device, "status_target_temp", None)
        if target is not None:
            temp_str = f"{temp:.2f}°C  →  {target:.1f}°C"
        else:
            temp_str = f"{temp:.2f}°C"

        state_text = Text(str(state.name) if state else "—", style=_STATE_STYLE.get(state, ""))

        rows: list[tuple[str, str | Text]] = [
            ("Program", f"{prog_idx}/{total_progs}  {program_name}"),
            ("Progress", progress_str),
            ("State", state_text),
            ("Activity", activity_text),
            ("Rate", rate_str),
            ("Temperature", temp_str),
        ]

        raw = getattr(self._device, "_last_status", None)
        if raw is not None:
            if getattr(raw, "m_waterTemperature", None):
                rows.append(("Water temp", f"{raw.m_waterTemperature:.2f}°C"))
            if getattr(raw, "m_pcbTemperature", None):
                rows.append(("PCB temp", f"{raw.m_pcbTemperature:.2f}°C"))
            if getattr(raw, "m_healthStatus", None) is not None:
                rows.append(("Health", hex(raw.m_healthStatus)))

        if status:
            rows.append(("", Text(status, style="italic dim")))

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold dim", justify="right")
        grid.add_column()
        for label, value in rows:
            grid.add_row(label, value)

        return Panel(grid, title="[bold]TSA2 Status[/bold]", border_style="blue", expand=False)
