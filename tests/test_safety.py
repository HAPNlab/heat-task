"""Tests for the safety limits table.

Values are sourced from examples/medoc-python-api/C/inc/constants.h — the
original C implementation. Any divergence between this test and safety.py
means one of them is wrong.
"""

from __future__ import annotations

import hashlib
import importlib

import pytest

# Expected table verbatim from constants.h
_EXPECTED_TABLE = (
    (56.0,      0),
    (55.0,     50),
    (52.0,    400),
    (51.0,   1000),
    (50.0,   5000),
    (49.0,  10000),
    (47.0,  60000),
    ( 6.0, 300000),
    ( 0.0, 300000),
    (-10.0, 300000),
)


class TestSafetyTableValues:
    """Verify every entry in the table matches the C header exactly."""

    def test_table_length(self):
        from medoc.safety import _TABLE
        assert len(_TABLE) == len(_EXPECTED_TABLE)

    def test_table_values_match_c_header(self):
        from medoc.safety import _TABLE
        assert _TABLE == _EXPECTED_TABLE

    def test_table_contents_are_immutable(self):
        from medoc.safety import _TABLE
        with pytest.raises(TypeError):
            _TABLE[0] = (99.0, 0)  # type: ignore[index]


class TestSafetyFunctions:
    @pytest.mark.parametrize("temp, expected_ms", [
        (56.0,      0),
        (55.5,     50),
        (55.0,     50),
        (52.0,    400),
        (51.0,   1000),
        (50.0,   5000),
        (49.0,  10000),
        (47.0,  60000),
        (46.9, 300000),
        (40.0, 300000),
        ( 6.0, 300000),
        ( 0.0, 300000),
        (-10.0, 300000),
    ])
    def test_get_safety_ms(self, temp, expected_ms):
        from medoc.safety import get_safety_ms
        assert get_safety_ms(temp) == expected_ms

    @pytest.mark.parametrize("temp, expected_level", [
        (57.0,  56.0),
        (56.0,  56.0),
        (55.0,  55.0),
        (52.5,  52.0),
        (50.0,  50.0),
        (47.0,  47.0),
        (10.0,   6.0),
        ( 0.0,   0.0),
        (-5.0, -10.0),
    ])
    def test_get_safety_level(self, temp, expected_level):
        from medoc.safety import get_safety_level
        assert get_safety_level(temp) == expected_level

    def test_get_safety_ms_below_all_limits(self):
        from medoc.safety import get_safety_ms
        # Below the lowest threshold, should return the last entry's ms
        assert get_safety_ms(-20.0) == 300000

    def test_get_safety_level_below_all_limits(self):
        from medoc.safety import get_safety_level
        assert get_safety_level(-20.0) == -10.0


class TestChecksumProtection:
    def test_checksum_validates_on_import(self):
        """Importing medoc.safety must not raise — checksum is valid."""
        import medoc.safety  # noqa: F401 — just checking it imports cleanly
