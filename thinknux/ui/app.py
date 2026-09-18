"""ThinkNux AdwApplication lifecycle management, style injection, and shutdown cleanup."""

from pathlib import Path
import signal
import sys
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from ..core.fan_curve import FanCurveManager
from ..core.hardware.fan import restore_fan_to_auto_blocking
from ..core.settings import get_settings_manager
from ..core.telemetry import get_telemetry_service
from .widgets.tray import TrayIndicator
from .window import MainWindow

APP_ID = "com.byrizki.thinknux"


class ThinkNuxApplication(Adw.Application):
    """AdwApplication instance managing window lifecycle and failsafe shutdown hooks."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._window: Optional[MainWindow] = None
        self._settings_mgr = get_settings_manager()
        self._curve_mgr = FanCurveManager(self._settings_mgr.settings.fan_curve)
        self._telemetry_service = get_telemetry_service()
        self._tray: Optional[TrayIndicator] = None
        self._start_minimized = False

        self.add_main_option(
            "minimized",
            ord("m"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Start application minimized to system tray",
            None,
        )

        # Signal handlers for clean exit
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self._load_styles()

        # Start telemetry daemon and fan curve manager
        self._telemetry_service.start()
        self._curve_mgr.start()

        # Initialize system tray
        self._tray = TrayIndicator(
            on_show=self._show_window,
            on_hide=self._hide_window,
            on_quit=self.quit,
        )

    def do_activate(self) -> None:
        if not self._window:
            self._window = MainWindow(self, self._curve_mgr, self._telemetry_service)

        if not self._start_minimized:
            self._window.present()
        self._start_minimized = False

        # Ask for root grant on app start if permissions are missing
        self._check_and_prompt_permissions()

    def _check_and_prompt_permissions(self) -> None:
        from ..core.permissions import check_permissions_status, setup_permissions
        import threading
        has_perms, _ = check_permissions_status()
        if not has_perms:
            def worker():
                success, msg = setup_permissions()
                GLib.idle_add(self._on_startup_permissions_completed, success, msg)

            threading.Thread(target=worker, daemon=True).start()

    def _on_startup_permissions_completed(self, success: bool, msg: str) -> None:
        if self._window:
            if hasattr(self._window, "_perm_banner"):
                self._window._perm_banner.check_status()
            if success:
                self._window.show_toast("Hardware permissions granted and configured!")
                for view in self._window._views.values():
                    if hasattr(view, "refresh"):
                        view.refresh()
            else:
                self._window.show_toast(f"Permissions setup: {msg}")

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        options = command_line.get_options_dict()
        if options.contains("minimized"):
            self._start_minimized = True
        self.activate()
        return 0

    def do_shutdown(self) -> None:
        """Invoked on application termination - hands fan control back to firmware."""
        if self._tray:
            self._tray.stop()
        if self._telemetry_service:
            self._telemetry_service.stop()
        if self._curve_mgr:
            self._curve_mgr.stop()
        restore_fan_to_auto_blocking()
        Adw.Application.do_shutdown(self)

    def _show_window(self) -> None:
        if not self._window:
            self.activate()
        else:
            self._window.set_visible(True)
            self._window.present()
        if self._tray:
            self._tray.set_window_visible(True)

    def _hide_window(self) -> None:
        if self._window:
            self._window.set_visible(False)
        if self._tray:
            self._tray.set_window_visible(False)

    def _handle_signal(self, _signum, _frame) -> None:
        restore_fan_to_auto_blocking()
        self.quit()

    def _load_styles(self) -> None:
        display = Gdk.Display.get_default()
        if display:
            icons_dir = Path(__file__).parent / "icons"
            if icons_dir.is_dir():
                theme = Gtk.IconTheme.get_for_display(display)
                theme.add_search_path(str(icons_dir))

        css_file = Path(__file__).parent / "style.css"
        if css_file.is_file():
            try:
                provider = Gtk.CssProvider()
                provider.load_from_path(str(css_file))
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
            except Exception as exc:
                print(f"[ThinkNux] Error loading style.css: {exc}", file=sys.stderr)
