"""Battery health monitoring and charge threshold configuration view."""

import threading
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ...core.hardware.battery import (
    get_battery_info,
    get_battery_thresholds,
    get_charge_behaviour,
    set_battery_thresholds,
    set_charge_behaviour,
    threshold_paths,
)
from ...core.settings import get_settings_manager
from ...models.battery import BatteryThresholds
from .base_view import BaseView


class BatteryView(BaseView):
    """View displaying battery telemetry and configuring dual charge limits."""

    def __init__(self):
        super().__init__(title="Battery Management", subtitle="Battery health metrics and longevity charge thresholds")
        self._settings_mgr = get_settings_manager()
        self._updating = False

        # 1. Batteries Status Groups (BAT0, BAT1)
        self._bat_cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.append(self._bat_cards_box)

        # 2. Charge Thresholds Configuration Group
        self._thresh_group = Adw.PreferencesGroup(title="Battery Charge Thresholds")

        # Master On/Off Switch Row
        self._limit_switch = Adw.SwitchRow(title="Battery Charge Limit (Longevity)")
        self._limit_switch.set_subtitle("Stop charging early to prolong battery health")
        self._limit_switch.connect("notify::active", self._on_switch_toggled)
        self._thresh_group.add(self._limit_switch)

        # Quick Presets Row
        preset_row = Adw.ActionRow(title="Quick Presets", subtitle="One-click threshold profiles")
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        btn_longevity = Gtk.Button(label="80% Longevity")
        btn_longevity.set_tooltip_text("Start: 40% | Stop: 80% (Maximum battery lifespan)")
        btn_longevity.connect("clicked", lambda _: self._apply_preset(40, 80))
        btn_box.append(btn_longevity)

        btn_balanced = Gtk.Button(label="85% Balanced")
        btn_balanced.set_tooltip_text("Start: 75% | Stop: 85% (Daily portability and longevity)")
        btn_balanced.connect("clicked", lambda _: self._apply_preset(75, 85))
        btn_box.append(btn_balanced)

        btn_full = Gtk.Button(label="Full 100% (Off)")
        btn_full.set_tooltip_text("Start: 0% | Stop: 100% (No threshold, charge to full)")
        btn_full.connect("clicked", lambda _: self._apply_preset(0, 100))
        btn_box.append(btn_full)

        preset_row.add_suffix(btn_box)
        self._thresh_group.add(preset_row)

        # Custom Thresholds Expander Row
        self._custom_expander = Adw.ExpanderRow(title="Custom Threshold Limits")
        self._custom_expander.set_subtitle("Adjust specific start and stop percentages")

        self._start_spin = Adw.SpinRow.new_with_range(0, 99, 1)
        self._start_spin.set_title("Start Charging Below (%)")
        self._custom_expander.add_row(self._start_spin)

        self._stop_spin = Adw.SpinRow.new_with_range(1, 100, 1)
        self._stop_spin.set_title("Stop Charging Above (%)")
        self._custom_expander.add_row(self._stop_spin)

        apply_row = Adw.ActionRow(title="Apply Custom Values")
        self._btn_apply = Gtk.Button(label="Apply")
        self._btn_apply.add_css_class("suggested-action")
        self._btn_apply.connect("clicked", self._on_apply_custom_clicked)
        apply_row.add_suffix(self._btn_apply)
        self._custom_expander.add_row(apply_row)

        self._thresh_group.add(self._custom_expander)
        self.content_box.append(self._thresh_group)

        # 3. Advanced Power Modes Group (charge_behaviour)
        self._modes_group = Adw.PreferencesGroup(title="Advanced Charging Modes")

        self._inhibit_switch = Adw.SwitchRow(title="Inhibit Charging (AC Bypass)")
        self._inhibit_switch.set_subtitle("Run directly on AC power without charging battery cells (preserves cycle count)")
        self._inhibit_switch.connect("notify::active", self._on_inhibit_toggled)
        self._modes_group.add(self._inhibit_switch)

        discharge_row = Adw.ActionRow(title="Force Battery Discharge", subtitle="Discharge on AC power for cell conditioning / recalibration")
        self._btn_discharge = Gtk.Button(label="Discharge")
        self._btn_discharge.connect("clicked", self._on_discharge_clicked)
        discharge_row.add_suffix(self._btn_discharge)
        self._modes_group.add(discharge_row)

        self.content_box.append(self._modes_group)

        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        try:
            # Clear old battery boxes
            while child := self._bat_cards_box.get_first_child():
                self._bat_cards_box.remove(child)

            bats = get_battery_info()
            if not bats:
                empty_status = Adw.StatusPage(
                    icon_name="battery-missing-symbolic",
                    title="No Battery Detected",
                    description="No power supply battery interface found in /sys/class/power_supply/.",
                )
                self._bat_cards_box.append(empty_status)
            else:
                for b in bats:
                    group = Adw.PreferencesGroup(title=f"{b.name} Details ({b.status})")

                    # Capacity & Health
                    cap_row = Adw.ActionRow(title="Current Charge", subtitle=f"Design: {round(b.energy_design, 1)} Wh | Full: {round(b.energy_full, 1)} Wh")
                    cap_label = Gtk.Label(label=f"{b.capacity}%")
                    cap_label.add_css_class("heading")
                    cap_row.add_suffix(cap_label)
                    group.add(cap_row)

                    health_row = Adw.ActionRow(title="Battery Health", subtitle=f"Cycle Count: {b.cycles} cycles")
                    health_label = Gtk.Label(label=f"{b.health}%")
                    health_label.add_css_class("heading")
                    health_row.add_suffix(health_label)
                    group.add(health_row)

                    # Voltage & Power
                    power_row = Adw.ActionRow(title="Power Consumption", subtitle=f"Voltage: {round(b.voltage, 2)} V | Current: {round(b.current, 2)} A")
                    power_label = Gtk.Label(label=f"{round(b.power, 2)} W")
                    power_label.add_css_class("heading")
                    power_row.add_suffix(power_label)
                    group.add(power_row)

                    self._bat_cards_box.append(group)

            # Threshold controls
            supported = threshold_paths() is not None
            self._thresh_group.set_sensitive(supported)
            if supported:
                thresh = get_battery_thresholds()
                is_limited = thresh.stop < 100
                self._limit_switch.set_active(is_limited)
                if is_limited:
                    self._limit_switch.set_subtitle(f"Active — stops charging at {thresh.stop}% (starts below {thresh.start}%)")
                else:
                    self._limit_switch.set_subtitle("Disabled — charging up to 100% (Maximum capacity)")

                self._start_spin.set_value(thresh.start)
                self._stop_spin.set_value(thresh.stop)

            # Advanced charge behavior
            cb = get_charge_behaviour()
            self._inhibit_switch.set_active(cb == "inhibit-charge")
            if cb == "force-discharge":
                self._btn_discharge.set_label("Stop Discharge")
                self._btn_discharge.add_css_class("destructive-action")
            else:
                self._btn_discharge.set_label("Discharge")
                self._btn_discharge.remove_css_class("destructive-action")
        finally:
            self._updating = False

    def _on_switch_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return

        active = self._limit_switch.get_active()
        if active:
            saved = self._settings_mgr.settings.battery_thresholds
            start = saved.start if (saved and saved.start is not None and saved.start < 100) else 40
            stop = saved.stop if (saved and saved.stop is not None and saved.stop < 100) else 80
            if start >= stop:
                start, stop = 40, 80
            self._apply_thresholds(start, stop)
        else:
            self._apply_thresholds(0, 100)

    def _apply_preset(self, start: int, stop: int) -> None:
        self._start_spin.set_value(start)
        self._stop_spin.set_value(stop)
        self._apply_thresholds(start, stop)

    def _on_apply_custom_clicked(self, _button: Gtk.Button) -> None:
        start = int(self._start_spin.get_value())
        stop = int(self._stop_spin.get_value())

        if start >= stop:
            self._show_toast("Start threshold must be less than stop threshold")
            return
        self._apply_thresholds(start, stop)

    def _apply_thresholds(self, start: int, stop: int) -> None:
        def worker():
            ok, err = set_battery_thresholds(start, stop)
            GLib.idle_add(self._on_thresholds_applied, ok, err, start, stop)

        threading.Thread(target=worker, daemon=True).start()

    def _on_thresholds_applied(self, ok: bool, err: str, start: int, stop: int) -> None:
        if ok:
            if stop < 100:
                self._show_toast(f"Battery limit active: {start}% - {stop}%")
                app_settings = self._settings_mgr.settings
                app_settings.battery_thresholds = BatteryThresholds(start=start, stop=stop)
                self._settings_mgr.save(app_settings)
            else:
                self._show_toast("Battery limit disabled: Full 100% charge")
        else:
            self._show_toast(f"Failed to set thresholds: {err}")
        self.refresh()

    def _show_toast(self, message: str) -> None:
        root = self.get_root()
        if hasattr(root, "show_toast"):
            root.show_toast(message)

    def _on_inhibit_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = self._inhibit_switch.get_active()
        mode = "inhibit-charge" if active else "auto"

        def worker():
            ok, err = set_charge_behaviour(mode)
            msg = "Charging inhibited (AC Bypass active)" if mode == "inhibit-charge" else "Standard charging restored (Auto)"
            GLib.idle_add(self._on_charge_behaviour_done, ok, err, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_discharge_clicked(self, _btn: Gtk.Button) -> None:
        cb = get_charge_behaviour()
        new_mode = "auto" if cb == "force-discharge" else "force-discharge"

        def worker():
            ok, err = set_charge_behaviour(new_mode)
            msg = "Forced battery discharge enabled" if new_mode == "force-discharge" else "Forced discharge stopped"
            GLib.idle_add(self._on_charge_behaviour_done, ok, err, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_charge_behaviour_done(self, ok: bool, err: Optional[str], msg: str) -> None:
        if ok:
            self._show_toast(msg)
        else:
            self._show_toast(f"Error: {err}")
        self.refresh()
