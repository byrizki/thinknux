"""Metric card composite widget for dashboard indicators."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk


class MetricCard(Gtk.Box):
    """Composite card displaying an icon, title, value, and subtitle or progress bar."""

    def __init__(self, title: str, icon_name: str, initial_value: str = "--", subtitle: str = ""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class("metric-card")
        self.set_hexpand(True)

        # Header with icon and title
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._icon = Gtk.Image.new_from_icon_name(icon_name)
        self._icon.set_icon_size(Gtk.IconSize.NORMAL)
        self._icon.add_css_class("thinkpad-red")
        header.append(self._icon)

        self._title_label = Gtk.Label(label=title, xalign=0.0)
        self._title_label.add_css_class("metric-title")
        self._title_label.set_hexpand(True)
        header.append(self._title_label)

        self.append(header)

        # Main value
        self._value_label = Gtk.Label(label=initial_value, xalign=0.0)
        self._value_label.add_css_class("metric-value")
        self.append(self._value_label)

        # Optional Subtitle
        self._subtitle_label = Gtk.Label(label=subtitle, xalign=0.0)
        self._subtitle_label.add_css_class("metric-subtitle")
        self.append(self._subtitle_label)

        # Optional Progress Bar
        self._progress = Gtk.ProgressBar()
        self._progress.set_margin_top(2)
        self._progress.set_visible(False)
        self.append(self._progress)

    def set_value(self, text: str) -> None:
        self._value_label.set_text(text)

    def set_subtitle(self, text: str) -> None:
        self._subtitle_label.set_text(text)

    def set_fraction(self, fraction: float) -> None:
        self._progress.set_fraction(max(0.0, min(1.0, fraction)))
        self._progress.set_visible(True)
