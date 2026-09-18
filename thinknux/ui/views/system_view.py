"""System information and hardware tweaks management view."""

import threading
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ...core.autostart import is_autostart_enabled, set_autostart
from ...core.hardware.firmware import (
    get_firmware_status,
    is_thinklmi_supported,
    set_firmware_attribute,
)
from ...core.hardware.leds import (
    get_available_leds,
    set_led_brightness,
    set_lid_logo_dot_mode,
)
from ...core.hardware.system_info import get_system_info
from ...core.hardware.trackpoint import (
    get_trackpoint_config,
    reset_trackpoint_defaults,
    set_trackpoint_press_to_select,
    set_trackpoint_sensitivity,
)
from ...core.settings import get_settings_manager
from .base_view import BaseView


class SystemView(BaseView):
    """View presenting ThinkPad specifications, BIOS firmware settings, TrackPoint, and OS details."""

    def __init__(self):
        super().__init__(
            title="System & Hardware",
            subtitle="ThinkPad specifications, BIOS firmware settings, TrackPoint, and LEDs",
        )
        self._settings_mgr = get_settings_manager()
        self._updating = False

        # 1. Hardware Specifications Group
        hw_group = Adw.PreferencesGroup(title="Hardware Specifications")

        self._model_row = Adw.ActionRow(title="Model", icon_name="computer-symbolic")
        self._model_val = Gtk.Label()
        self._model_val.add_css_class("heading")
        self._model_row.add_suffix(self._model_val)
        hw_group.add(self._model_row)

        self._cpu_row = Adw.ActionRow(title="Processor", icon_name="computer-chip-symbolic")
        self._cpu_val = Gtk.Label()
        self._cpu_val.add_css_class("heading")
        self._cpu_row.add_suffix(self._cpu_val)
        hw_group.add(self._cpu_row)

        self._mem_row = Adw.ActionRow(title="Installed Memory", icon_name="drive-multidisk-symbolic")
        self._mem_val = Gtk.Label()
        self._mem_val.add_css_class("heading")
        self._mem_row.add_suffix(self._mem_val)
        hw_group.add(self._mem_row)

        self.content_box.append(hw_group)

        # 2. Software and OS Group
        os_group = Adw.PreferencesGroup(title="Software and Kernel")

        self._os_row = Adw.ActionRow(title="Operating System", icon_name="applications-system-symbolic")
        self._os_val = Gtk.Label()
        self._os_val.add_css_class("heading")
        self._os_row.add_suffix(self._os_val)
        os_group.add(self._os_row)

        self._kernel_row = Adw.ActionRow(title="Kernel Version", icon_name="application-x-executable-symbolic")
        self._kernel_val = Gtk.Label()
        self._kernel_val.add_css_class("heading")
        self._kernel_row.add_suffix(self._kernel_val)
        os_group.add(self._kernel_row)

        self._host_row = Adw.ActionRow(title="Hostname", icon_name="network-server-symbolic")
        self._host_val = Gtk.Label()
        self._host_val.add_css_class("heading")
        self._host_row.add_suffix(self._host_val)
        os_group.add(self._host_row)

        self.content_box.append(os_group)

        # 3. ThinkPad BIOS & Keyboard Controls (ThinkLMI)
        self._bios_group = Adw.PreferencesGroup(title="ThinkPad BIOS and Keyboard (ThinkLMI)")

        self._fn_swap_row = Adw.SwitchRow(title="Swap Fn and Ctrl Keys")
        self._fn_swap_row.set_subtitle("Physically swap the bottom-left Fn and Ctrl key functions")
        self._fn_swap_row.connect("notify::active", lambda *_: self._on_bios_toggle("FnCtrlKeySwap", self._fn_swap_row))
        self._bios_group.add(self._fn_swap_row)

        self._fn_primary_row = Adw.SwitchRow(title="F1–F12 as Primary Keys")
        self._fn_primary_row.set_subtitle("Default to standard F1–F12 function keys instead of media hotkeys")
        self._fn_primary_row.connect("notify::active", lambda *_: self._on_bios_toggle("FnKeyAsPrimary", self._fn_primary_row))
        self._bios_group.add(self._fn_primary_row)

        self._usb_row = Adw.SwitchRow(title="Always-On USB Charging")
        self._usb_row.set_subtitle("Charge devices via designated USB port while laptop is sleeping or off")
        self._usb_row.connect("notify::active", lambda *_: self._on_bios_toggle("AlwaysOnUSB", self._usb_row))
        self._bios_group.add(self._usb_row)

        self._sleep_row = Adw.ComboRow(title="Sleep State Mode")
        self._sleep_row.set_subtitle("UEFI power suspend architecture")
        self._sleep_model = Gtk.StringList.new(["Linux (S3 Deep Sleep)", "Windows10 (Modern Standby S0ix)"])
        self._sleep_row.set_model(self._sleep_model)
        self._sleep_row.connect("notify::selected", self._on_sleep_mode_changed)
        self._bios_group.add(self._sleep_row)

        self._lap_row = Adw.SwitchRow(title="Cool and Quiet on Lap")
        self._lap_row.set_subtitle("Reduce skin temperature and fan noise when laptop is resting on your lap")
        self._lap_row.connect("notify::active", lambda *_: self._on_bios_toggle("CoolQuietOnLap", self._lap_row))
        self._bios_group.add(self._lap_row)

        self.content_box.append(self._bios_group)

        # 4. TrackPoint Tuning & Tap-To-Click
        self._tp_group = Adw.PreferencesGroup(title="TrackPoint Configuration")

        self._sens_row = Adw.ActionRow(title="TrackPoint Sensitivity", subtitle="Standard default: 128 (range: 0–255)")
        self._sens_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 5)
        self._sens_scale.set_draw_value(True)
        self._sens_scale.set_digits(0)
        self._sens_scale.set_hexpand(True)
        self._sens_scale.connect("value-changed", self._on_sensitivity_changed)
        self._sens_row.add_suffix(self._sens_scale)
        self._tp_group.add(self._sens_row)

        self._press_row = Adw.SwitchRow(title="Press to Select (Tap-to-Click)")
        self._press_row.set_subtitle("Tapping the red TrackPoint cap registers as a mouse click")
        self._press_row.connect("notify::active", self._on_press_to_select_toggled)
        self._tp_group.add(self._press_row)

        reset_row = Adw.ActionRow(title="Reset TrackPoint to Factory Defaults")
        btn_reset = Gtk.Button(label="Reset")
        btn_reset.connect("clicked", self._on_reset_trackpoint_clicked)
        reset_row.add_suffix(btn_reset)
        self._tp_group.add(reset_row)

        self.content_box.append(self._tp_group)

        # 5. ThinkPad LED Lighting Controls
        self._led_group = Adw.PreferencesGroup(title="ThinkPad LED Lighting")

        self._lid_led_row = Adw.ComboRow(title="Outer Lid Red Dot ('i' LED)")
        self._lid_led_row.set_subtitle("The illuminated red indicator on the ThinkPad lid logo")
        self._lid_model = Gtk.StringList.new(["Solid On", "Turned Off", "Disk Activity Pulse", "CPU Load Pulse"])
        self._lid_led_row.set_model(self._lid_model)
        self._lid_led_row.connect("notify::selected", self._on_lid_led_changed)
        self._led_group.add(self._lid_led_row)

        self._power_led_row = Adw.SwitchRow(title="Power Button LED Ring")
        self._power_led_row.set_subtitle("Illumination around the physical power button")
        self._power_led_row.connect("notify::active", self._on_power_led_toggled)
        self._led_group.add(self._power_led_row)

        self.content_box.append(self._led_group)

        # 6. Application Preferences Group
        app_group = Adw.PreferencesGroup(title="Application Preferences")

        self._autostart_row = Adw.SwitchRow(title="Start Automatically on Login")
        self._autostart_row.set_subtitle("Launch ThinkNux minimized to taskbar on system boot")
        self._autostart_row.connect("notify::active", self._on_autostart_toggled)
        app_group.add(self._autostart_row)

        self._tray_row = Adw.SwitchRow(title="Minimize to System Tray")
        self._tray_row.set_subtitle("Keep running in the background when the main window is closed")
        self._tray_row.connect("notify::active", self._on_tray_toggled)
        app_group.add(self._tray_row)

        self.content_box.append(app_group)

        # 7. About ThinkNux Group
        about_group = Adw.PreferencesGroup(title="About ThinkNux")

        pkg_row = Adw.ActionRow(title="Package / Application ID", icon_name="package-x-generic-symbolic")
        pkg_val = Gtk.Label(label="com.byrizki.thinknux")
        pkg_val.add_css_class("dim-label")
        pkg_row.add_suffix(pkg_val)
        about_group.add(pkg_row)

        creator_row = Adw.ActionRow(title="Creator", icon_name="avatar-default-symbolic")
        creator_val = Gtk.Label(label="Muhamad Rizki")
        creator_val.add_css_class("dim-label")
        creator_row.add_suffix(creator_val)
        about_group.add(creator_row)

        inspire_row = Adw.ActionRow(title="Inspiration", icon_name="starred-symbolic")
        inspire_val = Gtk.Label(label="ThinkUtils (vietanhdev)")
        inspire_val.add_css_class("dim-label")
        inspire_row.add_suffix(inspire_val)
        about_group.add(inspire_row)

        self.content_box.append(about_group)

        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        try:
            info = get_system_info()
            self._model_val.set_text(info.model)
            self._cpu_val.set_text(info.cpu)
            self._mem_val.set_text(info.memory)
            self._os_val.set_text(info.os)
            self._kernel_val.set_text(info.kernel)
            self._host_val.set_text(info.hostname)

            # BIOS / ThinkLMI
            if is_thinklmi_supported():
                self._bios_group.set_sensitive(True)
                st = get_firmware_status()
                attrs = st.attributes

                if "FnCtrlKeySwap" in attrs:
                    self._fn_swap_row.set_active(attrs["FnCtrlKeySwap"].current_value.lower() in ["enable", "enabled", "1"])
                if "FnKeyAsPrimary" in attrs:
                    self._fn_primary_row.set_active(attrs["FnKeyAsPrimary"].current_value.lower() in ["enable", "enabled", "1"])
                if "AlwaysOnUSB" in attrs:
                    self._usb_row.set_active(attrs["AlwaysOnUSB"].current_value.lower() in ["enable", "enabled", "1"])
                if "CoolQuietOnLap" in attrs:
                    self._lap_row.set_active(attrs["CoolQuietOnLap"].current_value.lower() in ["enable", "enabled", "1"])

                if "SleepState" in attrs:
                    cur_sleep = attrs["SleepState"].current_value
                    self._sleep_row.set_selected(0 if cur_sleep == "Linux" else 1)
            else:
                self._bios_group.set_sensitive(False)

            # TrackPoint
            tp = get_trackpoint_config()
            self._tp_group.set_sensitive(tp.supported)
            if tp.supported:
                self._sens_scale.set_value(tp.sensitivity)
                self._press_row.set_active(tp.press_to_select)

            # LEDs
            leds = {l.name: l for l in get_available_leds()}
            if "tpacpi::lid_logo_dot" in leds:
                lid = leds["tpacpi::lid_logo_dot"]
                if lid.current_trigger == "disk-activity":
                    self._lid_led_row.set_selected(2)
                elif lid.current_trigger == "cpu":
                    self._lid_led_row.set_selected(3)
                elif lid.brightness > 0:
                    self._lid_led_row.set_selected(0)
                else:
                    self._lid_led_row.set_selected(1)

            if "tpacpi::power" in leds:
                self._power_led_row.set_active(leds["tpacpi::power"].brightness > 0)

            # App settings
            user_cfg = self._settings_mgr.settings.user
            self._autostart_row.set_active(is_autostart_enabled())
            self._tray_row.set_active(user_cfg.minimize_to_tray)
        finally:
            self._updating = False

    def _on_bios_toggle(self, attr_name: str, switch_row: Adw.SwitchRow) -> None:
        if self._updating:
            return
        val = "Enable" if switch_row.get_active() else "Disable"

        def worker():
            ok, err = set_firmware_attribute(attr_name, val)
            GLib.idle_add(self._on_action_done, ok, err, f"{attr_name} set to {val}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_sleep_mode_changed(self, _row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        selected = self._sleep_row.get_selected()
        val = "Linux" if selected == 0 else "Windows10"

        def worker():
            ok, err = set_firmware_attribute("SleepState", val)
            GLib.idle_add(self._on_action_done, ok, err, f"SleepState set to {val}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_sensitivity_changed(self, scale: Gtk.Scale) -> None:
        if self._updating:
            return
        val = int(scale.get_value())

        def worker():
            ok, err = set_trackpoint_sensitivity(val)
            GLib.idle_add(self._on_action_done, ok, err, f"TrackPoint sensitivity: {val}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_press_to_select_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = self._press_row.get_active()

        def worker():
            ok, err = set_trackpoint_press_to_select(active)
            GLib.idle_add(self._on_action_done, ok, err, f"Press-to-Select {'enabled' if active else 'disabled'}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_reset_trackpoint_clicked(self, _button: Gtk.Button) -> None:
        def worker():
            ok, err = reset_trackpoint_defaults()
            GLib.idle_add(self._on_action_done, ok, err, "TrackPoint reset to factory defaults")

        threading.Thread(target=worker, daemon=True).start()

    def _on_lid_led_changed(self, _row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        idx = self._lid_led_row.get_selected()
        mode_map = {0: "solid", 1: "off", 2: "disk", 3: "cpu"}
        mode = mode_map.get(idx, "solid")

        def worker():
            ok, err = set_lid_logo_dot_mode(mode)
            GLib.idle_add(self._on_action_done, ok, err, f"Lid logo LED mode: {mode}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_power_led_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = self._power_led_row.get_active()

        def worker():
            ok, err = set_led_brightness("tpacpi::power", 255 if active else 0)
            GLib.idle_add(self._on_action_done, ok, err, f"Power button LED {'on' if active else 'off'}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_autostart_toggled(self, row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = row.get_active()
        set_autostart(active)
        app_settings = self._settings_mgr.settings
        app_settings.user.auto_start = active
        self._settings_mgr.save(app_settings)

    def _on_tray_toggled(self, row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = row.get_active()
        app_settings = self._settings_mgr.settings
        app_settings.user.minimize_to_tray = active
        self._settings_mgr.save(app_settings)

    def _on_action_done(self, ok: bool, err: Optional[str], msg: str) -> None:
        root = self.get_root()
        if hasattr(root, "show_toast"):
            root.show_toast(msg if ok else f"Error: {err}")
        self.refresh()
