"""Tests for battery thresholds, ordering safeguards, and models."""

import unittest

from thinknux.core.hardware.battery import write_start_first
from thinknux.models.battery import BatteryInfo, BatteryThresholds


class TestBattery(unittest.TestCase):
    def test_write_start_first_ordering(self):
        # Current: (start=40, stop=80). New: (start=20, stop=35).
        # Intermediate with stop first would be (40, 35) -> start > stop!
        # Must write start first: (20, 80) is valid.
        self.assertTrue(write_start_first(current_start=40, new_stop=35))

        # Equal boundary: current_start=40, new_stop=40
        # Intermediate with stop first would be (40, 40) -> start == stop (rejected by firmware)!
        # Must write start first.
        self.assertTrue(write_start_first(current_start=40, new_stop=40))

        # Current: (start=40, stop=80). New: (start=50, stop=90).
        # Intermediate with stop first would be (40, 90) -> valid!
        # Intermediate with start first would be (50, 80) -> valid!
        # When new_stop > current_start, write_start_first is False.
        self.assertFalse(write_start_first(current_start=40, new_stop=90))

    def test_battery_thresholds_serialization(self):
        bt = BatteryThresholds(start=40, stop=80)
        d = bt.to_dict()
        self.assertEqual(d["start"], 40)
        self.assertEqual(d["stop"], 80)

        restored = BatteryThresholds.from_dict(d)
        self.assertEqual(restored.start, 40)
        self.assertEqual(restored.stop, 80)

    def test_battery_info_model(self):
        info = BatteryInfo(
            name="BAT0",
            status="Discharging",
            capacity=85,
            health=94,
            cycles=120,
            voltage=11.4,
            current=1.2,
            power=13.68,
            energy_now=45.2,
            energy_full=52.0,
            energy_design=55.0,
            technology="Li-poly",
            manufacturer="SMP",
        )
        d = info.to_dict()
        self.assertEqual(d["capacity"], 85)
        self.assertEqual(d["health"], 94)
        self.assertEqual(d["name"], "BAT0")


if __name__ == "__main__":
    unittest.main()
