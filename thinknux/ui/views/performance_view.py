"""Performance tuning view managing CPU governors, power profiles, and turbo boost."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ...core.hardware.performance import (
    apply_rapl_for_profile,
    get_cpu_info,
    get_power_profile,
    get_turbo_boost_status,
    set_cpu_governor,
    set_power_profile,
    set_turbo_boost,
)
from ...core.hardware.rapl import (
    get_rapl_limits,
    is_rapl_supported,
    set_rapl_limits,
)
from ...core.settings import get_settings_manager
from .base_view import BaseView


class PerformanceView(BaseView):
    """View managing CPU governors, frequencies, power profiles, turbo boost, and RAPL limits."""

    def __init__(self):
        super().__init__(title="Performance Tuning", subtitle="CPU frequency scaling, power profiles, and boost management")
        self._settings_mgr = get_settings_manager()
        self._updating = False

        # 1. CPU Scaling Governor
        gov_group = Adw.PreferencesGroup(title="CPU Frequency Scaling")

        self._freq_row = Adw.ActionRow(title="Current Frequency", subtitle="Range: -- to -- MHz")
        self._freq_label = Gtk.Label(label="-- MHz")
        self._freq_label.add_css_class("heading")
        self._freq_row.add_suffix(self._freq_label)
        gov_group.add(self._freq_row)

        self._gov_row = Adw.ComboRow(title="Scaling Governor")
        self._gov_row.connect("notify::selected-item", self._on_governor_selected)
        gov_group.add(self._gov_row)
        self.content_box.append(gov_group)

        # 2. System Power Profiles
        profile_group = Adw.PreferencesGroup(title="System Power Profiles")

        self._profile_row = Adw.ComboRow(title="Active Profile", subtitle="Managed via power-profiles-daemon or TLP")
        self._profile_row.connect("notify::selected-item", self._on_profile_selected)
        profile_group.add(self._profile_row)
        self.content_box.append(profile_group)

        # 3. Turbo Boost
        boost_group = Adw.PreferencesGroup(title="Processor Boost")

        self._turbo_row = Adw.SwitchRow(title="Turbo Boost / Core Performance Boost")
        self._turbo_row.set_subtitle("Allows the CPU to temporarily exceed base clock speeds for burst workloads")
        self._turbo_row.connect("notify::active", self._on_turbo_toggled)
        boost_group.add(self._turbo_row)
        self.content_box.append(boost_group)

        # 4. Intel RAPL Package Power Limits (TDP)
        self._rapl_group = Adw.PreferencesGroup(title="CPU Package Power Limits (Intel RAPL TDP)")

        # Auto-adjust switch
        self._auto_rapl_switch = Adw.SwitchRow(title="Auto-Adjust TDP with Power Profile")
        self._auto_rapl_switch.set_subtitle("Automatically tune PL1/PL2 limits on profile switch (Eco 15W, Balanced 28W, Perf 45W)")
        self._auto_rapl_switch.connect("notify::active", self._on_auto_rapl_toggled)
        self._rapl_group.add(self._auto_rapl_switch)

        # Presets Row with linked buttons
        preset_row = Adw.ActionRow(title="TDP Presets", subtitle="One-click thermal power profiles")
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.add_css_class("linked")

        btn_eco = Gtk.Button(label="Eco (15W)")
        btn_eco.connect("clicked", lambda _: self._apply_rapl_preset(15, 20))
        btn_box.append(btn_eco)

        btn_bal = Gtk.Button(label="Balanced (28W)")
        btn_bal.connect("clicked", lambda _: self._apply_rapl_preset(28, 35))
        btn_box.append(btn_bal)

        btn_perf = Gtk.Button(label="Performance (45W)")
        btn_perf.connect("clicked", lambda _: self._apply_rapl_preset(45, 54))
        btn_box.append(btn_perf)

        btn_max = Gtk.Button(label="Max (64W)")
        btn_max.connect("clicked", lambda _: self._apply_rapl_preset(64, 64))
        btn_box.append(btn_max)

        preset_row.add_suffix(btn_box)
        self._rapl_group.add(preset_row)

        # Custom Limits Expander
        self._custom_rapl_expander = Adw.ExpanderRow(
            title="Custom Power Limits",
            subtitle="Manual fine-tuning for PL1 sustained and PL2 burst wattages",
        )

        self._pl1_spin = Adw.SpinRow.new_with_range(5, 75, 1)
        self._pl1_spin.set_title("PL1 Sustained Power Limit (Watts)")
        self._pl1_spin.set_subtitle("Long-term power clamp under sustained thermal loads")
        self._custom_rapl_expander.add_row(self._pl1_spin)

        self._pl2_spin = Adw.SpinRow.new_with_range(5, 75, 1)
        self._pl2_spin.set_title("PL2 Burst Power Limit (Watts)")
        self._pl2_spin.set_subtitle("Short-term power allowance for burst workloads")
        self._custom_rapl_expander.add_row(self._pl2_spin)

        apply_row = Adw.ActionRow(title="Apply Custom Values")
        self._btn_apply_rapl = Gtk.Button(label="Apply")
        self._btn_apply_rapl.add_css_class("suggested-action")
        self._btn_apply_rapl.connect("clicked", self._on_apply_rapl_clicked)
        apply_row.add_suffix(self._btn_apply_rapl)
        self._custom_rapl_expander.add_row(apply_row)

        self._rapl_group.add(self._custom_rapl_expander)
        self.content_box.append(self._rapl_group)

        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        try:
            # CPU Info
            cpu = get_cpu_info()
            self._freq_label.set_text(f"{cpu.current_freq} MHz")
            self._freq_row.set_subtitle(f"Min: {cpu.min_freq} MHz | Max: {cpu.max_freq} MHz")

            if cpu.available_governors:
                gov_model = Gtk.StringList.new(cpu.available_governors)
                self._gov_row.set_model(gov_model)
                if cpu.governor in cpu.available_governors:
                    idx = cpu.available_governors.index(cpu.governor)
                    self._gov_row.set_selected(idx)

            # Power Profiles
            pp = get_power_profile()
            if pp.available:
                p_model = Gtk.StringList.new(pp.available)
                self._profile_row.set_model(p_model)
                if pp.current in pp.available:
                    idx = pp.available.index(pp.current)
                    self._profile_row.set_selected(idx)

            # Turbo Boost
            turbo = get_turbo_boost_status()
            self._turbo_row.set_sensitive(turbo.supported)
            self._turbo_row.set_active(turbo.enabled)

            # Intel RAPL Power Limits
            rapl = get_rapl_limits()
            self._rapl_group.set_sensitive(rapl.supported)
            self._auto_rapl_switch.set_active(self._settings_mgr.settings.user.auto_adjust_rapl)
            if rapl.supported:
                self._pl1_spin.set_value(rapl.pl1_watts)
                self._pl2_spin.set_value(rapl.pl2_watts)
        finally:
            self._updating = False

    def _on_auto_rapl_toggled(self, row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = row.get_active()
        app_settings = self._settings_mgr.settings
        app_settings.user.auto_adjust_rapl = active
        self._settings_mgr.save(app_settings)

        if active:
            item = self._profile_row.get_selected_item()
            if item:
                prof = item.get_string()
                def worker():
                    ok, err = apply_rapl_for_profile(prof)
                    GLib.idle_add(self._on_action_done, ok, err, f"RAPL auto-adjusted for {prof}")
                threading.Thread(target=worker, daemon=True).start()

    def _apply_rapl_preset(self, pl1: float, pl2: float) -> None:
        self._pl1_spin.set_value(pl1)
        self._pl2_spin.set_value(pl2)
        self._on_apply_rapl_clicked(None)

    def _on_apply_rapl_clicked(self, _button: Gtk.Button) -> None:
        pl1 = float(self._pl1_spin.get_value())
        pl2 = float(self._pl2_spin.get_value())

        def worker():
            ok, err = set_rapl_limits(pl1, pl2)
            GLib.idle_add(self._on_action_done, ok, err, f"RAPL limits set: PL1={pl1}W, PL2={pl2}W")

        threading.Thread(target=worker, daemon=True).start()

    def _on_governor_selected(self, _row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        item = self._gov_row.get_selected_item()
        if not item:
            return
        gov = item.get_string()

        def worker():
            ok, err = set_cpu_governor(gov)
            GLib.idle_add(self._on_action_done, ok, err, f"Governor set to {gov}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_profile_selected(self, _row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        item = self._profile_row.get_selected_item()
        if not item:
            return
        prof = item.get_string()

        def worker():
            ok, err = set_power_profile(prof)
            GLib.idle_add(self._on_action_done, ok, err, f"Power profile set to {prof}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_turbo_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        enabled = self._turbo_row.get_active()

        def worker():
            ok, err = set_turbo_boost(enabled)
            GLib.idle_add(self._on_action_done, ok, err, f"Turbo boost {'enabled' if enabled else 'disabled'}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_action_done(self, ok: bool, err: str, success_msg: str) -> None:
        root = self.get_root()
        if hasattr(root, "show_toast"):
            root.show_toast(success_msg if ok else f"Error: {err}")
        self.refresh()
