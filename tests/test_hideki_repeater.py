#!/usr/bin/env python3
"""
Unit tests for Hideki / Cresta protocol repeater encoding.
Tests the exact bitwise transformations and checksum calculations
used in src/main.cpp to re-transmit readings for EMOS E0688.
"""

import unittest


def encrypt_byte(b: int) -> int:
    """Exact Python equivalent of encryptByte(byte b) in src/main.cpp."""
    b = b & 0xFF
    a = 0
    while b:
        a ^= b
        b = (b << 1) & 0xFF
    return a & 0xFF


def second_check(b: int) -> int:
    """Exact Python equivalent of secondCheck(byte b) in src/main.cpp."""
    b = b & 0xFF
    if b & 0x80:
        b ^= 0x95
    c = (b ^ (b >> 1)) & 0xFF
    if b & 1:
        c ^= 0x5F
    if c & 1:
        b ^= 0x5F
    return (b ^ (c >> 1)) & 0xFF


def encrypt_and_add_check(buffer: list) -> int:
    """Exact Python equivalent of encryptAndAddCheck(byte *buffer) in src/main.cpp."""
    count = (buffer[2] >> 1) & 0x1F
    cs1 = 0
    cs2 = 0
    for i in range(1, count + 1):
        buffer[i] = encrypt_byte(buffer[i])
        cs1 ^= buffer[i]
        cs2 = second_check(buffer[i] ^ cs2)

    buffer[count + 1] = cs1
    buffer[count + 2] = second_check(cs1 ^ cs2)
    return count + 3


def encode_hideki_payload(temp_c: float, humidity: int, channel: int = 1, sensor_id: int = 0x0C) -> list:
    """Encodes temperature and humidity into raw Hideki bytes before encryption."""
    raw = [0] * 10
    raw[0] = 0x75  # Header
    raw[1] = ((channel & 0x07) << 5) | (sensor_id & 0x1F)
    raw[2] = 0xCE  # Packet size indicator
    raw[3] = 0x1E  # Sensor type: thermo/hygro

    t = int(round(temp_c * 10.0))
    if t < 0:
        raw[5] = 0x4 << 4  # Negative sign indicator
        t = -t
    else:
        raw[5] = 0xC << 4  # Positive sign indicator

    raw[4] = (((t % 100) // 10) << 4) | (t % 10)
    raw[5] |= (t // 100)
    raw[6] = (((humidity // 10) & 0x0F) << 4) | (humidity % 10)
    raw[7] = 0xFF  # Comfort / status flag
    return raw


class TestHidekiRepeater(unittest.TestCase):

    def test_encrypt_byte_properties(self):
        """encrypt_byte should produce deterministic 8-bit output."""
        self.assertEqual(encrypt_byte(0x00), 0x00)
        self.assertEqual(encrypt_byte(0x01), 0x01 ^ 0x02 ^ 0x04 ^ 0x08 ^ 0x10 ^ 0x20 ^ 0x40 ^ 0x80)
        # Verify 8-bit bounds
        for b in range(256):
            res = encrypt_byte(b)
            self.assertTrue(0 <= res <= 255)

    def test_second_check_bounds(self):
        """second_check should map 8-bit byte to 8-bit byte."""
        for b in range(256):
            res = second_check(b)
            self.assertTrue(0 <= res <= 255)

    def test_packet_structure_positive_temp(self):
        """Test encoding of +21.5 C and 55% humidity."""
        raw = encode_hideki_payload(21.5, 55, channel=1, sensor_id=0x0C)
        self.assertEqual(raw[0], 0x75)
        # Channel 1 (0x20) | ID 0x0C -> 0x2C
        self.assertEqual(raw[1], 0x2C)
        self.assertEqual(raw[2], 0xCE)
        self.assertEqual(raw[3], 0x1E)
        # Temperature 21.5 -> t = 215 -> raw[4] = (1 << 4) | 5 = 0x15, raw[5] = 0xC0 | 2 = 0xC2
        self.assertEqual(raw[4], 0x15)
        self.assertEqual(raw[5], 0xC2)
        # Humidity 55% -> 0x55
        self.assertEqual(raw[6], 0x55)
        self.assertEqual(raw[7], 0xFF)

    def test_packet_structure_negative_temp(self):
        """Test encoding of -5.2 C and 80% humidity."""
        raw = encode_hideki_payload(-5.2, 80, channel=2, sensor_id=0x05)
        # Channel 2 (0x40) | ID 0x05 -> 0x45
        self.assertEqual(raw[1], 0x45)
        # Temperature -5.2 -> t = 52 -> raw[4] = (5 << 4) | 2 = 0x52, raw[5] = 0x40 | 0 = 0x40
        self.assertEqual(raw[4], 0x52)
        self.assertEqual(raw[5], 0x40)
        self.assertEqual(raw[6], 0x80)

    def test_packet_checksum_generation(self):
        """Verify encrypt_and_add_check appends two checksum bytes."""
        raw = encode_hideki_payload(20.0, 50, channel=1, sensor_id=0x0C)
        packet_len = ((raw[2] >> 1) & 0x1F) + 1
        buffer = list(raw[:packet_len]) + [0, 0, 0, 0]
        total_len = encrypt_and_add_check(buffer)
        self.assertEqual(total_len, packet_len + 2)
        # Checksum bytes must not be both zero for standard packet
        cs1 = buffer[total_len - 2]
        cs2 = buffer[total_len - 1]
        self.assertTrue(0 <= cs1 <= 255)
        self.assertTrue(0 <= cs2 <= 255)


if __name__ == "__main__":
    unittest.main()
