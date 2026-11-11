"""Tests for the task-driven MMS pretest (send_pretest / wait_for_pretest)."""

from __future__ import annotations

import pytest

# heat_task.task.mms imports PsychoPy (and rich) at module level; the headless CI
# job has no PsychoPy, so skip there.
pytest.importorskip("psychopy")

from rich.console import Console  # noqa: E402

from heat_task import config  # noqa: E402
from heat_task.medoc.models import MedocResponse, ReturnCode  # noqa: E402
from heat_task.medoc.models import TestState as MedocTestState  # noqa: E402
from heat_task.task import mms  # noqa: E402

RUNNING = int(MedocTestState.RUNNING)
READY = int(MedocTestState.READY)
IDLE = int(MedocTestState.IDLE)


def _response(*, test_state: int = RUNNING, return_code: int = 0) -> MedocResponse:
    return MedocResponse(
        response_length=23,
        timestamp=1000,
        command=0,
        system_state=2,
        test_state=test_state,
        return_code=return_code,
        test_time=100,
        raw_temperature=3200,
        covas=0,
        yes=0,
        no=0,
        ttl=0,
    )


def _console() -> Console:
    return Console(quiet=True)


@pytest.fixture(autouse=True)
def _pretest_timing(monkeypatch):
    monkeypatch.setattr(config, "PRETEST_POLL_S", 0.0)
    monkeypatch.setattr(config, "PRETEST_MIN_WAIT_S", 1.0)
    monkeypatch.setattr(config, "PRETEST_TIMEOUT_S", 5.0)


class _FakeClock:
    """Advances by *step* seconds on every tick, starting at 0."""

    def __init__(self, step: float) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        return self.now

    def tick(self) -> None:
        self.now += self.step


def _poll_states(monkeypatch, states):
    """Make each STATUS poll answer with the next state (None = no reply,
    OSError = connection failure); the last one repeats."""
    seq = list(states)

    def fake_send(host, port, method, *args):
        assert method == "status"
        state = seq.pop(0) if len(seq) > 1 else seq[0]
        if state is OSError:
            raise OSError("connection refused")
        return None if state is None else _response(test_state=state)

    monkeypatch.setattr(mms, "send_command", fake_send)


def _wait(clock, progress=None):
    return mms.wait_for_pretest(
        "h",
        1,
        on_tick=clock.tick,
        on_progress=(progress.append if progress is not None else lambda s: None),
        clock=clock,
    )


# ── send_pretest ──────────────────────────────────────────────────────────────


def test_send_pretest_ok(monkeypatch):
    sent = []
    monkeypatch.setattr(mms, "send_command", lambda h, p, m: sent.append(m) or _response())
    mms.send_pretest("h", 1, _console())
    assert sent == ["start"]


def test_send_pretest_error_reply_raises_with_name(monkeypatch):
    reply = _response(return_code=int(ReturnCode.WAITING_MANUAL_OPERATION))
    monkeypatch.setattr(mms, "send_command", lambda *a: reply)
    with pytest.raises(mms.PretestError, match="WAITING_MANUAL_OPERATION") as info:
        mms.send_pretest("h", 1, _console())
    assert not isinstance(info.value, mms.PretestTimeout)


def test_send_pretest_no_reply_is_tolerated(monkeypatch):
    monkeypatch.setattr(mms, "send_command", lambda *a: None)
    mms.send_pretest("h", 1, _console())


def test_send_pretest_unreachable_raises(monkeypatch):
    def refuse(*a):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(mms, "send_command", refuse)
    with pytest.raises(mms.PretestError, match="Could not reach MMS"):
        mms.send_pretest("h", 1, _console())


# ── wait_for_pretest ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("done_state", [READY, IDLE])
def test_returns_when_pretest_settles(monkeypatch, done_state):
    _poll_states(monkeypatch, [RUNNING, RUNNING, RUNNING, done_state])
    progress = []
    elapsed = _wait(_FakeClock(step=0.5), progress)
    assert elapsed == pytest.approx(2.0)
    assert progress == pytest.approx([0.5, 1.0, 1.5])


def test_ready_before_min_wait_does_not_count(monkeypatch):
    # A poll that lands before MMS has started the pretest still reads READY.
    _poll_states(monkeypatch, [READY, READY, RUNNING, READY])
    elapsed = _wait(_FakeClock(step=0.4))
    assert elapsed == pytest.approx(1.6)


def test_dropped_polls_keep_waiting(monkeypatch):
    _poll_states(monkeypatch, [None, OSError, RUNNING, READY])
    elapsed = _wait(_FakeClock(step=0.5))
    assert elapsed == pytest.approx(2.0)


def test_times_out_with_last_state(monkeypatch):
    _poll_states(monkeypatch, [RUNNING])
    with pytest.raises(mms.PretestTimeout, match="test state: RUNNING"):
        _wait(_FakeClock(step=1.0))


def test_timeout_with_no_reply_says_so(monkeypatch):
    _poll_states(monkeypatch, [None])
    with pytest.raises(mms.PretestTimeout, match="no reply"):
        _wait(_FakeClock(step=1.0))
