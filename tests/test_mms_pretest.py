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


BASELINE = 32.0


def _response(
    *, test_state: int = RUNNING, return_code: int = 0, temp: float = BASELINE
) -> MedocResponse:
    return MedocResponse(
        response_length=23,
        timestamp=1000,
        command=0,
        system_state=2,
        test_state=test_state,
        return_code=return_code,
        test_time=100,
        raw_temperature=round(temp * 100),
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
    monkeypatch.setattr(config, "BASELINE_TOLERANCE", 0.4)
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


def _poll_states(monkeypatch, replies):
    """Make each STATUS poll answer with the next reply: a (state, temp) pair,
    None for no reply, or OSError for a connection failure. The last repeats."""
    seq = list(replies)

    def fake_send(host, port, method, *args):
        assert method == "status"
        reply = seq.pop(0) if len(seq) > 1 else seq[0]
        if reply is OSError:
            raise OSError("connection refused")
        if reply is None:
            return None
        state, temp = reply
        return _response(test_state=state, temp=temp)

    monkeypatch.setattr(mms, "send_command", fake_send)


def _wait(clock, progress=None):
    return mms.wait_for_pretest(
        "h",
        1,
        BASELINE,
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


def test_done_on_first_poll_when_already_at_baseline(monkeypatch):
    _poll_states(monkeypatch, [(RUNNING, BASELINE)])
    progress = []
    assert _wait(_FakeClock(step=0.5), progress) == pytest.approx(0.5)
    assert progress == []


def test_waits_for_the_thermode_to_reach_baseline(monkeypatch):
    _poll_states(monkeypatch, [(RUNNING, 30.0), (RUNNING, 31.0), (RUNNING, 31.7)])
    progress = []
    assert _wait(_FakeClock(step=0.5), progress) == pytest.approx(1.5)
    assert progress == pytest.approx([0.5, 1.0])


@pytest.mark.parametrize("state", [READY, IDLE])
def test_not_done_until_running(monkeypatch, state):
    # At baseline before MMS has started the pretest doesn't count.
    _poll_states(monkeypatch, [(state, BASELINE), (RUNNING, BASELINE)])
    assert _wait(_FakeClock(step=0.5)) == pytest.approx(1.0)


def test_dropped_polls_keep_waiting(monkeypatch):
    _poll_states(monkeypatch, [None, OSError, (RUNNING, BASELINE)])
    assert _wait(_FakeClock(step=0.5)) == pytest.approx(1.5)


def test_times_out_with_last_reading(monkeypatch):
    _poll_states(monkeypatch, [(RUNNING, 30.0)])
    with pytest.raises(mms.PretestTimeout, match="test state RUNNING, 30.00 °C"):
        _wait(_FakeClock(step=1.0))


def test_timeout_with_no_reply_says_so(monkeypatch):
    _poll_states(monkeypatch, [None])
    with pytest.raises(mms.PretestTimeout, match="no reply"):
        _wait(_FakeClock(step=1.0))
