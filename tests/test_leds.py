"""Unit tests for ThinkPad LED models and mode validation."""

import unittest

from thinknux.core.hardware.leds import set_lid_logo_dot_mode
from thinknux.models.leds import LedDevice


class TestLeds(unittest.TestCase):
    def test_led_device_model(self):
        led = LedDevice(
            name="tpacpi::lid_logo_dot",
            sysfs_path="/sys/class/leds/tpacpi::lid_logo_dot",
            brightness=255,
            max_brightness=255,
            current_trigger="none",
            available_triggers=["none", "disk-activity", "cpu"],
        )
        d = led.to_dict()
        self.assertEqual(d["name"], "tpacpi::lid_logo_dot")
        self.assertEqual(d["brightness"], 255)
        self.assertIn("disk-activity", d["available_triggers"])

    def test_unknown_lid_mode(self):
        ok, err = set_lid_logo_dot_mode("invalid_mode")
        self.assertFalse(ok)
        self.assertIn("Unknown mode", err)


if __name__ == "__main__":
    unittest.main()
