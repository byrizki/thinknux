"""Tests for settings persistence and JSON storage."""

from pathlib import Path
import tempfile
import unittest

from thinknux.core.settings import SettingsManager
from thinknux.models.settings import AppSettings, UserSettings


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.mgr = SettingsManager(config_file=self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_settings(self):
        settings = self.mgr.settings
        self.assertEqual(settings.user.fan_mode, "auto")
        self.assertEqual(settings.user.theme, "system")
        self.assertTrue(settings.user.minimize_to_tray)
        self.assertTrue(settings.user.clamav_auto_update)
        self.assertTrue(settings.user.clamav_auto_scan)
        self.assertEqual(settings.user.clamav_scan_interval_hours, 24)
        self.assertEqual(settings.user.clamav_scan_target, "downloads")
        self.assertTrue(settings.user.clamav_pause_on_battery)
        self.assertEqual(settings.user.clamav_max_file_size_mb, 25)
        self.assertTrue(settings.user.auto_adjust_rapl)

    def test_save_and_reload_settings(self):
        new_user = UserSettings(
            fan_mode="manual",
            fan_level=5,
            auto_start=False,
            minimize_to_tray=False,
            theme="dark",
            battery_start_threshold=45,
            battery_stop_threshold=85,
            clamav_auto_update=False,
            clamav_auto_scan=True,
            clamav_scan_interval_hours=12,
            clamav_scan_target="home",
            clamav_pause_on_battery=False,
            clamav_max_file_size_mb=50,
            auto_adjust_rapl=False,
        )
        self.mgr.update_user_settings(new_user)
        self.assertTrue(self.config_path.is_file())

        # Reload with separate manager instance pointing to same file
        reloaded_mgr = SettingsManager(config_file=self.config_path)
        reloaded = reloaded_mgr.settings
        self.assertEqual(reloaded.user.fan_mode, "manual")
        self.assertEqual(reloaded.user.fan_level, 5)
        self.assertEqual(reloaded.user.theme, "dark")
        self.assertEqual(reloaded.user.battery_start_threshold, 45)
        self.assertEqual(reloaded.user.battery_stop_threshold, 85)
        self.assertFalse(reloaded.user.clamav_auto_update)
        self.assertTrue(reloaded.user.clamav_auto_scan)
        self.assertEqual(reloaded.user.clamav_scan_interval_hours, 12)
        self.assertEqual(reloaded.user.clamav_scan_target, "home")
        self.assertFalse(reloaded.user.clamav_pause_on_battery)
        self.assertEqual(reloaded.user.clamav_max_file_size_mb, 50)
        self.assertFalse(reloaded.user.auto_adjust_rapl)


if __name__ == "__main__":
    unittest.main()
