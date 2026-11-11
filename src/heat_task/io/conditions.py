"""TOML run-file loading for the ramp-and-hold task."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from heat_task.medoc.models import Command

_RESERVED_MAX = max(Command)


class SequenceConfig(BaseModel):
    """One MMS *sequence*: a baseline → ramp-up → hold → ramp-down → baseline
    cycle. Field names mirror the MMS program columns.

    time_before_s is the MMS "Time Before Sequence" lead-in (0 for all but the
    first sequence in a typical program); baseline_duration_s is the trailing
    baseline the sequence holds *after* its ramp-down (the MMS ISI), consumed at
    the end of the sequence."""

    model_config = ConfigDict(frozen=True)

    baseline: float
    target_temp: float
    time_before_s: float = 0.0
    baseline_duration_s: float | None = None
    target_hold_duration_s: float | None = None

    @model_validator(mode="after")
    def _target_above_baseline(self) -> SequenceConfig:
        if self.target_temp <= self.baseline:
            raise ValueError(
                f"target_temp ({self.target_temp}) must be greater than "
                f"baseline ({self.baseline})"
            )
        return self


class RunConfig(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    file_path: Path
    program_word: str
    # TOML uses [[sequence]] tables; expose them as the plural `sequences`.
    sequences: tuple[SequenceConfig, ...] = Field(alias="sequence", min_length=1)

    @field_validator("program_word")
    @classmethod
    def _valid_program_word(cls, value: str) -> str:
        program_id = parse_program_word(value)  # raises ValueError on a malformed word
        # MMS maps external-control commands to these same 8-bit words, so a
        # program set to one of them would be shadowed by that command.
        if program_id in Command._value2member_map_:
            raise ValueError(
                f"program_word {value} is reserved by MMS for the "
                f"{Command(program_id).name} command; use {_RESERVED_MAX + 1:08b} or above"
            )
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def program_id(self) -> int:
        return parse_program_word(self.program_word)


_PACKAGE_DIR = Path(__file__).parent.parent  # src/heat_task (this file lives in io/)
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent  # src/heat_task -> src -> project root
_CONDITIONS_DIR = _PROJECT_ROOT / "conditions"


def conditions_dir() -> Path:
    return _CONDITIONS_DIR


def list_run_files() -> list[Path]:
    """The run files in conditions/, sorted by name (the setup wizard's list order)."""
    return sorted(_CONDITIONS_DIR.glob("*.toml"))


def summarize_run_config(config: RunConfig) -> str:
    """One-line summary of a run file, shown under it in the setup wizard's list."""
    count = len(config.sequences)
    targets = ", ".join(f"{t:g}" for t in sorted({s.target_temp for s in config.sequences}))
    noun = "sequence" if count == 1 else "sequences"
    return f"{count} {noun} · targets {targets} °C · program word {config.program_word}"


def summarize_load_error(exc: Exception) -> str:
    """One-line reason load_run_config failed, short enough to show inline in the
    setup wizard's list (the full pydantic report spans many lines)."""
    cause = exc.__cause__
    if isinstance(cause, ValidationError):
        first = cause.errors()[0]
        message = first["msg"].removeprefix("Value error, ")
        # Number [[sequence]] tables from 1, as they read in the file. Skip the
        # location when the message already names the field it's about.
        location = " ".join(
            str(part + 1) if isinstance(part, int) else part for part in first["loc"]
        )
        named = bool(first["loc"]) and message.startswith(str(first["loc"][-1]))
        reason = f"{location}: {message}" if location and not named else message
        if extra := cause.error_count() - 1:
            reason += f" (+{extra} more)"
        return reason
    return str(exc).splitlines()[0]


def resolve_run_file(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return _CONDITIONS_DIR / path


def parse_program_word(value: str) -> int:
    if len(value) != 8 or any(bit not in "01" for bit in value):
        raise ValueError("program_word must be exactly 8 bits, e.g. 00001111")
    return int(value, 2)


def load_run_config(path_value: str | Path) -> RunConfig:
    path = resolve_run_file(path_value)
    if not path.exists():
        raise FileNotFoundError(f"Run file not found: {path}")

    with open(path, "rb") as handle:
        payload = tomllib.load(handle)

    try:
        return RunConfig.model_validate({**payload, "file_path": path})
    except ValidationError as exc:
        raise ValueError(f"Invalid run file {path}:\n{exc}") from exc
