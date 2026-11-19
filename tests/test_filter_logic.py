#!/usr/bin/env python3
"""
Unit tests for the 433 MHz RF sensor filter logic.
Verifies the matching algorithm implemented in src/main.cpp:
- Filter disabled: all packets with valid temperature are accepted.
- Filter enabled: packets are filtered by model, sensor ID, and channel.
- Wildcards: empty model string, ID = -1, channel = -1 match any value.
"""

import unittest


def matches_filter(packet_model: str, packet_id: int, packet_channel: int,
                   filter_enabled: bool, target_model: str, target_id: int, target_channel: int) -> bool:
    """Python reference implementation of the firmware filter logic in src/main.cpp."""
    if not filter_enabled:
        return True

    # Case-insensitive model check; empty model matches any
    is_target = len(target_model) == 0 or packet_model.lower() == target_model.lower()

    # Sensor ID check (-1 matches any)
    if is_target and target_id >= 0 and packet_id != target_id:
        is_target = False

    # Channel check (-1 matches any)
    if is_target and target_channel >= 0 and packet_channel != target_channel:
        is_target = False

    return is_target


class TestFilterLogic(unittest.TestCase):

    def test_filter_disabled_accepts_all(self):
        """When filter is disabled, any model/id/channel must be accepted."""
        self.assertTrue(matches_filter("Kedsum-TH", 186, 1, filter_enabled=False,
                                       target_model="Hideki-TS04", target_id=12, target_channel=2))
        self.assertTrue(matches_filter("Acurite-606TX", 44, 1, filter_enabled=False,
                                       target_model="Kedsum-TH", target_id=-1, target_channel=-1))
        self.assertTrue(matches_filter("Nexus-TH", 99, 3, filter_enabled=False,
                                       target_model="", target_id=-1, target_channel=-1))

    def test_filter_exact_match(self):
        """When filter is enabled, exact match must be accepted."""
        self.assertTrue(matches_filter("Kedsum-TH", 186, 1, filter_enabled=True,
                                       target_model="Kedsum-TH", target_id=186, target_channel=1))

    def test_filter_case_insensitivity(self):
        """Model matching should be case-insensitive (e.g. kedsum-th == Kedsum-TH)."""
        self.assertTrue(matches_filter("kedsum-th", 186, 1, filter_enabled=True,
                                       target_model="Kedsum-TH", target_id=186, target_channel=1))
        self.assertTrue(matches_filter("HIDEKI-TS04", 12, 1, filter_enabled=True,
                                       target_model="hideki-ts04", target_id=12, target_channel=1))

    def test_filter_model_mismatch(self):
        """Mismatched model must be rejected when filter is enabled."""
        self.assertFalse(matches_filter("Acurite-606TX", 186, 1, filter_enabled=True,
                                        target_model="Kedsum-TH", target_id=186, target_channel=1))

    def test_filter_id_wildcard(self):
        """target_id == -1 must match any sensor ID."""
        self.assertTrue(matches_filter("Kedsum-TH", 12, 1, filter_enabled=True,
                                       target_model="Kedsum-TH", target_id=-1, target_channel=1))
        self.assertTrue(matches_filter("Kedsum-TH", 999, 1, filter_enabled=True,
                                       target_model="Kedsum-TH", target_id=-1, target_channel=1))

    def test_filter_id_mismatch(self):
        """Mismatched sensor ID must be rejected when target_id >= 0."""
        self.assertFalse(matches_filter("Kedsum-TH", 187, 1, filter_enabled=True,
                                        target_model="Kedsum-TH", target_id=186, target_channel=1))

    def test_filter_channel_wildcard(self):
        """target_channel == -1 must match any channel."""
        self.assertTrue(matches_filter("Kedsum-TH", 186, 1, filter_enabled=True,
                                       target_model="Kedsum-TH", target_id=186, target_channel=-1))
        self.assertTrue(matches_filter("Kedsum-TH", 186, 2, filter_enabled=True,
                                       target_model="Kedsum-TH", target_id=186, target_channel=-1))
        self.assertTrue(matches_filter("Kedsum-TH", 186, 3, filter_enabled=True,
                                       target_model="Kedsum-TH", target_id=186, target_channel=-1))

    def test_filter_channel_mismatch(self):
        """Mismatched channel must be rejected when target_channel >= 0."""
        self.assertFalse(matches_filter("Kedsum-TH", 186, 2, filter_enabled=True,
                                        target_model="Kedsum-TH", target_id=186, target_channel=1))

    def test_filter_empty_model_wildcard(self):
        """An empty target model matches any model if ID and channel match."""
        self.assertTrue(matches_filter("Hideki-TS04", 12, 1, filter_enabled=True,
                                       target_model="", target_id=12, target_channel=1))
        self.assertTrue(matches_filter("Kedsum-TH", 12, 1, filter_enabled=True,
                                       target_model="", target_id=12, target_channel=1))
        self.assertFalse(matches_filter("Kedsum-TH", 99, 1, filter_enabled=True,
                                        target_model="", target_id=12, target_channel=1))


if __name__ == "__main__":
    unittest.main()
