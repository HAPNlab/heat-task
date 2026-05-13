"""Converter tests ported from examples/medoc-python-api/UnitTests/unittest_converter.py.

Expected values come from Medoc's original test suite — ground truth for
byte-level protocol parsing.
"""

from __future__ import annotations

import pytest

from medoc.serial.utilities.converters import (
    get_bytes16,
    get_bytes32,
    to_int_16,
    to_u_int_16_ex,
    to_uint_16,
    to_uint_32,
)
from medoc.serial.utilities.temp_converter import pc2tcu


class TestToUInt16Ex:
    def setup_method(self):
        self.case1 = [0x37, 0x00, 0x15, 0x25]

    def test_index_0(self):
        assert to_u_int_16_ex(self.case1, 0) == 0x3700

    def test_index_1(self):
        assert to_u_int_16_ex(self.case1, 1) == 0x0015

    def test_index_2(self):
        assert to_u_int_16_ex(self.case1, 2) == 0x1525

    def test_out_of_range_raises(self):
        with pytest.raises(IndexError):
            to_u_int_16_ex(self.case1, 4)


class TestToInt16:
    def setup_method(self):
        self.case1 = [0x37, 0x00, 0x15, 0x25]

    def test_index_0(self):
        assert to_int_16(self.case1, 0) == 0x3700

    def test_index_1(self):
        assert to_int_16(self.case1, 1) == 0x0015

    def test_index_2(self):
        assert to_int_16(self.case1, 2) == 0x1525

    def test_out_of_range_3(self):
        with pytest.raises(IndexError):
            to_int_16(self.case1, 3)

    def test_out_of_range_4(self):
        with pytest.raises(IndexError):
            to_int_16(self.case1, 4)


class TestToUInt16:
    def setup_method(self):
        self.case2 = [0xFF, 0xEE, 0xDD, 0xAA]

    def test_index_0(self):
        assert to_uint_16(self.case2, 0) == 0xFFEE

    def test_index_1(self):
        assert to_uint_16(self.case2, 1) == 0xEEDD

    def test_index_2(self):
        assert to_uint_16(self.case2, 2) == 0xDDAA


class TestToUInt32:
    def setup_method(self):
        self.case32 = [0x61, 0x20, 0x00, 0x30, 0x23]

    def test_index_0(self):
        assert to_uint_32(self.case32, 0) == 0x61200030

    def test_index_1(self):
        assert to_uint_32(self.case32, 1) == 0x20003023

    def test_out_of_range_2(self):
        with pytest.raises(IndexError):
            to_uint_32(self.case32, 2)

    def test_out_of_range_3(self):
        with pytest.raises(IndexError):
            to_uint_32(self.case32, 3)


class TestGetBytes:
    def test_get_bytes16_short(self):
        assert list(get_bytes16(3700)) == [0x74, 0x0E]

    def test_get_bytes16_ushort(self):
        assert list(get_bytes16(30000)) == [0x30, 0x75]

    def test_get_bytes32(self):
        assert list(get_bytes32(2000000)) == [0x80, 0x84, 0x1E, 0x00]


class TestTempConverter:
    def test_pc2tcu_32c(self):
        assert pc2tcu(32) == 3200
