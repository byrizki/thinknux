"""Tests for CPU governor validation and performance models."""

import unittest

from thinknux.core.hardware.performance import (
    PROFILE_RAPL_MAPPING,
    apply_rapl_for_profile,
    validate_governor,
)
from thinknux.models.performance import CpuInfo, PowerProfile, TurboBoostStatus


class TestPerformance(unittest.TestCase):
    def test_governor_validation(self):
        # Valid governor names pass character check (even if not available on this specific host)
        for g in ["powersave", "performance", "schedutil", "conservative"]:
            valid, err = validate_governor(g)
            if not valid:
                self.assertIn("not available", err)

        # Malicious or invalid names
        self.assertFalse(validate_governor("powersave; rm -rf /")[0])
        self.assertFalse(validate_governor("Performance")[0])
        self.assertFalse(validate_governor("power-save")[0])
        self.assertFalse(validate_governor("")[0])
        self.assertFalse(validate_governor("a" * 33)[0])

    def test_performance_models(self):
        cpu = CpuInfo(
            governor="powersave",
            min_freq=400,
            max_freq=4800,
            current_freq=1800,
            available_governors=["powersave", "performance"],
        )
        self.assertEqual(cpu.to_dict()["governor"], "powersave")

        pp = PowerProfile(current="balanced", available=["power-saver", "balanced", "performance"])
        self.assertEqual(pp.to_dict()["current"], "balanced")

        turbo = TurboBoostStatus(supported=True, enabled=True)
        self.assertTrue(turbo.to_dict()["enabled"])

    def test_rapl_profile_mapping(self):
        self.assertIn("power-saver", PROFILE_RAPL_MAPPING)
        self.assertIn("balanced", PROFILE_RAPL_MAPPING)
        self.assertIn("performance", PROFILE_RAPL_MAPPING)

        # Power saver should clamp lower than performance
        saver_pl1, saver_pl2 = PROFILE_RAPL_MAPPING["power-saver"]
        bal_pl1, bal_pl2 = PROFILE_RAPL_MAPPING["balanced"]
        perf_pl1, perf_pl2 = PROFILE_RAPL_MAPPING["performance"]

        self.assertLess(saver_pl1, bal_pl1)
        self.assertLess(bal_pl1, perf_pl1)
        self.assertLessEqual(saver_pl1, saver_pl2)
        self.assertLessEqual(bal_pl1, bal_pl2)
        self.assertLessEqual(perf_pl1, perf_pl2)

        # Unknown profile rejected
        ok, err = apply_rapl_for_profile("nonexistent")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
