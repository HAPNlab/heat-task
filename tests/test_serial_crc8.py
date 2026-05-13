"""CRC8 tests ported from examples/medoc-python-api/UnitTests/unittest_crc8.py.

Expected values come from Medoc's original test suite — these are ground truth
for the wire protocol checksum.
"""

from __future__ import annotations

from medoc.serial.crc8 import calculate


class TestCrc8:
    def test_get_version_send(self):
        # From unittest_crc8.py: known good CRC for GetVersion command bytes
        get_version_send = [0x00, 0x00, 0x08, 0x25, 0x00, 0x00, 0x00, 0x02, 0x00]
        assert calculate(get_version_send, 1, 8) == 0x76

    def test_empty_slice(self):
        data = [0x01, 0x02, 0x03]
        assert calculate(data, 0, 0) == 0

    def test_single_byte(self):
        # CRC of a single zero byte should be 0 (XOR with 0 → table[0] = 0)
        assert calculate([0x00], 0, 1) == 0
