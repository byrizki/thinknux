from pathlib import Path
from typing import Dict, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from ..core.fan_curve import FanCurveManager
from ..core.settings import get_settings_manager
from ..core.telemetry import TelemetryService, get_telemetry_service
from .views.battery_view import BatteryView
from .views.fan_view import FanView
from .views.home_view import HomeView
from .views.monitor_view import MonitorView
from .views.performance_view import PerformanceView
from .views.security_view import SecurityView
from .views.system_view import SystemView
from .widgets.permission_banner import PermissionBanner


class MainWindow(Adw.ApplicationWindow):
    """Primary application window with clean icon sidebar and 7 functional views."""

    def __init__(
        self,
        app: Adw.Application,
        curve_manager: FanCurveManager,
        telemetry_service: Optional[TelemetryService] = None,
    ):
        super().__init__(application=app, title="ThinkNux")
        self.set_default_size(1050, 680)
        self.set_size_request(760, 480)

        self._curve_manager = curve_manager
        self._telemetry_service = telemetry_service or get_telemetry_service()
        self._settings_mgr = get_settings_manager()

        display = Gdk.Display.get_default()
        if display:
            icons_dir = Path(__file__).parent / "icons"
            if icons_dir.is_dir():
                theme = Gtk.IconTheme.get_for_display(display)
                theme.add_search_path(str(icons_dir))

        # Toast Overlay
        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        # Root vertical layout (HeaderBar + Banner + SplitView)
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._toast_overlay.set_child(root_box)

        # Title bar (HeaderBar with close, minimize actions and no description)
        self._header = Adw.HeaderBar()
        self._title_widget = Adw.WindowTitle(title="ThinkNux")
        self._header.set_title_widget(self._title_widget)
        self._header.set_decoration_layout(":minimize,close")
        self._header.set_show_end_title_buttons(True)
        self._header.set_show_start_title_buttons(True)
        root_box.append(self._header)

        # Permission Banner
        self._perm_banner = PermissionBanner(on_configured=self._on_permissions_configured)
        root_box.append(self._perm_banner)

        # Navigation Split View
        self._split_view = Adw.NavigationSplitView()
        self._split_view.set_hexpand(True)
        self._split_view.set_vexpand(True)
        self._split_view.set_min_sidebar_width(58)
        self._split_view.set_max_sidebar_width(64)
        self._split_view.set_collapsed(False)
        root_box.append(self._split_view)

        # 1. Views Stack
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)

        # Instantiate 7 views
        self._views: Dict[str, Gtk.Widget] = {
            "home": HomeView(self._telemetry_service),
            "fan": FanView(self._curve_manager, self._telemetry_service),
            "battery": BatteryView(),
            "performance": PerformanceView(),
            "monitor": MonitorView(self._telemetry_service),
            "system": SystemView(),
            "security": SecurityView(),
        }

        for name, view in self._views.items():
            self._stack.add_named(view, name)

        content_page = Adw.NavigationPage.new(self._stack, "Content")
        self._split_view.set_content(content_page)

        # 2. Sidebar Page (constructed after stack & views are ready)
        sidebar_page = Adw.NavigationPage.new(self._create_sidebar(), "Navigation")
        self._split_view.set_sidebar(sidebar_page)

        # Close request intercept for minimize-to-tray
        self.connect("close-request", self._on_close_requested)

    def _create_sidebar(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_hexpand(False)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(4)
        box.set_margin_end(4)

        # List box for navigation
        self._nav_list = Gtk.ListBox()
        self._nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._nav_list.add_css_class("navigation-sidebar")
        self._nav_list.connect("row-selected", self._on_nav_selected)

        nav_items = [
            ("home", "Home Dashboard", "user-home-symbolic"),
            ("fan", "Fan Control", "fan-symbolic"),
            ("battery", "Battery", "battery-symbolic"),
            ("performance", "Performance", "speedometer-symbolic"),
            ("monitor", "System Monitor", "utilities-system-monitor-symbolic"),
            ("system", "System & Hardware", "computer-symbolic"),
            ("security", "Security", "security-high-symbolic"),
        ]

        self._row_keys = []
        for key, label, icon in nav_items:
            row = Gtk.ListBoxRow()
            row.set_tooltip_text(label)

            icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            icon_box.set_halign(Gtk.Align.CENTER)
            icon_box.set_valign(Gtk.Align.CENTER)
            icon_box.set_margin_top(8)
            icon_box.set_margin_bottom(8)

            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(22)
            icon_box.append(img)

            row.set_child(icon_box)
            self._nav_list.append(row)
            self._row_keys.append(key)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._nav_list)
        box.append(scrolled)

        # Select first row by default
        first_row = self._nav_list.get_row_at_index(0)
        if first_row:
            self._nav_list.select_row(first_row)

        return box

    def _on_nav_selected(self, _list_box: Gtk.ListBox, row: Optional[Gtk.ListBoxRow]) -> None:
        if not row:
            return
        idx = row.get_index()
        if hasattr(self, "_row_keys") and 0 <= idx < len(self._row_keys):
            key = self._row_keys[idx]
            if hasattr(self, "_telemetry_service"):
                self._telemetry_service.set_active_view(key)
            if hasattr(self, "_stack"):
                self._stack.set_visible_child_name(key)
            if hasattr(self, "_views"):
                view = self._views.get(key)
                if view and hasattr(view, "refresh"):
                    view.refresh()

    def _on_permissions_configured(self) -> None:
        self.show_toast("Permissions configured successfully!")
        for view in self._views.values():
            if hasattr(view, "refresh"):
                view.refresh()

    def show_toast(self, message: str) -> None:
        """Display an in-app toast notification."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)

    def _on_close_requested(self, _window: Gtk.Window) -> bool:
        """Hide window if minimize_to_tray is enabled in settings, else quit."""
        user_cfg = self._settings_mgr.settings.user
        if user_cfg.minimize_to_tray:
            self.set_visible(False)
            app = self.get_application()
            if app and hasattr(app, "_tray") and app._tray:
                app._tray.set_window_visible(False)
            return True  # Stop default close
        return False  # Proceed with close
