#!/usr/bin/env python3
"""
Unit tests for rtl_433 JSON packet parsing and message handling.
Mirrors the rtl_433_Callback and addLogEntry behavior in src/main.cpp.
"""

import json
import unittest


def parse_rtl433_packet(raw_json_str: str) -> dict:
    """Parses an rtl_433 JSON string and extracts standardized sensor fields."""
    try:
        data = json.loads(raw_json_str)
    except Exception as e:
        return {"error": f"JSON parse error: {e}"}

    model = data.get("model", "")
    sensor_id = data.get("id", -1)
    channel = data.get("channel", -1)

    # Temperature field can be 'temperature_C' or 'temp'
    temp = None
    if "temperature_C" in data and data["temperature_C"] is not None:
        temp = float(data["temperature_C"])
    elif "temp" in data and data["temp"] is not None:
        temp = float(data["temp"])

    # Humidity
    humidity = data.get("humidity", -1)

    # Battery
    battery_ok = -1
    if "battery_ok" in data and data["battery_ok"] is not None:
        battery_ok = 1 if data["battery_ok"] else 0

    has_temperature = temp is not None
    return {
        "model": model,
        "id": sensor_id,
        "channel": channel,
        "temperature": temp,
        "humidity": humidity,
        "battery_ok": battery_ok,
        "has_temperature": has_temperature,
    }


class RingLogBuffer:
    """Python simulation of the MAX_LOG_ENTRIES ring buffer in src/main.cpp."""

    def __init__(self, max_size=35):
        self.max_size = max_size
        self.entries = []

    def add(self, raw, model, sensor_id, channel, temp, bat, hum, accepted):
        entry = {
            "raw": raw,
            "model": model,
            "id": sensor_id,
            "channel": channel,
            "temperature": temp,
            "battery": bat,
            "humidity": hum,
            "accepted": accepted,
        }
        self.entries.insert(0, entry)
        if len(self.entries) > self.max_size:
            self.entries.pop()


class TestRtl433Parser(unittest.TestCase):

    def test_parse_kedsum_packet(self):
        """Test parsing of standard Kedsum-TH packet."""
        raw = '{"model":"Kedsum-TH","id":186,"channel":1,"battery_ok":1,"temperature_C":21.4,"humidity":55}'
        res = parse_rtl433_packet(raw)
        self.assertEqual(res["model"], "Kedsum-TH")
        self.assertEqual(res["id"], 186)
        self.assertEqual(res["channel"], 1)
        self.assertEqual(res["temperature"], 21.4)
        self.assertEqual(res["humidity"], 55)
        self.assertEqual(res["battery_ok"], 1)
        self.assertTrue(res["has_temperature"])

    def test_parse_hideki_packet(self):
        """Test parsing of Hideki-TS04 packet with RSSI and duration."""
        raw = ('{"model":"Hideki-TS04","id":12,"channel":1,"battery_ok":1,'
               '"temperature_C":9.0,"humidity":81,"mic":"CRC","rssi":-53}')
        res = parse_rtl433_packet(raw)
        self.assertEqual(res["model"], "Hideki-TS04")
        self.assertEqual(res["id"], 12)
        self.assertEqual(res["channel"], 1)
        self.assertEqual(res["temperature"], 9.0)
        self.assertEqual(res["humidity"], 81)

    def test_parse_packet_without_temperature(self):
        """Packets without temperature field must be flagged accordingly."""
        raw = '{"model":"Generic-Remote","id":55,"state":"ON"}'
        res = parse_rtl433_packet(raw)
        self.assertFalse(res["has_temperature"])
        self.assertIsNone(res["temperature"])

    def test_parse_alternative_temp_field(self):
        """Some rtl_433 decoders emit 'temp' instead of 'temperature_C'."""
        raw = '{"model":"Nexus-TH","id":7,"channel":2,"temp":-3.5,"humidity":70}'
        res = parse_rtl433_packet(raw)
        self.assertEqual(res["temperature"], -3.5)
        self.assertTrue(res["has_temperature"])

    def test_ring_log_buffer_max_size(self):
        """Ring buffer must cap at max_size (35 entries) and keep newest at index 0."""
        buf = RingLogBuffer(max_size=35)
        for i in range(50):
            buf.add(f'{{"i":{i}}}', f"Model-{i}", i, 1, 20.0 + i, 1, 50, True)

        self.assertEqual(len(buf.entries), 35)
        self.assertEqual(buf.entries[0]["model"], "Model-49")
        self.assertEqual(buf.entries[-1]["model"], "Model-15")


if __name__ == "__main__":
    unittest.main()
