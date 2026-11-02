"""Tests for confirming that START actually started the MMS test."""

from __future__ import annotations

import pytest

# heat_task.task.mms imports PsychoPy (and rich) at module level; the headless CI
# job installs neither, so skip there rather than fail collection.
pytest.importorskip("psychopy")

from rich.console import Console  # noqa: E402

from heat_task import config  # noqa: E402
from heat_task.medoc.models import MedocResponse, ReturnCode  # noqa: E402
from heat_task.medoc.models import TestState as MedocTestState  # noqa: E402
from heat_task.task import mms  # noqa: E402


def _response(
    *, test_state: int = int(MedocTestState.RUNNING), return_code: int = 0
) -> MedocResponse:
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


@pytest.fixture(autouse=True)
def _fast_confirm(monkeypatch):
    monkeypatch.setattr(config, "START_CONFIRM_TIMEOUT_S", 0.0)
    monkeypatch.setattr(config, "START_CONFIRM_POLL_S", 0.0)


def _console() -> Console:
    return Console(quiet=True)


def test_ok_reply_passes():
    mms.confirm_started("h", 1, _console(), _response())


def test_error_reply_raises_with_decoded_name():
    reply = _response(return_code=int(ReturnCode.WAITING_MANUAL_OPERATION))
    with pytest.raises(RuntimeError, match="WAITING_MANUAL_OPERATION"):
        mms.confirm_started("h", 1, _console(), reply)


def test_no_reply_but_running_passes(monkeypatch):
    monkeypatch.setattr(mms, "send_command", lambda *a: _response())
    mms.confirm_started("h", 1, _console(), None)


def test_no_reply_and_not_running_raises(monkeypatch):
    idle = _response(test_state=int(MedocTestState.IDLE))
    monkeypatch.setattr(mms, "send_command", lambda *a: idle)
    with pytest.raises(RuntimeError, match="not running"):
        mms.confirm_started("h", 1, _console(), None)
