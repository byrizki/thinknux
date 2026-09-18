"""Sensor reading list row composite widget."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class SensorRow(Adw.ActionRow):
    """ActionRow displaying a hardware sensor title and live value."""

    def __init__(self, title: str, initial_value: str = "--", icon_name: str = "sensors-temperature-symbolic"):
        super().__init__(title=title)
        self.set_icon_name(icon_name)

        self._value_label = Gtk.Label(label=initial_value)
        self._value_label.add_css_class("heading")
        self.add_suffix(self._value_label)

    def set_value(self, text: str) -> None:
        self._value_label.set_text(text)
