"""Tests for UI assets and view aliases."""

from pathlib import Path
import unittest

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from thinknux.ui.views.hardware_tweaks_view import HardwareTweaksView
from thinknux.ui.views.system_view import SystemView


class TestUiAssets(unittest.TestCase):
    def test_fan_symbolic_icon_exists(self):
        icon_path = Path(__file__).parent.parent / "thinknux" / "ui" / "icons" / "fan-symbolic.svg"
        self.assertTrue(icon_path.is_file())
        content = icon_path.read_text(encoding="utf-8")
        self.assertIn("<svg", content)
        self.assertIn("currentColor", content)

    def test_icon_theme_loads_custom_icons(self):
        icons_dir = Path(__file__).parent.parent / "thinknux" / "ui" / "icons"
        display = Gdk.Display.get_default()
        if display:
            theme = Gtk.IconTheme.get_for_display(display)
            theme.add_search_path(str(icons_dir))
            self.assertTrue(theme.has_icon("fan-symbolic"))
            self.assertTrue(theme.has_icon("sensors-fan-symbolic"))
            self.assertTrue(theme.has_icon("sensors-temperature-symbolic"))
            self.assertTrue(theme.has_icon("temperature-symbolic"))
            self.assertTrue(theme.has_icon("cpu-symbolic"))
            self.assertTrue(theme.has_icon("computer-chip-symbolic"))

    def test_hardware_tweaks_view_alias(self):
        # HardwareTweaksView must be identical to SystemView for backwards compatibility
        self.assertIs(HardwareTweaksView, SystemView)


if __name__ == "__main__":
    unittest.main()
