"""Unit tests for TrackPoint models and sensitivity bounding."""

import unittest

from thinknux.core.hardware.trackpoint import set_trackpoint_sensitivity
from thinknux.models.trackpoint import TrackpointConfig


class TestTrackpoint(unittest.TestCase):
    def test_trackpoint_config_model(self):
        cfg = TrackpointConfig(
            supported=True,
            sensitivity=140,
            press_to_select=True,
            rate=100,
            resolution=200,
        )
        d = cfg.to_dict()
        self.assertTrue(d["supported"])
        self.assertEqual(d["sensitivity"], 140)
        self.assertTrue(d["press_to_select"])
        self.assertEqual(d["rate"], 100)


if __name__ == "__main__":
    unittest.main()
