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
        parse_program_word(value)  # raises ValueError on a malformed word
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
