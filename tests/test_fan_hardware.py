"""Tests for ThinkPad fan hardware parsing and speed whitelist validation."""

import unittest

from thinknux.core.hardware.fan import (
    FAN_WATCHDOG_SECS,
    VALID_FAN_SPEEDS,
    fan_control_is_enabled,
    is_valid_speed,
    parse_fan_proc,
)

SAMPLE_PROC_FAN = """status:		enabled
speed:		3200
level:		auto
commands:	level <level> (<level> is 0-7, auto, disengaged, full-speed)
commands:	enable, disable
commands:	watchdog <timeout> (<timeout> is 0-120 seconds)
"""

SAMPLE_PROC_FAN_DISABLED = """status:		enabled
speed:		2500
level:		auto
"""


class TestFanHardware(unittest.TestCase):
    def test_parse_fan_proc(self):
        parsed = parse_fan_proc(SAMPLE_PROC_FAN)
        self.assertEqual(parsed.get("status"), "enabled")
        self.assertEqual(parsed.get("speed"), "3200")
        self.assertEqual(parsed.get("level"), "auto")
        self.assertIn("level", parsed.get("commands", ""))

    def test_fan_control_enabled_detection(self):
        self.assertTrue(fan_control_is_enabled(SAMPLE_PROC_FAN))
        self.assertFalse(fan_control_is_enabled(SAMPLE_PROC_FAN_DISABLED))

    def test_speed_whitelist(self):
        for speed in ["auto", "full-speed", "0", "1", "2", "3", "4", "5", "6", "7"]:
            self.assertTrue(is_valid_speed(speed), f"Speed {speed} should be valid")

        for invalid in ["8", "level 1", "disable", "30", "", "max", "auto "]:
            self.assertFalse(is_valid_speed(invalid), f"Speed {invalid} should be invalid")

    def test_watchdog_constant(self):
        self.assertEqual(FAN_WATCHDOG_SECS, 30)


if __name__ == "__main__":
    unittest.main()
