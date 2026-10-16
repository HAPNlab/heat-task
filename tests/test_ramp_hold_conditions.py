"""Tests for ramp-and-hold TOML run-file parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from heat_task.io.conditions import conditions_dir, load_run_config, parse_program_word


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
    run_files = sorted(conditions_dir().glob("*.toml"))
    words = [load_run_config(path).program_word for path in run_files]
    assert len(set(words)) == len(words)
