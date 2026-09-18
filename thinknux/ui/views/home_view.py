"""Home dashboard view displaying real-time system metrics and quick controls."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from typing import Optional

from ...core.hardware.battery import set_battery_thresholds
from ...core.hardware.performance import (
    set_cpu_governor,
    set_power_profile,
    set_turbo_boost,
)
from ...core.settings import get_settings_manager
from ...core.telemetry import TelemetryService, TelemetrySnapshot, get_telemetry_service
from ...models.battery import BatteryThresholds
from ..widgets.metric_card import MetricCard
from .base_view import BaseView


class HomeView(BaseView):
    """Home dashboard with real-time indicators and quick hardware toggles."""

    def __init__(self, telemetry_service: Optional[TelemetryService] = None):
        super().__init__(title="Home Dashboard", subtitle="ThinkPad hardware status and essential controls")
        self._settings_mgr = get_settings_manager()
        self._telemetry = telemetry_service or get_telemetry_service()
        self._updating = False

        # 1. Metric Cards Grid (Compact Spacing)
        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        grid.set_column_homogeneous(True)

        self._card_cpu = MetricCard("CPU Usage", "computer-chip-symbolic", "--%", "Temp: --°C")
        self._card_fan = MetricCard("Fan Speed", "fan-symbolic", "-- RPM", "Mode: --")
        self._card_bat = MetricCard("Battery", "battery-symbolic", "--%", "Status: --")
        self._card_mem = MetricCard("Memory", "drive-multidisk-symbolic", "--%", "Used: --")

        grid.attach(self._card_cpu, 0, 0, 1, 1)
        grid.attach(self._card_fan, 1, 0, 1, 1)
        grid.attach(self._card_bat, 0, 1, 1, 1)
        grid.attach(self._card_mem, 1, 1, 1, 1)
        self.content_box.append(grid)

        # 2. Quick Hardware Controls Group
        pref_group = Adw.PreferencesGroup(title="Quick Hardware Controls")

        # Power Profile buttons
        profile_row = Adw.ActionRow(title="Power Profile", subtitle="System performance vs battery conservation")
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.add_css_class("linked")

        self._btn_saver = Gtk.ToggleButton(label="Power Saver")
        self._btn_balanced = Gtk.ToggleButton(label="Balanced")
        self._btn_perf = Gtk.ToggleButton(label="Performance")

        self._btn_balanced.set_group(self._btn_saver)
        self._btn_perf.set_group(self._btn_saver)

        self._btn_saver.connect("toggled", lambda b: b.get_active() and self._on_profile_clicked("power-saver"))
        self._btn_balanced.connect("toggled", lambda b: b.get_active() and self._on_profile_clicked("balanced"))
        self._btn_perf.connect("toggled", lambda b: b.get_active() and self._on_profile_clicked("performance"))

        btn_box.append(self._btn_saver)
        btn_box.append(self._btn_balanced)
        btn_box.append(self._btn_perf)
        profile_row.add_suffix(btn_box)
        pref_group.add(profile_row)

        # CPU Governor ComboRow
        self._gov_row = Adw.ComboRow(title="CPU Frequency Governor")
        self._gov_row.connect("notify::selected-item", self._on_governor_selected)
        pref_group.add(self._gov_row)

        # Turbo Boost SwitchRow
        self._turbo_row = Adw.SwitchRow(title="Intel Turbo Boost / AMD Boost")
        self._turbo_row.set_subtitle("Allow CPU to scale up to maximum burst frequencies")
        self._turbo_row.connect("notify::active", self._on_turbo_toggled)
        pref_group.add(self._turbo_row)

        # Battery Threshold Toggle SwitchRow
        self._thresh_row = Adw.SwitchRow(title="Battery Charge Limit (Longevity)")
        self._thresh_row.set_subtitle("Stop charging early to preserve battery health")
        self._thresh_row.connect("notify::active", self._on_thresh_toggled)
        pref_group.add(self._thresh_row)

        self.content_box.append(pref_group)

        # Subscribe to asynchronous background telemetry updates
        self._telemetry.subscribe("home", self._on_telemetry_update)

    def _on_telemetry_update(self, snapshot: TelemetrySnapshot) -> None:
        """Update widgets from background telemetry snapshot (runs on GTK thread via idle_add)."""
        self._updating = True
        try:
            # CPU
            temp_str = f"{snapshot.cpu_temp}°C" if snapshot.cpu_temp is not None else "--°C"
            self._card_cpu.set_value(f"{int(round(snapshot.cpu_percent))}%")
            self._card_cpu.set_subtitle(f"Package Temp: {temp_str}")
            self._card_cpu.set_fraction(max(0.0, min(1.0, snapshot.cpu_percent / 100.0)))

            # Fan
            self._card_fan.set_value(snapshot.fan_rpm_str)
            self._card_fan.set_subtitle(f"Level: {snapshot.fan_level}")

            # Battery
            if snapshot.has_battery:
                self._card_bat.set_value(f"{snapshot.battery_capacity}%")
                self._card_bat.set_subtitle(f"{snapshot.battery_status} ({snapshot.battery_health}% health)")
                self._card_bat.set_fraction(max(0.0, min(1.0, snapshot.battery_capacity / 100.0)))
            else:
                self._card_bat.set_value("N/A")
                self._card_bat.set_subtitle("No battery detected")

            # Memory
            mem_pct = int(round(snapshot.mem_percent))
            used_gb = round(snapshot.mem_used / (1024 * 1024 * 1024), 1)
            total_gb = round(snapshot.mem_total / (1024 * 1024 * 1024), 1)
            self._card_mem.set_value(f"{mem_pct}%")
            self._card_mem.set_subtitle(f"{used_gb} / {total_gb} GB")
            self._card_mem.set_fraction(max(0.0, min(1.0, snapshot.mem_percent / 100.0)))

            # Power profile
            if snapshot.power_profile == "power-saver":
                self._btn_saver.set_active(True)
            elif snapshot.power_profile == "performance":
                self._btn_perf.set_active(True)
            else:
                self._btn_balanced.set_active(True)

            # Governor
            if snapshot.governor_available:
                gov_model = Gtk.StringList.new(snapshot.governor_available)
                self._gov_row.set_model(gov_model)
                if snapshot.governor in snapshot.governor_available:
                    idx = snapshot.governor_available.index(snapshot.governor)
                    self._gov_row.set_selected(idx)

            # Turbo
            self._turbo_row.set_sensitive(snapshot.turbo_supported)
            self._turbo_row.set_active(snapshot.turbo_enabled)

            # Battery threshold
            is_limited = snapshot.threshold_stop < 100
            self._thresh_row.set_active(is_limited)
            if is_limited:
                self._thresh_row.set_subtitle(
                    f"Active: stops charging at {snapshot.threshold_stop}% (starts below {snapshot.threshold_start}%)"
                )
            else:
                self._thresh_row.set_subtitle("Disabled: charging to 100% (Maximum capacity)")
        finally:
            self._updating = False

    def refresh(self) -> None:
        """Render cached snapshot immediately and request background poll."""
        self._on_telemetry_update(self._telemetry.snapshot)
        self._telemetry.request_poll()

    def _on_profile_clicked(self, profile: str) -> None:
        if self._updating:
            return
        def worker():
            set_power_profile(profile)
            self._telemetry.request_poll()
        threading.Thread(target=worker, daemon=True).start()

    def _on_governor_selected(self, _row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        item = self._gov_row.get_selected_item()
        if item:
            gov = item.get_string()
            def worker():
                set_cpu_governor(gov)
                self._telemetry.request_poll()
            threading.Thread(target=worker, daemon=True).start()

    def _on_turbo_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        enabled = self._turbo_row.get_active()
        def worker():
            set_turbo_boost(enabled)
            self._telemetry.request_poll()
        threading.Thread(target=worker, daemon=True).start()

    def _on_thresh_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return

        active = self._thresh_row.get_active()
        if active:
            saved = self._settings_mgr.settings.battery_thresholds
            start = saved.start if (saved and saved.start is not None and saved.start < 100) else 40
            stop = saved.stop if (saved and saved.stop is not None and saved.stop < 100) else 80
            if start >= stop:
                start, stop = 40, 80
        else:
            start, stop = 0, 100

        def worker():
            ok, err = set_battery_thresholds(start, stop)
            GLib.idle_add(self._on_thresh_applied, ok, err, start, stop)

        threading.Thread(target=worker, daemon=True).start()

    def _on_thresh_applied(self, ok: bool, err: str, start: int, stop: int) -> None:
        root = self.get_root()
        if ok:
            if stop < 100:
                msg = f"Battery charge limit enabled: {start}% - {stop}%"
                app_settings = self._settings_mgr.settings
                app_settings.battery_thresholds = BatteryThresholds(start=start, stop=stop)
                self._settings_mgr.save(app_settings)
            else:
                msg = "Battery charge limit disabled: Full 100% charge"
            if hasattr(root, "show_toast"):
                root.show_toast(msg)
        else:
            if hasattr(root, "show_toast"):
                root.show_toast(f"Failed to set thresholds: {err}")
        self.refresh()
