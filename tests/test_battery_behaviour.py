"""Unit tests for battery charge behaviour modes."""

import unittest

from thinknux.core.hardware.battery import set_charge_behaviour


class TestBatteryBehaviour(unittest.TestCase):
    def test_invalid_mode_rejected(self):
        ok, err = set_charge_behaviour("unsupported_mode")
        self.assertFalse(ok)
        self.assertIn("Invalid charge behaviour", err)


if __name__ == "__main__":
    unittest.main()
