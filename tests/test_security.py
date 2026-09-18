"""Tests for ClamAV security integration and battery power awareness."""

from pathlib import Path
from unittest.mock import patch
import unittest

from thinknux.core.security import (
    append_security_log,
    clear_security_log,
    get_recent_security_logs,
    is_on_battery,
    resolve_scan_target,
    run_auto_protection_cycle,
)


class TestSecurityPower(unittest.TestCase):
    def test_resolve_scan_target(self):
        target_dl = resolve_scan_target("downloads")
        self.assertTrue(len(target_dl) > 0)
        target_doc = resolve_scan_target("documents")
        self.assertTrue(len(target_doc) > 0)

    @patch("pathlib.Path.is_dir")
    def test_is_on_battery_no_sysfs(self, mock_is_dir):
        mock_is_dir.return_value = False
        self.assertFalse(is_on_battery())

    @patch("thinknux.core.security.is_on_battery")
    @patch("thinknux.core.security.scan_path")
    def test_auto_protection_pauses_on_battery(self, mock_scan, mock_battery):
        mock_battery.return_value = True

        # When pause_on_battery is True and on battery, scan_path must not be called
        run_auto_protection_cycle(
            auto_update=False,
            auto_scan=True,
            scan_interval_hours=0,
            scan_target_key="downloads",
            pause_on_battery=True,
        )
        mock_scan.assert_not_called()


class TestSecurityLogging(unittest.TestCase):
    def setUp(self):
        self.test_log_dir = Path("/tmp/thinknux_test_log")
        self.test_log_dir.mkdir(parents=True, exist_ok=True)
        self.test_log_file = self.test_log_dir / "clamav_scan.log"
        if self.test_log_file.exists():
            self.test_log_file.unlink()

    def tearDown(self):
        if self.test_log_file.exists():
            self.test_log_file.unlink()
        if self.test_log_dir.exists():
            self.test_log_dir.rmdir()

    @patch("thinknux.core.security.get_security_log_path")
    def test_append_and_get_logs(self, mock_path):
        mock_path.return_value = self.test_log_file

        self.assertEqual(get_recent_security_logs(), [])

        append_security_log("Test log entry 1")
        append_security_log("Test log entry 2")

        logs = get_recent_security_logs()
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0], "Test log entry 1")
        self.assertEqual(logs[1], "Test log entry 2")

    @patch("thinknux.core.security.get_security_log_path")
    def test_clear_logs(self, mock_path):
        mock_path.return_value = self.test_log_file

        append_security_log("Entry before clear")
        self.assertEqual(len(get_recent_security_logs()), 1)

        clear_security_log()
        self.assertEqual(get_recent_security_logs(), [])


if __name__ == "__main__":
    unittest.main()
