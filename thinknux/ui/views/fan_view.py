"""Fan control view providing mode selection, live RPM monitoring, and curve editor."""

import threading
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ...core.fan_curve import FanCurveManager
from ...core.hardware.fan import (
    get_fan_capability,
    get_fan_status,
    restore_fan_to_auto_blocking,
    set_fan_speed,
)
from ...core.hardware.thermal import get_cpu_temperature, get_sensor_data
from ...core.settings import get_settings_manager
from ...core.telemetry import TelemetryService, TelemetrySnapshot, get_telemetry_service
from ...models.fan import CurvePoint, FanCurveConfig, SensorData
from ..widgets.fan_curve_editor import FanCurveEditor
from ..widgets.sensor_row import SensorRow
from .base_view import BaseView


class FanView(BaseView):
    """View managing manual fan speeds, presets, automated curves, and thermal readings."""

    def __init__(
        self,
        curve_manager: FanCurveManager,
        telemetry_service: Optional[TelemetryService] = None,
    ):
        super().__init__(title="Fan Control", subtitle="ThinkPad cooling management and automated thermal curves")
        self._curve_manager = curve_manager
        self._telemetry: TelemetryService = telemetry_service or get_telemetry_service()
        self._settings_mgr = get_settings_manager()
        self._updating = False
        self._user_interacting = False

        # 1. Capability / Status Banner
        self._cap_group = Adw.PreferencesGroup()
        self._cap_row = Adw.ActionRow(title="Hardware Interface", subtitle="Checking thinkpad_acpi...")
        self._cap_badge = Gtk.Label(label="Checking")
        self._cap_badge.add_css_class("badge-status")
        self._cap_row.add_suffix(self._cap_badge)
        self._cap_group.add(self._cap_row)
        self.content_box.append(self._cap_group)

        # 2. Live Fan Telemetry Group
        self._telemetry_group = Adw.PreferencesGroup(title="Live Fan Telemetry")

        self._speed_row = Adw.ActionRow(title="Fan Speed", icon_name="fan-symbolic")
        self._speed_val = Gtk.Label(label="-- RPM")
        self._speed_val.add_css_class("heading")
        self._speed_val.add_css_class("thinkpad-red")
        self._speed_row.add_suffix(self._speed_val)
        self._telemetry_group.add(self._speed_row)

        self._active_level_row = Adw.ActionRow(title="Active Fan Level", icon_name="speedometer-symbolic")
        self._active_level_val = Gtk.Label(label="--")
        self._active_level_val.add_css_class("heading")
        self._active_level_row.add_suffix(self._active_level_val)
        self._telemetry_group.add(self._active_level_row)

        self.content_box.append(self._telemetry_group)

        # 3. Fan Control Mode
        mode_group = Adw.PreferencesGroup(title="Control Mode")

        self._mode_row = Adw.ComboRow(title="Operating Mode")
        mode_model = Gtk.StringList.new(["Automatic (Firmware)", "Manual Fixed Level", "Full Speed", "Custom Curve"])
        self._mode_row.set_model(mode_model)
        self._mode_row.connect("notify::selected", self._on_mode_changed)
        mode_group.add(self._mode_row)

        # Manual Level Slider
        self._manual_row = Adw.ActionRow(title="Fixed Fan Level", subtitle="Level 0 (off) to 7 (maximum)")
        self._level_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 7, 1)
        self._level_scale.set_draw_value(True)
        self._level_scale.set_digits(0)
        self._level_scale.set_hexpand(True)
        self._level_scale.connect("value-changed", self._on_manual_level_changed)
        self._manual_row.add_suffix(self._level_scale)
        mode_group.add(self._manual_row)

        self.content_box.append(mode_group)

        # 4. Fan Curve Editor Section
        self._curve_group = Adw.PreferencesGroup(title="Interactive Curve Editor")

        cfg = self._curve_manager.config
        self._editor = FanCurveEditor(points=cfg.points, on_changed=self._on_curve_modified)
        self._curve_group.add(self._editor)

        # Presets Box
        preset_row = Adw.ActionRow(title="Presets")
        preset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        btn_quiet = Gtk.Button(label="Quiet")
        btn_quiet.connect("clicked", lambda _: self._apply_preset([
            CurvePoint(45, 0), CurvePoint(55, 1), CurvePoint(65, 2), CurvePoint(75, 4), CurvePoint(85, 7)
        ]))
        preset_box.append(btn_quiet)

        btn_balanced = Gtk.Button(label="Balanced")
        btn_balanced.connect("clicked", lambda _: self._apply_preset([
            CurvePoint(40, 0), CurvePoint(50, 1), CurvePoint(60, 3), CurvePoint(70, 5), CurvePoint(80, 7)
        ]))
        preset_box.append(btn_balanced)

        btn_perf = Gtk.Button(label="Performance")
        btn_perf.connect("clicked", lambda _: self._apply_preset([
            CurvePoint(35, 1), CurvePoint(45, 3), CurvePoint(55, 5), CurvePoint(65, 7), CurvePoint(75, 7)
        ]))
        preset_box.append(btn_perf)

        preset_row.add_suffix(preset_box)
        self._curve_group.add(preset_row)
        self.content_box.append(self._curve_group)

        # 5. Thermal Sensors Section
        self._sensor_group = Adw.PreferencesGroup(title="Thermal Sensors and RPM")
        self.content_box.append(self._sensor_group)
        self._sensor_rows = {}

        self._check_capability()

        # Connect telemetry
        if self._telemetry:
            self._telemetry.subscribe("fan", self._on_telemetry_update)
            self._on_telemetry_update(self._telemetry.snapshot)
        else:
            self.refresh()

    def _check_capability(self) -> None:
        cap = get_fan_capability()
        self._cap_row.set_subtitle(cap.message)
        if cap.readiness == "Ready":
            self._cap_badge.set_text("Ready")
            self._cap_badge.remove_css_class("badge-danger")
            self._cap_badge.add_css_class("badge-success")
        else:
            self._cap_badge.set_text(cap.readiness)
            self._cap_badge.remove_css_class("badge-success")
            self._cap_badge.add_css_class("badge-danger")

    def _on_telemetry_update(self, snapshot: TelemetrySnapshot) -> None:
        self._speed_val.set_text(snapshot.fan_rpm_str)
        self._active_level_val.set_text(snapshot.fan_level.capitalize())

        # Sync mode selection if user is not actively interacting
        if not self._user_interacting:
            self._updating = True
            try:
                cfg = self._curve_manager.config
                current_level = snapshot.fan_level
                if cfg.enabled:
                    self._mode_row.set_selected(3)
                    self._manual_row.set_sensitive(False)
                elif current_level == "full-speed":
                    self._mode_row.set_selected(2)
                    self._manual_row.set_sensitive(False)
                elif current_level.isdigit():
                    self._mode_row.set_selected(1)
                    self._manual_row.set_sensitive(True)
                    self._level_scale.set_value(int(current_level))
                else:
                    self._mode_row.set_selected(0)
                    self._manual_row.set_sensitive(False)
            finally:
                self._updating = False

        # Temperature marker on canvas
        if snapshot.cpu_temp is not None:
            self._editor.set_current_temperature(snapshot.cpu_temp)

        # Sensors
        if snapshot.sensor_data is not None:
            self._update_sensors(snapshot.sensor_data)

    def _update_sensors(self, sensor_data: SensorData) -> None:
        all_readings = {}
        for k, v in sensor_data.fans.items():
            all_readings[k] = (v, "fan-symbolic")
        for k, v in sensor_data.temps.items():
            all_readings[k] = (v, "sensors-temperature-symbolic")

        for key, (val, icon) in all_readings.items():
            if key not in self._sensor_rows:
                row = SensorRow(title=key, initial_value=val, icon_name=icon)
                self._sensor_rows[key] = row
                self._sensor_group.add(row)
            else:
                self._sensor_rows[key].set_value(val)

    def refresh(self) -> None:
        self._check_capability()
        if self._telemetry:
            self._on_telemetry_update(self._telemetry.snapshot)
            self._telemetry.request_poll()
        else:
            from ...core.hardware.fan import get_current_fan_level, get_current_fan_speed_rpm
            rpm, rpm_str = get_current_fan_speed_rpm()
            current_level = get_current_fan_level()
            self._speed_val.set_text(rpm_str if rpm > 0 else "0 RPM (Idle)")
            self._active_level_val.set_text(current_level.capitalize())
            temp = get_cpu_temperature()
            self._editor.set_current_temperature(temp)
            self._update_sensors(get_sensor_data())

    def _on_mode_changed(self, _row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        self._user_interacting = True
        mode_idx = self._mode_row.get_selected()
        if mode_idx == 0:  # Auto
            self._manual_row.set_sensitive(False)
            self._curve_manager.set_config(FanCurveConfig(enabled=False, points=self._editor.points))
            threading.Thread(target=self._apply_mode_worker, args=("auto",), daemon=True).start()
        elif mode_idx == 1:  # Manual
            self._manual_row.set_sensitive(True)
            self._curve_manager.set_config(FanCurveConfig(enabled=False, points=self._editor.points))
            lvl = int(self._level_scale.get_value())
            threading.Thread(target=self._apply_mode_worker, args=(str(lvl),), daemon=True).start()
        elif mode_idx == 2:  # Full Speed
            self._manual_row.set_sensitive(False)
            self._curve_manager.set_config(FanCurveConfig(enabled=False, points=self._editor.points))
            threading.Thread(target=self._apply_mode_worker, args=("full-speed",), daemon=True).start()
        elif mode_idx == 3:  # Custom Curve
            self._manual_row.set_sensitive(False)
            cfg = FanCurveConfig(enabled=True, points=self._editor.points)
            self._curve_manager.set_config(cfg)
            if self._telemetry:
                self._telemetry.request_poll()

    def _apply_mode_worker(self, target: str) -> None:
        if target == "auto":
            restore_fan_to_auto_blocking()
        else:
            set_fan_speed(target)
        if self._telemetry:
            self._telemetry.request_poll()

    def _on_manual_level_changed(self, scale: Gtk.Scale) -> None:
        if self._updating or self._mode_row.get_selected() != 1:
            return
        self._user_interacting = True
        lvl = int(scale.get_value())
        threading.Thread(target=self._apply_mode_worker, args=(str(lvl),), daemon=True).start()

    def _on_curve_modified(self, points: list) -> None:
        cfg = FanCurveConfig(enabled=(self._mode_row.get_selected() == 3), points=points)
        self._curve_manager.set_config(cfg)
        app_settings = self._settings_mgr.settings
        app_settings.fan_curve = cfg
        self._settings_mgr.save(app_settings)

    def _apply_preset(self, points: list) -> None:
        self._editor.set_points(points)
        self._on_curve_modified(points)
