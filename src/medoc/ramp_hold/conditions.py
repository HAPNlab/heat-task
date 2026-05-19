"""TOML run-file loading for the ramp-and-hold task."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class TrialConfig:
    baseline: float
    target_temp: float


@dataclass(frozen=True, slots=True)
class RunConfig:
    file_path: Path
    program_word: str
    program_id: int
    trials: tuple[TrialConfig, ...]


_PACKAGE_DIR = Path(__file__).parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent.parent
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

    program_word = payload.get("program_word")
    if not isinstance(program_word, str):
        raise ValueError("Run file must define program_word as a string")
    program_id = parse_program_word(program_word)

    raw_trials = payload.get("trial")
    if not isinstance(raw_trials, list) or not raw_trials:
        raise ValueError("Run file must define at least one [[trial]] entry")

    trials: list[TrialConfig] = []
    for index, raw_trial in enumerate(raw_trials, start=1):
        if not isinstance(raw_trial, dict):
            raise ValueError(f"trial {index}: entry must be a table")

        try:
            baseline = float(raw_trial["baseline"])
            target_temp = float(raw_trial["target_temp"])
        except KeyError as exc:
            raise ValueError(f"trial {index}: missing required field {exc.args[0]!r}") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"trial {index}: baseline and target_temp must be numeric") from exc

        if target_temp <= baseline:
            raise ValueError(
                f"trial {index}: target_temp ({target_temp}) must be greater than baseline ({baseline})"
            )

        trials.append(TrialConfig(baseline=baseline, target_temp=target_temp))

    return RunConfig(
        file_path=path,
        program_word=program_word,
        program_id=program_id,
        trials=tuple(trials),
    )
