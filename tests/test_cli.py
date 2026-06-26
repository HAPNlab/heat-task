"""Tests for the Medoc command line interface."""

from __future__ import annotations

from collections.abc import Iterator

import heat_task.medoc.cli as cli
from heat_task.medoc.models import MedocResponse, ReturnCode, SystemState
from heat_task.medoc.models import TestState as MedocTestState


def _response(
    *,
    command: int = 0,
    system_state: int = int(SystemState.ACTIVE),
    test_state: int = int(MedocTestState.RUNNING),
    return_code: int = int(ReturnCode.OK),
) -> MedocResponse:
    return MedocResponse(
        response_length=23,
        timestamp=1000,
        command=command,
        system_state=system_state,
        test_state=test_state,
        return_code=return_code,
        test_time=100,
        raw_temperature=3200,
        covas=0,
        yes=0,
        no=0,
        ttl=0,
    )


_DEFAULT_SELECT_RESPONSE = _response(command=1, test_state=int(MedocTestState.READY))
_DEFAULT_START_RESPONSE = _response(command=2)


class FakeClient:
    def __init__(
        self,
        statuses: list[MedocResponse],
        *,
        select_response: MedocResponse | None = _DEFAULT_SELECT_RESPONSE,
        start_responses: list[MedocResponse | None] | None = None,
    ):
        self.selected_program_id: int | None = None
        self.statuses: Iterator[MedocResponse] = iter(statuses)
        self.select_response = select_response
        self.start_responses: Iterator[MedocResponse | None] = iter(
            start_responses or [_DEFAULT_START_RESPONSE, _DEFAULT_START_RESPONSE]
        )
        self.start_count = 0
        self.aborted = False

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def select_test(self, program_id: int) -> MedocResponse | None:
        self.selected_program_id = program_id
        return self.select_response

    def start(self) -> MedocResponse | None:
        self.start_count += 1
        return next(self.start_responses)

    def status(self) -> MedocResponse:
        return next(self.statuses)

    def abort(self) -> MedocResponse:
        self.aborted = True
        return _response(command=6, test_state=int(MedocTestState.IDLE))


def test_run_program_selects_starts_and_monitors_until_finished(monkeypatch, capsys):
    fake_client = FakeClient(
        [
            _response(test_state=int(MedocTestState.RUNNING)),
            _response(system_state=int(SystemState.READY), test_state=int(MedocTestState.IDLE)),
        ]
    )

    monkeypatch.setattr(cli.MedocClient, "connect", lambda *args, **kwargs: fake_client)

    exit_code = cli.main(
        [
            "run",
            "127.0.0.1",
            "15",
            "--poll-interval",
            "0",
            "--select-delay",
            "0",
            "--pretest-delay",
            "0",
        ]
    )

    assert exit_code == 0
    assert fake_client.selected_program_id == 15
    assert fake_client.start_count == 2
    assert "program finished" in capsys.readouterr().out


def test_run_program_accepts_program_word(monkeypatch):
    fake_client = FakeClient(
        [
            _response(test_state=int(MedocTestState.RUNNING)),
            _response(system_state=int(SystemState.READY), test_state=int(MedocTestState.IDLE)),
        ]
    )

    monkeypatch.setattr(cli.MedocClient, "connect", lambda *args, **kwargs: fake_client)

    exit_code = cli.main(
        [
            "run",
            "127.0.0.1",
            "--program-word",
            "00001111",
            "--poll-interval",
            "0",
            "--select-delay",
            "0",
            "--pretest-delay",
            "0",
        ]
    )

    assert exit_code == 0
    assert fake_client.selected_program_id == 15


def test_run_program_returns_error_when_start_fails(monkeypatch, capsys):
    fake_client = FakeClient(
        [],
        start_responses=[
            _response(command=2),
            _response(command=2, return_code=int(ReturnCode.ILLEGAL_STATE)),
        ],
    )

    monkeypatch.setattr(cli.MedocClient, "connect", lambda *args, **kwargs: fake_client)

    exit_code = cli.main(
        [
            "run",
            "127.0.0.1",
            "15",
            "--poll-interval",
            "0",
            "--select-delay",
            "0",
            "--pretest-delay",
            "0",
        ]
    )

    assert exit_code == 1
    assert "start: MMS returned ILLEGAL_STATE" in capsys.readouterr().err


def test_run_program_monitors_when_select_and_start_do_not_respond(monkeypatch, capsys):
    fake_client = FakeClient(
        [
            _response(test_state=int(MedocTestState.RUNNING)),
            _response(system_state=int(SystemState.READY), test_state=int(MedocTestState.IDLE)),
        ],
        select_response=None,
        start_responses=[None, None],
    )

    monkeypatch.setattr(cli.MedocClient, "connect", lambda *args, **kwargs: fake_client)

    exit_code = cli.main(
        [
            "run",
            "127.0.0.1",
            "15",
            "--poll-interval",
            "0",
            "--select-delay",
            "0",
            "--pretest-delay",
            "0",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "select: no immediate response" in captured.out
    assert "pretest: no immediate response" in captured.out
    assert "start: no immediate response" in captured.out
    assert "program finished" in captured.out


def test_monitor_status_only_does_not_select_or_start(monkeypatch, capsys):
    fake_client = FakeClient([_response(test_state=int(MedocTestState.RUNNING))])

    monkeypatch.setattr(cli.MedocClient, "connect", lambda *args, **kwargs: fake_client)

    exit_code = cli.main(
        ["monitor", "127.0.0.1", "--poll-interval", "0", "--count", "1"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert fake_client.selected_program_id is None
    assert fake_client.start_count == 0
    assert "status: system=ACTIVE test=RUNNING" in captured.out


def test_monitor_can_select_program_before_status(monkeypatch, capsys):
    fake_client = FakeClient([_response(test_state=int(MedocTestState.RUNNING))])

    monkeypatch.setattr(cli.MedocClient, "connect", lambda *args, **kwargs: fake_client)

    exit_code = cli.main(
        [
            "monitor",
            "127.0.0.1",
            "15",
            "--poll-interval",
            "0",
            "--select-delay",
            "0",
            "--count",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert fake_client.selected_program_id == 15
    assert fake_client.start_count == 0
    assert "select: system=ACTIVE test=READY" in captured.out
    assert "status: system=ACTIVE test=RUNNING" in captured.out


def test_monitor_can_select_program_word(monkeypatch):
    fake_client = FakeClient([_response(test_state=int(MedocTestState.RUNNING))])

    monkeypatch.setattr(cli.MedocClient, "connect", lambda *args, **kwargs: fake_client)

    exit_code = cli.main(
        [
            "monitor",
            "127.0.0.1",
            "--program-word",
            "10000000",
            "--poll-interval",
            "0",
            "--select-delay",
            "0",
            "--count",
            "1",
        ]
    )

    assert exit_code == 0
    assert fake_client.selected_program_id == 128
