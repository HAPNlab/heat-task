"""Tests for ramp-and-hold TOML run-file parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from heat_task.io.conditions import (
    list_run_files,
    load_run_config,
    parse_program_word,
    summarize_load_error,
    summarize_run_config,
)


def test_parse_program_word_accepts_8_bit_string() -> None:
    assert parse_program_word("00001111") == 15


def test_parse_program_word_rejects_invalid_strings() -> None:
    with pytest.raises(ValueError, match="exactly 8 bits"):
        parse_program_word("1111")


def test_load_run_config_parses_sequences(tmp_path: Path) -> None:
    run_file = tmp_path / "run.toml"
    run_file.write_text(
        "\n".join(
            [
                'program_word = "00001111"',
                "",
                "[[sequence]]",
                "baseline = 32.0",
                "target_temp = 45.0",
                "time_before_s = 20.0",
                "",
                "[[sequence]]",
                "baseline = 31.5",
                "target_temp = 44.5",
            ]
        )
    )

    config = load_run_config(run_file)

    assert config.program_word == "00001111"
    assert config.program_id == 15
    assert len(config.sequences) == 2
    assert config.sequences[0].time_before_s == 20.0
    assert config.sequences[1].baseline == 31.5
    assert config.sequences[1].time_before_s == 0.0  # defaults to 0


def test_load_run_config_rejects_target_below_baseline(tmp_path: Path) -> None:
    run_file = tmp_path / "run.toml"
    run_file.write_text(
        "\n".join(
            [
                'program_word = "00001111"',
                "",
                "[[sequence]]",
                "baseline = 40.0",
                "target_temp = 39.5",
            ]
        )
    )

    with pytest.raises(ValueError, match="must be greater than baseline"):
        load_run_config(run_file)


def test_load_run_config_rejects_reserved_command_word(tmp_path: Path) -> None:
    run_file = tmp_path / "run.toml"
    run_file.write_text(
        "\n".join(
            [
                'program_word = "00000010"',
                "",
                "[[sequence]]",
                "baseline = 35.0",
                "target_temp = 46.0",
            ]
        )
    )

    with pytest.raises(ValueError, match="reserved by MMS for the START command"):
        load_run_config(run_file)


def test_bundled_run_files_have_unique_unreserved_words() -> None:
    words = [load_run_config(path).program_word for path in list_run_files()]
    assert len(set(words)) == len(words)


def test_list_run_files_returns_bundled_toml_files_sorted() -> None:
    run_files = list_run_files()
    assert run_files, "conditions/ should ship at least one run file"
    assert all(path.suffix == ".toml" for path in run_files)
    assert [path.name for path in run_files] == sorted(path.name for path in run_files)


def test_summarize_run_config_lists_count_targets_and_word(tmp_path: Path) -> None:
    run_file = tmp_path / "run.toml"
    run_file.write_text(
        "\n".join(
            [
                'program_word = "00010000"',
                "[[sequence]]",
                "baseline = 35.0",
                "target_temp = 46.0",
                "[[sequence]]",
                "baseline = 35.0",
                "target_temp = 45.0",
                "[[sequence]]",
                "baseline = 35.0",
                "target_temp = 46.0",
            ]
        )
    )

    summary = summarize_run_config(load_run_config(run_file))

    assert summary == "3 sequences · targets 45, 46 °C · program word 00010000"


def test_summarize_load_error_gives_first_validation_problem(tmp_path: Path) -> None:
    run_file = tmp_path / "run.toml"
    run_file.write_text(
        "\n".join(
            [
                'program_word = "00000010"',
                "[[sequence]]",
                "baseline = 40.0",
                "target_temp = 39.5",
            ]
        )
    )

    with pytest.raises(ValueError) as excinfo:
        load_run_config(run_file)
    reason = summarize_load_error(excinfo.value)

    assert "\n" not in reason
    assert reason.startswith("program_word 00000010 is reserved")
    assert reason.endswith("more)")  # the other errors are counted, not listed


def test_summarize_load_error_handles_toml_syntax_errors(tmp_path: Path) -> None:
    run_file = tmp_path / "run.toml"
    run_file.write_text("program_word = \n")

    with pytest.raises(ValueError) as excinfo:
        load_run_config(run_file)

    assert "line 1" in summarize_load_error(excinfo.value)


def test_summarize_load_error_numbers_sequences_from_one(tmp_path: Path) -> None:
    run_file = tmp_path / "run.toml"
    run_file.write_text(
        "\n".join(
            [
                'program_word = "00010000"',
                "[[sequence]]",
                "baseline = 35.0",
                "target_temp = 45.0",
                "[[sequence]]",
                "baseline = 40.0",
                "target_temp = 39.5",
            ]
        )
    )

    with pytest.raises(ValueError) as excinfo:
        load_run_config(run_file)

    assert summarize_load_error(excinfo.value).startswith(
        "sequence 2: target_temp (39.5) must be greater than baseline (40.0)"
    )
