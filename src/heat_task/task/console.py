"""Rich live-view table for the ramp-and-hold sequence loop."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import rich.box
from psychopy import core
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

from heat_task.task.phase_tracker import Phase

_DIM = "[dim]…[/dim]"

_BLINK_INTERVAL_S = 0.4

# Minimum gap between sample-driven repaints. Samples arrive in bursts; redrawing
# the whole Live region on each one causes visible flicker, so throttle to a
# steady rate (meaningful events still force an immediate repaint).
_MIN_REFRESH_INTERVAL_S = 0.1

# How long without a new MMS sample before the data is flagged as frozen.
_FREEZE_AFTER_S = 0.5

# Trailing window over which latency is averaged and its peak tracked.
_LATENCY_WINDOW_S = 2.0


def _styled(text: str, style: str) -> str:
    """Wrap text in a Rich markup style tag."""
    return f"[{style}]{text}[/{style}]"


def _latency_style(ms: float) -> str:
    if ms < 150:
        return "green"
    if ms < 500:
        return "yellow"
    return "red"


def _fmt_latency(ms: float) -> str:
    """Format a latency value, colour-coded by severity."""
    text = f"{ms:.0f}ms" if ms < 1000 else f"{ms / 1000:.1f}s"
    return _styled(text, _latency_style(ms))


# Plain name and Rich style for each phase, in one place so the label and the
# padding width can't drift apart.
_PHASE_DISPLAY: dict[Phase, tuple[str, str]] = {
    Phase.BASELINE: ("baseline", "dim"),
    Phase.RAMP_UP: ("ramp ↑", "yellow"),
    Phase.HOLD: ("hold", "red"),
    Phase.RAMP_DOWN: ("ramp ↓", "yellow"),
    Phase.COMPLETE: ("done", "green"),
}
_PHASE_WIDTH = max(len(name) for name, _ in _PHASE_DISPLAY.values())


def _render_phase(phase: Phase) -> str:
    """Styled phase label, right-padded to the widest plain name so the status
    line after the phase column stays put as the phase changes."""
    name, style = _PHASE_DISPLAY[phase]
    return _styled(name, style) + " " * (_PHASE_WIDTH - len(name))


@dataclass
class _RowData:
    seq_label: str
    baseline_str: str
    target_str: str
    rating_str: str = _DIM
    flag_str: str = ""


def _make_table(rows: list[_RowData]) -> Table:
    t = Table(box=rich.box.SIMPLE_HEAD)
    t.add_column("#", justify="right")
    t.add_column("Baseline", justify="right")
    t.add_column("Target", justify="right")
    t.add_column("Rating", justify="right")
    t.add_column("", justify="left")
    for r in rows:
        t.add_row(
            r.seq_label,
            r.baseline_str,
            r.target_str,
            r.rating_str,
            r.flag_str,
        )
    return t


class SequenceLiveView:
    """Rich Live view with a status line (live temp) above the per-sequence table."""

    def __init__(self, console: Console, n_sequences: int) -> None:
        self._n_sequences = n_sequences
        self._live = Live(console=console, auto_refresh=False, vertical_overflow="visible")
        self._rows: list[_RowData] = []
        self._current: _RowData | None = None
        self._temp: float | None = None
        self._phase: Phase | None = None
        self._blink_on = True
        self._blink_t = core.monotonicClock.getTime()
        self._last_refresh_t = 0.0
        self._last_sample_t: float | None = None
        self._latency_window: deque[tuple[float, float]] = deque()
        self._net_event_count = 0

    def __enter__(self) -> SequenceLiveView:
        self._live.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._live.__exit__(*args)

    def start_sequence(self, sequence_n: int, baseline: float, target_temp: float) -> None:
        row = _RowData(
            seq_label=f"{sequence_n}/{self._n_sequences}",
            baseline_str=f"{baseline:.1f}°C",
            target_str=f"{target_temp:.1f}°C",
        )
        self._current = row
        self._rows.append(row)
        self._refresh(force=True)

    def on_sample(self, temperature: float, phase: Phase, latency_ms: float) -> None:
        if self._current is None:
            return
        now = core.monotonicClock.getTime()
        self._latency_window.append((now, latency_ms))
        self._last_sample_t = now
        self._temp = temperature
        self._phase = phase
        self._refresh()

    def on_net_event(self) -> None:
        """Record a status-poll failure (timeout/reconnect) for the live chip."""
        self._net_event_count += 1
        self._refresh(force=True)

    def tick(self) -> None:
        """Advance the blink and repaint, independent of MMS sample arrival.

        Called every frame from the render loop so the ``● Live`` heartbeat keeps
        pulsing (and the console stays repainted) even during gaps in MMS polling
        — the blink reflects render-loop liveness, not sample timing.
        """
        self._refresh()

    def on_rating(self, rating: float, no_response: bool) -> None:
        r = self._current
        if r is None:
            return
        r.rating_str = _styled(f"{float(rating):.0f}", "cyan")
        r.flag_str = _styled("⚑ no resp", "yellow") if no_response else ""
        self._refresh(force=True)

    def _blink_dot(self, now: float) -> str:
        """The pulsing ``●`` heartbeat; toggled on its own interval clock."""
        if now - self._blink_t >= _BLINK_INTERVAL_S:
            self._blink_on = not self._blink_on
            self._blink_t = now
        return _styled("●", "bold green") if self._blink_on else " "

    def _render_status(self) -> Text:
        now = core.monotonicClock.getTime()
        running = f"{self._blink_dot(now)} [green]Running[/green]"
        if self._temp is None or self._phase is None:
            first_line = f"{running}  [dim]Waiting for MMS…[/dim]"
        else:
            first_line = (
                f"{running}  Temp: [bold cyan]{self._temp:.2f}°C[/bold cyan]  "
                f"Phase: {_render_phase(self._phase)}"
            )
        return Text.from_markup(f"{first_line}\n{self._latency_markup(now).strip()}")

    def _latency_markup(self, now: float) -> str:
        """Latency chip: windowed average + peak, plus a freeze timer if stalled."""
        while self._latency_window and now - self._latency_window[0][0] > _LATENCY_WINDOW_S:
            self._latency_window.popleft()
        chip = ""
        if self._latency_window:
            values = [ms for _, ms in self._latency_window]
            avg = sum(values) / len(values)
            peak = max(values)
            chip = f"  [dim]latency[/dim] {_fmt_latency(avg)} avg"
            if peak >= avg + 1:  # only show a peak when it differs meaningfully
                chip += f" · {_fmt_latency(peak)} peak"
        if self._last_sample_t is not None:
            frozen_s = now - self._last_sample_t
            if frozen_s >= _FREEZE_AFTER_S:
                chip += " " + _styled(f"(frozen {frozen_s:.1f}s)", "red")
        if self._net_event_count:
            chip += "  " + _styled(f"drops {self._net_event_count}", "yellow")
        return chip

    def _refresh(self, force: bool = False) -> None:
        now = core.monotonicClock.getTime()
        # Not a wait — a throttle. We return immediately (no sleep, nothing
        # blocks) when the last repaint was under _MIN_REFRESH_INTERVAL_S ago, so
        # bursts of samples coalesce into a steady redraw rate without flicker.
        if not force and now - self._last_refresh_t < _MIN_REFRESH_INTERVAL_S:
            return
        self._last_refresh_t = now
        self._live.update(Group(self._render_status(), _make_table(self._rows)))
        self._live.refresh()
