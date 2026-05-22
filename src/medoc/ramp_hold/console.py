"""Rich live-view table for the ramp-and-hold trial loop."""
from __future__ import annotations

from dataclasses import dataclass

import rich.box
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

_DIM = "[dim]…[/dim]"

_PHASE_LABELS: dict[str, str] = {
    "baseline": "[dim]baseline[/dim]",
    "ramp_up": "[yellow]ramp ↑[/yellow]",
    "hold": "[red]hold[/red]",
    "ramp_down": "[yellow]ramp ↓[/yellow]",
    "complete": "[green]done[/green]",
}


@dataclass
class _RowData:
    trial_label: str
    baseline_str: str
    target_str: str
    rating_str: str = _DIM
    rt_str: str = _DIM


def _make_table(rows: list[_RowData]) -> Table:
    t = Table(box=rich.box.SIMPLE_HEAD)
    t.add_column("#", justify="right")
    t.add_column("Baseline", justify="right")
    t.add_column("Target", justify="right")
    t.add_column("Rating", justify="right")
    t.add_column("RT", justify="right")
    for r in rows:
        t.add_row(
            r.trial_label,
            r.baseline_str,
            r.target_str,
            r.rating_str,
            r.rt_str,
        )
    return t


class TrialLiveView:
    """Rich Live view with a status line (live temp) above the per-trial table."""

    def __init__(self, console: Console, n_trials: int) -> None:
        self._n_trials = n_trials
        self._live = Live(console=console, auto_refresh=False, vertical_overflow="visible")
        self._rows: list[_RowData] = []
        self._current: _RowData | None = None
        self._status = Text("")

    def __enter__(self) -> TrialLiveView:
        self._live.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._live.__exit__(*args)

    def start_trial(self, trial_n: int, baseline: float, target_temp: float) -> None:
        self._current = _RowData(
            trial_label=f"{trial_n}/{self._n_trials}",
            baseline_str=f"{baseline:.1f}°C",
            target_str=f"{target_temp:.1f}°C",
        )
        self._rows.append(self._current)
        self._refresh()

    def on_sample(self, temperature: float, phase: str) -> None:
        if self._current is None:
            return
        phase_label = _PHASE_LABELS.get(phase, phase)
        self._status = Text.from_markup(
            f"Temp: [bold cyan]{temperature:.2f}°C[/bold cyan]  Phase: {phase_label}"
        )
        self._refresh()

    def on_rating(self, rating: float | str, rt_ms: float | str, timed_out: bool) -> None:
        r = self._current
        if r is None:
            return
        if timed_out:
            r.rating_str = "[dim]timeout[/dim]"
            r.rt_str = "—"
        else:
            r.rating_str = f"[cyan]{float(rating):.1f}[/cyan]" if rating != "" else "—"
            r.rt_str = f"{rt_ms:.0f} ms" if isinstance(rt_ms, float) else "—"
        self._refresh()

    def _refresh(self) -> None:
        self._live.update(Group(self._status, _make_table(self._rows)))
        self._live.refresh()
