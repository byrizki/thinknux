"""Permissions warning banner composite widget."""

import threading
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk

from ...core.permissions import check_permissions_status, setup_permissions


class PermissionBanner(Gtk.Box):
    """Actionable warning banner informing user of missing sysfs or Polkit permissions."""

    def __init__(self, on_configured: Optional[Callable[[], None]] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._on_configured = on_configured

        self.add_css_class("warning")
        self.add_css_class("card")
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_visible(False)

        # Warning icon
        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        self.append(icon)

        # Text box
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        self._title = Gtk.Label(label="Elevated Permissions Required", xalign=0.0)
        self._title.add_css_class("heading")
        text_box.append(self._title)

        self._desc = Gtk.Label(
            label="Hardware control for fan speeds, CPU governor, and battery thresholds requires elevated access.",
            xalign=0.0,
            wrap=True,
        )
        self._desc.add_css_class("caption")
        text_box.append(self._desc)
        self.append(text_box)

        # Button and spinner
        self._btn = Gtk.Button(label="Grant Permissions")
        self._btn.add_css_class("suggested-action")
        self._btn.connect("clicked", self._on_grant_clicked)
        self.append(self._btn)

        self._spinner = Gtk.Spinner()
        self._spinner.set_visible(False)
        self.append(self._spinner)

        self.check_status()

    def check_status(self) -> None:
        def worker():
            has_perms, _ = check_permissions_status()
            GLib.idle_add(self.set_visible, not has_perms)

        threading.Thread(target=worker, daemon=True).start()

    def _on_grant_clicked(self, _button: Gtk.Button) -> None:
        self._btn.set_sensitive(False)
        self._spinner.set_visible(True)
        self._spinner.start()

        def worker():
            success, msg = setup_permissions()
            GLib.idle_add(self._on_setup_completed, success, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_setup_completed(self, success: bool, msg: str) -> None:
        self._spinner.stop()
        self._spinner.set_visible(False)
        self._btn.set_sensitive(True)
        self.check_status()
        if success and self._on_configured:
            self._on_configured()
