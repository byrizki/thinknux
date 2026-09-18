import datetime
import os
from pathlib import Path
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ...core.security import (
    check_freshclam_service_active,
    clear_security_log,
    get_recent_security_logs,
    get_security_status,
    scan_path,
    set_freshclam_service,
    update_virus_definitions,
)
from ...core.settings import get_settings_manager
from .base_view import BaseView


class SecurityView(BaseView):
    """Antivirus management view providing ClamAV status, scanning, and definition updates."""

    def __init__(self):
        super().__init__(title="Security and Antivirus", subtitle="ClamAV malware protection, threat scanning, and virus database")
        self._settings_mgr = get_settings_manager()
        self._updating = False
        self._scanning = False

        # 1. ClamAV Status Group
        status_group = Adw.PreferencesGroup(title="Antivirus Engine Status")

        self._installed_row = Adw.ActionRow(title="ClamAV Engine")
        self._installed_badge = Gtk.Label()
        self._installed_badge.add_css_class("badge-status")
        self._installed_row.add_suffix(self._installed_badge)
        status_group.add(self._installed_row)

        self._db_row = Adw.ActionRow(title="Signatures Database", subtitle="Version: -- | Updated: --")
        self._btn_update = Gtk.Button(label="Update Definitions")
        self._btn_update.connect("clicked", self._on_update_clicked)
        self._db_row.add_suffix(self._btn_update)
        status_group.add(self._db_row)

        self.content_box.append(status_group)

        # 2. Automation & Background Protection Group
        auto_group = Adw.PreferencesGroup(title="Automation and Background Protection")

        self._auto_update_switch = Adw.SwitchRow(title="Auto-Update Virus Definitions")
        self._auto_update_switch.set_subtitle("Automatically download fresh malware signatures in the background")
        self._auto_update_switch.connect("notify::active", self._on_auto_update_toggled)
        auto_group.add(self._auto_update_switch)

        self._auto_scan_switch = Adw.SwitchRow(title="Background Auto-Scan Protection")
        self._auto_scan_switch.set_subtitle("Automatically scan directories in background with low CPU/IO priority")
        self._auto_scan_switch.connect("notify::active", self._on_auto_scan_toggled)
        auto_group.add(self._auto_scan_switch)

        self._scan_target_row = Adw.ComboRow(title="Auto-Scan Target Directory")
        target_model = Gtk.StringList.new(["Downloads Folder (~/Downloads)", "User Home Directory"])
        self._scan_target_row.set_model(target_model)
        self._scan_target_row.connect("notify::selected", self._on_scan_target_changed)
        auto_group.add(self._scan_target_row)

        self._scan_freq_row = Adw.ComboRow(title="Auto-Scan Schedule")
        freq_model = Gtk.StringList.new(["Every 12 Hours", "Daily (Every 24 Hours)", "Weekly (Every 7 Days)"])
        self._scan_freq_row.set_model(freq_model)
        self._scan_freq_row.connect("notify::selected", self._on_scan_freq_changed)
        auto_group.add(self._scan_freq_row)

        self._pause_battery_switch = Adw.SwitchRow(title="Pause Scanning on Battery Power")
        self._pause_battery_switch.set_subtitle("Postpone automatic background scans when running on battery to conserve power")
        self._pause_battery_switch.connect("notify::active", self._on_pause_battery_toggled)
        auto_group.add(self._pause_battery_switch)

        self._max_size_row = Adw.ComboRow(title="Max Background File Size")
        self._max_size_row.set_subtitle("Skip large media/archives in background scans to avoid pegging CPU/IO")
        size_model = Gtk.StringList.new(["10 MB", "25 MB (Recommended)", "50 MB", "100 MB", "Unlimited"])
        self._max_size_row.set_model(size_model)
        self._max_size_row.connect("notify::selected", self._on_max_size_changed)
        auto_group.add(self._max_size_row)

        self.content_box.append(auto_group)

        # 2. Scanning Actions
        scan_group = Adw.PreferencesGroup(title="Virus Scanning")

        scan_row = Adw.ActionRow(title="Start Scan", subtitle="Scan filesystem for malicious signatures")
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._btn_quick = Gtk.Button(label="Quick Scan (Home)")
        self._btn_quick.connect("clicked", self._on_quick_scan_clicked)
        btn_box.append(self._btn_quick)

        self._btn_custom = Gtk.Button(label="Scan Folder...")
        self._btn_custom.connect("clicked", self._on_custom_scan_clicked)
        btn_box.append(self._btn_custom)

        scan_row.add_suffix(btn_box)
        scan_group.add(scan_row)

        self._scan_status_label = Gtk.Label(label="", xalign=0.0)
        self._scan_status_label.add_css_class("caption")
        self._scan_status_label.set_margin_start(12)
        scan_group.add(self._scan_status_label)

        self.content_box.append(scan_group)

        # 3. Threat Findings Group
        self._threat_group = Adw.PreferencesGroup(title="Detected Threats")
        self._threat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._threat_group.add(self._threat_box)
        self.content_box.append(self._threat_group)

        # 4. Live Scan Logs
        log_group = Adw.PreferencesGroup(title="Scan Activity and Logs")

        log_action_row = Adw.ActionRow(title="Activity History", subtitle="Manual scans and background protection logs")
        self._btn_clear_log = Gtk.Button(label="Clear History")
        self._btn_clear_log.add_css_class("flat")
        self._btn_clear_log.connect("clicked", self._on_clear_log_clicked)
        log_action_row.add_suffix(self._btn_clear_log)
        log_group.add(log_action_row)

        scrolled_log = Gtk.ScrolledWindow()
        scrolled_log.set_min_content_height(160)

        self._log_view = Gtk.TextView()
        self._log_view.set_editable(False)
        self._log_view.set_monospace(True)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._log_buffer = self._log_view.get_buffer()
        scrolled_log.set_child(self._log_view)
        log_group.add(scrolled_log)

        self.content_box.append(log_group)

        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        try:
            status = get_security_status()
            if status.clamav_installed:
                self._installed_badge.set_text("Installed")
                self._installed_badge.remove_css_class("badge-danger")
                self._installed_badge.add_css_class("badge-success")
                self._btn_quick.set_sensitive(not self._scanning)
                self._btn_custom.set_sensitive(not self._scanning)
                self._btn_update.set_sensitive(not self._scanning)
            else:
                self._installed_badge.set_text("Not Installed")
                self._installed_badge.remove_css_class("badge-success")
                self._installed_badge.add_css_class("badge-danger")
                self._btn_quick.set_sensitive(False)
                self._btn_custom.set_sensitive(False)
                self._btn_update.set_sensitive(False)

            self._db_row.set_subtitle(f"Version: {status.database_version} | Signatures: {status.definitions_count} | Updated: {status.last_update}")

            # Sync automation preferences
            user_cfg = self._settings_mgr.settings.user
            self._auto_update_switch.set_active(user_cfg.clamav_auto_update)
            self._auto_scan_switch.set_active(user_cfg.clamav_auto_scan)
            self._scan_target_row.set_selected(0 if user_cfg.clamav_scan_target == "downloads" else 1)
            if user_cfg.clamav_scan_interval_hours <= 12:
                self._scan_freq_row.set_selected(0)
            elif user_cfg.clamav_scan_interval_hours <= 24:
                self._scan_freq_row.set_selected(1)
            else:
                self._scan_freq_row.set_selected(2)

            self._pause_battery_switch.set_active(user_cfg.clamav_pause_on_battery)

            size_map = {10: 0, 25: 1, 50: 2, 100: 3, 0: 4}
            self._max_size_row.set_selected(size_map.get(user_cfg.clamav_max_file_size_mb, 1))

            if self._log_buffer.get_char_count() == 0:
                recent_logs = get_recent_security_logs(150)
                if recent_logs:
                    self._log_buffer.set_text("\n".join(recent_logs) + "\n")
                else:
                    self._log_buffer.set_text(
                        "================================================================================\n"
                        "ThinkNux ClamAV Security Monitor\n"
                        "Status: Ready. No previous scan history recorded.\n"
                        "Click \"Quick Scan (Home)\" or \"Scan Folder...\" to start scanning.\n"
                        "================================================================================\n"
                    )
                end_iter = self._log_buffer.get_end_iter()
                mark = self._log_buffer.create_mark(None, end_iter, False)
                self._log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        finally:
            self._updating = False

    def _on_auto_update_toggled(self, row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = row.get_active()
        app_settings = self._settings_mgr.settings
        app_settings.user.clamav_auto_update = active
        self._settings_mgr.save(app_settings)

    def _on_auto_scan_toggled(self, row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = row.get_active()
        app_settings = self._settings_mgr.settings
        app_settings.user.clamav_auto_scan = active
        self._settings_mgr.save(app_settings)

    def _on_pause_battery_toggled(self, row: Adw.SwitchRow, _param) -> None:
        if self._updating:
            return
        active = row.get_active()
        app_settings = self._settings_mgr.settings
        app_settings.user.clamav_pause_on_battery = active
        self._settings_mgr.save(app_settings)

    def _on_max_size_changed(self, row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        sel = row.get_selected()
        sizes = [10, 25, 50, 100, 0]
        size = sizes[sel] if sel < len(sizes) else 25
        app_settings = self._settings_mgr.settings
        app_settings.user.clamav_max_file_size_mb = size
        self._settings_mgr.save(app_settings)

    def _on_scan_target_changed(self, row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        sel = row.get_selected()
        target = "downloads" if sel == 0 else "home"
        app_settings = self._settings_mgr.settings
        app_settings.user.clamav_scan_target = target
        self._settings_mgr.save(app_settings)

    def _on_scan_freq_changed(self, row: Adw.ComboRow, _param) -> None:
        if self._updating:
            return
        sel = row.get_selected()
        hours = 12 if sel == 0 else (24 if sel == 1 else 168)
        app_settings = self._settings_mgr.settings
        app_settings.user.clamav_scan_interval_hours = hours
        self._settings_mgr.save(app_settings)

    def _append_log(self, text: str) -> None:
        end_iter = self._log_buffer.get_end_iter()
        self._log_buffer.insert(end_iter, f"{text}\n")
        mark = self._log_buffer.create_mark(None, self._log_buffer.get_end_iter(), False)
        self._log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _on_clear_log_clicked(self, _button: Gtk.Button) -> None:
        clear_security_log()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log_buffer.set_text(f"[{ts}] Scan log history cleared.\n")

    def _on_update_clicked(self, _button: Gtk.Button) -> None:
        self._btn_update.set_sensitive(False)
        self._append_log(">>> Updating virus signatures via freshclam...")

        def worker():
            ok, msg = update_virus_definitions(log_cb=lambda l: GLib.idle_add(self._append_log, l))
            GLib.idle_add(self._on_update_done, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_done(self, ok: bool, msg: str) -> None:
        self._btn_update.set_sensitive(True)
        self._append_log(f">>> {msg}")
        self.refresh()

    def _on_quick_scan_clicked(self, _button: Gtk.Button) -> None:
        home_path = os.path.expanduser("~")
        self._start_scan(home_path)

    def _on_custom_scan_clicked(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Select Folder to Scan")
        dialog.select_folder(self.get_root(), None, self._on_folder_selected)

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._start_scan(folder.get_path())
        except Exception:
            pass

    def _start_scan(self, path_to_scan: str) -> None:
        if self._scanning:
            return
        self._scanning = True
        self._btn_quick.set_sensitive(False)
        self._btn_custom.set_sensitive(False)
        self._scan_status_label.set_text(f"Scanning {path_to_scan}...")
        self._append_log(f">>> Starting scan of {path_to_scan}...")

        # Clear old threats
        while child := self._threat_box.get_first_child():
            self._threat_box.remove(child)

        def worker():
            res = scan_path(path_to_scan, log_cb=lambda l: GLib.idle_add(self._append_log, l))
            GLib.idle_add(self._on_scan_completed, res)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_completed(self, res) -> None:
        self._scanning = False
        self._btn_quick.set_sensitive(True)
        self._btn_custom.set_sensitive(True)
        self._scan_status_label.set_text(f"Scan complete in {res.scan_time}. Files: {res.scanned_files}, Infected: {res.infected_files}")
        self._append_log(f">>> Scan finished: {res.infected_files} threat(s) detected.")

        if res.threats:
            for threat in res.threats:
                row = Adw.ActionRow(title=threat.threat_name, subtitle=threat.file_path)
                badge = Gtk.Label(label="THREAT")
                badge.add_css_class("badge-status")
                badge.add_css_class("badge-danger")
                row.add_suffix(badge)
                self._threat_box.append(row)
        else:
            clean_lbl = Gtk.Label(label="No threats detected.")
            clean_lbl.add_css_class("dim-label")
            self._threat_box.append(clean_lbl)
