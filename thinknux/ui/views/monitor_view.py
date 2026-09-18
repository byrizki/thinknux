"""System monitor view displaying per-core CPU, memory, disk, network, and processes."""

from typing import List, Optional, Tuple

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from ...core.hardware.monitor import collect_system_stats
from ...core.telemetry import TelemetryService, TelemetrySnapshot, get_telemetry_service
from ...models.monitor import SystemMonitor
from .base_view import BaseView


class MonitorView(BaseView):
    """Real-time system telemetry and process inspection view."""

    def __init__(self, telemetry_service: Optional[TelemetryService] = None):
        super().__init__(title="System Monitor", subtitle="Hardware utilization, disk mounts, and process resource consumers")

        self._telemetry: TelemetryService = telemetry_service or get_telemetry_service()
        self._core_widgets: List[Tuple[Gtk.Box, Gtk.ProgressBar, Gtk.Label]] = []
        self._disk_widgets: List[Tuple[Adw.ActionRow, Gtk.ProgressBar]] = []
        self._proc_widgets: List[Tuple[Adw.ActionRow, Gtk.Label]] = []

        # 1. CPU and Cores
        self._cpu_group = Adw.PreferencesGroup(title="CPU Utilization and Cores")
        self._core_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._cpu_group.add(self._core_box)
        self.content_box.append(self._cpu_group)

        # 2. Memory and Swap
        self._mem_group = Adw.PreferencesGroup(title="Memory and Swap")

        self._ram_row = Adw.ActionRow(title="RAM Usage", subtitle="Used: -- / Total: --")
        self._ram_bar = Gtk.ProgressBar()
        self._ram_bar.set_hexpand(True)
        self._ram_bar.set_margin_top(8)
        self._ram_row.add_suffix(self._ram_bar)
        self._mem_group.add(self._ram_row)

        self._swap_row = Adw.ActionRow(title="Swap Space", subtitle="Used: -- / Total: --")
        self._swap_bar = Gtk.ProgressBar()
        self._swap_bar.set_hexpand(True)
        self._swap_bar.set_margin_top(8)
        self._swap_row.add_suffix(self._swap_bar)
        self._mem_group.add(self._swap_row)

        self.content_box.append(self._mem_group)

        # 3. Disks
        self._disk_group = Adw.PreferencesGroup(title="Storage and Mounted Filesystems")
        self._disk_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._disk_group.add(self._disk_box)
        self.content_box.append(self._disk_group)

        # 4. Top Processes
        self._proc_group = Adw.PreferencesGroup(title="Top Processes by CPU / Memory")
        self._proc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._proc_group.add(self._proc_box)
        self.content_box.append(self._proc_group)

        # Subscribe to telemetry
        if self._telemetry:
            self._telemetry.subscribe("monitor", self._on_telemetry_update)
            snap = self._telemetry.snapshot
            if snap.monitor_stats:
                self._update_ui(snap.monitor_stats)

    def _on_telemetry_update(self, snapshot: TelemetrySnapshot) -> None:
        if snapshot.monitor_stats is not None:
            self._update_ui(snapshot.monitor_stats)

    def refresh(self) -> None:
        if self._telemetry:
            snap = self._telemetry.snapshot
            if snap.monitor_stats is not None:
                self._update_ui(snap.monitor_stats)
            self._telemetry.request_poll()
        else:
            stats = collect_system_stats(include_processes=True)
            self._update_ui(stats)

    def _update_ui(self, stats: SystemMonitor) -> None:
        # Update CPU Cores (reuse existing widgets to avoid GTK layout churn)
        cores = stats.cpu.cores
        if len(self._core_widgets) != len(cores):
            while child := self._core_box.get_first_child():
                self._core_box.remove(child)
            self._core_widgets.clear()

            for core in cores:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                lbl = Gtk.Label(label=f"Core {core.core_id}", xalign=0.0)
                lbl.set_size_request(60, -1)
                row.append(lbl)

                bar = Gtk.ProgressBar()
                bar.set_hexpand(True)
                row.append(bar)

                val_lbl = Gtk.Label(xalign=1.0)
                val_lbl.set_size_request(110, -1)
                row.append(val_lbl)

                self._core_box.append(row)
                self._core_widgets.append((row, bar, val_lbl))

        for idx, core in enumerate(cores):
            _, bar, val_lbl = self._core_widgets[idx]
            bar.set_fraction(core.usage_percent / 100.0)
            val_lbl.set_text(f"{int(round(core.usage_percent))}% ({core.frequency} MHz)")

        # Memory & Swap
        mem = stats.memory
        used_gb = round(mem.used / (1024 * 1024 * 1024), 2)
        total_gb = round(mem.total / (1024 * 1024 * 1024), 2)
        self._ram_row.set_subtitle(f"Used: {used_gb} GB / Total: {total_gb} GB ({int(round(mem.usage_percent))}%)")
        self._ram_bar.set_fraction(mem.usage_percent / 100.0)

        if mem.swap_total > 0:
            s_used = round(mem.swap_used / (1024 * 1024 * 1024), 2)
            s_total = round(mem.swap_total / (1024 * 1024 * 1024), 2)
            s_pct = round((mem.swap_used / mem.swap_total) * 100.0, 1)
            self._swap_row.set_subtitle(f"Used: {s_used} GB / Total: {s_total} GB ({s_pct}%)")
            self._swap_bar.set_fraction(mem.swap_used / mem.swap_total)
        else:
            self._swap_row.set_subtitle("No swap configured")
            self._swap_bar.set_fraction(0.0)

        # Disks
        disks = stats.disk
        if len(self._disk_widgets) != len(disks):
            while child := self._disk_box.get_first_child():
                self._disk_box.remove(child)
            self._disk_widgets.clear()

            for _ in disks:
                d_row = Adw.ActionRow()
                d_bar = Gtk.ProgressBar()
                d_bar.set_hexpand(True)
                d_row.add_suffix(d_bar)
                self._disk_box.append(d_row)
                self._disk_widgets.append((d_row, d_bar))

        for idx, d in enumerate(disks):
            d_row, d_bar = self._disk_widgets[idx]
            used_g = round(d.used / (1024 * 1024 * 1024), 1)
            total_g = round(d.total / (1024 * 1024 * 1024), 1)
            d_row.set_title(f"{d.mount_point} ({d.device})")
            d_row.set_subtitle(f"{used_g} / {total_g} GB ({int(round(d.usage_percent))}%) - {d.filesystem}")
            d_bar.set_fraction(d.usage_percent / 100.0)

        # Top processes (up to 10)
        procs = stats.processes[:10]
        if len(self._proc_widgets) != len(procs):
            while child := self._proc_box.get_first_child():
                self._proc_box.remove(child)
            self._proc_widgets.clear()

            for _ in procs:
                p_row = Adw.ActionRow()
                metric_lbl = Gtk.Label()
                metric_lbl.add_css_class("caption")
                p_row.add_suffix(metric_lbl)
                self._proc_box.append(p_row)
                self._proc_widgets.append((p_row, metric_lbl))

        for idx, p in enumerate(procs):
            p_row, metric_lbl = self._proc_widgets[idx]
            p_row.set_title(p.name)
            p_row.set_subtitle(f"PID: {p.pid} | Status: {p.status}")
            metric_lbl.set_text(f"{p.cpu_percent}% CPU | {p.memory_mb} MB RAM")
