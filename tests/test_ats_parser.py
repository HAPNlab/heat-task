"""Regression tests for the .ats file parser against examples/experiment.ats."""

from __future__ import annotations

from pathlib import Path

import pytest

from medoc.ats_parser import parse_ats
from medoc.experiment import Experiment, RampAndHoldSequence, ThermodeProgram

ATS_FILE = Path(__file__).parent.parent / "examples" / "experiment.ats"


@pytest.fixture(scope="module")
def experiment() -> Experiment:
    return parse_ats(ATS_FILE)


class TestExperimentStructure:
    def test_program_count(self, experiment):
        assert len(experiment.programs) == 6

    def test_program_names(self, experiment):
        names = [p.name for p in experiment.programs]
        assert names == [
            "SingleProbe_46-47_Run1",
            "SingleProbe_46-48_Run1",
            "SingleProbe_45-46_Run1",
            "SingleProbe_45-46_Run2",
            "SingleProbe_46-47_Run2",
            "SingleProbe_46-48_Run2",
        ]

    def test_each_program_has_six_sequences(self, experiment):
        for prog in experiment.programs:
            assert len(prog.sequences) == 6, f"{prog.name} has {len(prog.sequences)} sequences"

    def test_programs_are_frozen(self, experiment):
        with pytest.raises((AttributeError, TypeError)):
            experiment.programs[0].name = "tampered"  # type: ignore[misc]


class TestSequenceValues:
    """Spot-check specific sequence values against known-good output."""

    def test_all_sequences_baseline_35(self, experiment):
        for prog in experiment.programs:
            for seq in prog.sequences:
                assert seq.baseline_temp == 35.0

    def test_all_sequences_rate_4_5(self, experiment):
        for prog in experiment.programs:
            for seq in prog.sequences:
                assert seq.destination_rate == pytest.approx(4.5)

    def test_all_sequences_duration_30s(self, experiment):
        for prog in experiment.programs:
            for seq in prog.sequences:
                assert seq.duration_ms == 30_000

    def test_all_sequences_one_trial(self, experiment):
        for prog in experiment.programs:
            for seq in prog.sequences:
                assert seq.trials == 1

    def test_program0_destinations(self, experiment):
        # SingleProbe_46-47_Run1: seqs alternate between 46 and 47
        dests = [s.destination_temp for s in experiment.programs[0].sequences]
        assert dests == [46.0, 47.0, 47.0, 46.0, 46.0, 47.0]

    def test_program1_destinations(self, experiment):
        # SingleProbe_46-48_Run1
        dests = [s.destination_temp for s in experiment.programs[1].sequences]
        assert dests == [46.0, 48.0, 48.0, 46.0, 46.0, 48.0]

    def test_program2_destinations(self, experiment):
        # SingleProbe_45-46_Run1
        dests = [s.destination_temp for s in experiment.programs[2].sequences]
        assert dests == [45.0, 46.0, 46.0, 45.0, 45.0, 46.0]

    def test_sequence_numbers_start_at_one(self, experiment):
        for prog in experiment.programs:
            assert prog.sequences[0].number == 1

    def test_return_types(self, experiment):
        seq = experiment.programs[0].sequences[0]
        assert isinstance(seq, RampAndHoldSequence)
        assert isinstance(seq.baseline_temp, float)
        assert isinstance(seq.destination_temp, float)
        assert isinstance(seq.destination_rate, float)
        assert isinstance(seq.duration_ms, int)
        assert isinstance(seq.trials, int)


class TestParserErrors:
    def test_missing_file_raises(self):
        with pytest.raises((FileNotFoundError, OSError, ValueError)):
            parse_ats(Path("/nonexistent/file.ats"))
