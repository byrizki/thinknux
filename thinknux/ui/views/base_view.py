"""Base view component establishing consistent layout, scrolling, and refresh hooks."""

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class BaseView(Gtk.Box):
    """Base class for all feature views providing structured layout and refresh mechanism."""

    def __init__(self, title: str, subtitle: Optional[str] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Header section
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_margin_start(16)
        header_box.set_margin_end(16)
        header_box.set_margin_top(8)
        header_box.set_margin_bottom(4)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title_box.set_hexpand(True)

        title_label = Gtk.Label(label=title, xalign=0.0)
        title_label.add_css_class("title-2")
        title_box.append(title_label)

        header_box.append(title_box)

        # Refresh button
        self._refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self._refresh_btn.set_tooltip_text("Refresh")
        self._refresh_btn.add_css_class("flat")
        self._refresh_btn.connect("clicked", lambda _: self.refresh())
        header_box.append(self._refresh_btn)

        self.append(header_box)

        # Content area inside scrollable clamp
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(820)
        clamp.set_tightening_threshold(600)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.set_margin_start(16)
        self.content_box.set_margin_end(16)
        self.content_box.set_margin_top(4)
        self.content_box.set_margin_bottom(12)

        clamp.set_child(self.content_box)
        scrolled.set_child(clamp)
        self.append(scrolled)

    def refresh(self) -> None:
        """Override in subclasses to reload hardware metrics."""
        pass
