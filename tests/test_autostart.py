"""Tests for XDG autostart configuration."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from thinknux.core.autostart import is_autostart_enabled, set_autostart


class TestAutostart(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_file = Path(self.temp_dir.name) / "com.byrizki.thinknux.desktop"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_autostart_toggle(self):
        with patch("thinknux.core.autostart.AUTOSTART_FILE", self.mock_file), \
             patch("thinknux.core.autostart.AUTOSTART_DIR", Path(self.temp_dir.name)):
            self.assertFalse(is_autostart_enabled())

            # Enable autostart
            ok = set_autostart(True)
            self.assertTrue(ok)
            self.assertTrue(self.mock_file.is_file())
            self.assertTrue(is_autostart_enabled())

            content = self.mock_file.read_text(encoding="utf-8")
            self.assertIn("[Desktop Entry]", content)
            self.assertIn("--minimized", content)

            # Disable autostart
            ok = set_autostart(False)
            self.assertTrue(ok)
            self.assertFalse(self.mock_file.exists())
            self.assertFalse(is_autostart_enabled())


if __name__ == "__main__":
    unittest.main()
