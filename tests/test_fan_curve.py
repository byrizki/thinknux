"""Tests for fan curve interpolation calculation and boundaries."""

import unittest

from thinknux.core.fan_curve import calculate_fan_level
from thinknux.models.fan import CurvePoint, FanCurveConfig


class TestFanCurve(unittest.TestCase):
    def setUp(self):
        self.points = [
            CurvePoint(temp=40, level=0),
            CurvePoint(temp=50, level=1),
            CurvePoint(temp=60, level=3),
            CurvePoint(temp=70, level=5),
            CurvePoint(temp=80, level=7),
        ]

    def test_empty_points(self):
        self.assertEqual(calculate_fan_level(50, []), 0)

    def test_temperature_below_first_point(self):
        self.assertEqual(calculate_fan_level(30, self.points), 0)
        self.assertEqual(calculate_fan_level(40, self.points), 0)

    def test_temperature_above_last_point(self):
        self.assertEqual(calculate_fan_level(85, self.points), 7)
        self.assertEqual(calculate_fan_level(95, self.points), 7)

    def test_exact_point_matches(self):
        self.assertEqual(calculate_fan_level(50, self.points), 1)
        self.assertEqual(calculate_fan_level(60, self.points), 3)
        self.assertEqual(calculate_fan_level(70, self.points), 5)

    def test_linear_interpolation(self):
        # Between 40 (level 0) and 50 (level 1) -> 45C should round to 0 or 1
        lvl_45 = calculate_fan_level(45, self.points)
        self.assertIn(lvl_45, [0, 1])

        # Between 50 (level 1) and 60 (level 3) -> midpoint 55 is level 2
        self.assertEqual(calculate_fan_level(55, self.points), 2)

        # Between 60 (level 3) and 70 (level 5) -> midpoint 65 is level 4
        self.assertEqual(calculate_fan_level(65, self.points), 4)

        # Between 70 (level 5) and 80 (level 7) -> midpoint 75 is level 6
        self.assertEqual(calculate_fan_level(75, self.points), 6)

    def test_fan_curve_config_model(self):
        cfg = FanCurveConfig(enabled=True, points=self.points)
        d = cfg.to_dict()
        self.assertTrue(d["enabled"])
        self.assertEqual(len(d["points"]), 5)

        restored = FanCurveConfig.from_dict(d)
        self.assertTrue(restored.enabled)
        self.assertEqual(len(restored.points), 5)
        self.assertEqual(restored.points[2].temp, 60)
        self.assertEqual(restored.points[2].level, 3)


if __name__ == "__main__":
    unittest.main()
