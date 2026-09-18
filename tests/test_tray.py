"""Tests for system tray indicator and dbusmenu layout."""

import unittest

from gi.repository import GLib

from thinknux.ui.widgets.tray import _DBusMenu


class TestTrayDBusMenu(unittest.TestCase):
    def setUp(self):
        self.menu = _DBusMenu(on_toggle=lambda: None, on_quit=lambda: None)

    def test_get_layout_variant_serialization(self):
        # Call GetLayout and test that it satisfies pydbus (u(ia{sv}av)) signature
        revision, layout = self.menu.GetLayout(0, -1, [])
        self.assertEqual(revision, 1)

        fmt = "(u(ia{sv}av))"
        # Must serialize into GLib.Variant without raising TypeError
        v = GLib.Variant(fmt, (revision, layout))
        self.assertEqual(v.get_type_string(), "(u(ia{sv}av))")

    def test_get_layout_child(self):
        revision, child_layout = self.menu.GetLayout(1, -1, [])
        fmt = "(u(ia{sv}av))"
        v = GLib.Variant(fmt, (revision, child_layout))
        self.assertEqual(v.get_type_string(), "(u(ia{sv}av))")

    def test_get_group_properties(self):
        props = self.menu.GetGroupProperties([1, 2], [])
        fmt = "(a(ia{sv}))"
        v = GLib.Variant(fmt, (props,))
        self.assertEqual(v.get_type_string(), "(a(ia{sv}))")

    def test_get_property(self):
        prop = self.menu.GetProperty(1, "label")
        self.assertIsInstance(prop, GLib.Variant)
        self.assertEqual(prop.get_string(), "Show / Hide ThinkNux")

        # Test new quick action labels
        self.assertEqual(self.menu.GetProperty(10, "label").get_string(), "Power: Performance")
        self.assertEqual(self.menu.GetProperty(20, "label").get_string(), "Fan: Auto (BIOS)")
        self.assertEqual(self.menu.GetProperty(30, "label").get_string(), "Battery: 80% Conservation Limit")
        self.assertEqual(self.menu.GetProperty(40, "label").get_string(), "ClamAV: Quick Antivirus Scan")
        self.assertEqual(self.menu.GetProperty(99, "label").get_string(), "Quit ThinkNux")

    def test_menu_children_count(self):
        _, (_, _, children) = self.menu.GetLayout(0, -1, [])
        self.assertEqual(len(children), len(_DBusMenu._MENU_ITEMS))

    def test_toggle_properties(self):
        # Power items have checkmark toggle-type
        for item_id in (10, 11, 12):
            self.assertEqual(self.menu.GetProperty(item_id, "toggle-type").get_string(), "checkmark")
            self.assertIn(self.menu.GetProperty(item_id, "toggle-state").get_int32(), (0, 1))

        # Fan items have checkmark toggle-type
        for item_id in (20, 21, 22):
            self.assertEqual(self.menu.GetProperty(item_id, "toggle-type").get_string(), "checkmark")
            self.assertIn(self.menu.GetProperty(item_id, "toggle-state").get_int32(), (0, 1))

        # AboutToShow returns True to trigger refresh on menu display
        self.assertTrue(self.menu.AboutToShow(0))


if __name__ == "__main__":
    unittest.main()
