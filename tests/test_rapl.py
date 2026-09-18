"""Unit tests for Intel RAPL package power limits and validations."""

import unittest

from thinknux.core.hardware.rapl import set_rapl_limits
from thinknux.models.rapl import RaplLimits


class TestRapl(unittest.TestCase):
    def test_rapl_limits_model(self):
        limits = RaplLimits(
            supported=True,
            name="package-0",
            pl1_watts=28.0,
            pl2_watts=64.0,
            pl1_time_window_sec=28.0,
            pl2_time_window_sec=0.002,
            enabled=True,
        )
        d = limits.to_dict()
        self.assertTrue(d["supported"])
        self.assertEqual(d["pl1_watts"], 28.0)
        self.assertEqual(d["pl2_watts"], 64.0)

    def test_rapl_invalid_inputs(self):
        # Negative or zero watts
        ok, err = set_rapl_limits(0, 50)
        self.assertFalse(ok)

        # PL1 greater than PL2
        ok, err = set_rapl_limits(65, 45)
        self.assertFalse(ok)
        self.assertIn("cannot exceed", err)


if __name__ == "__main__":
    unittest.main()
