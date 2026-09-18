"""Asynchronous background telemetry collection service.

Samples hardware state off the GTK UI thread and posts updates via GLib.idle_add,
ensuring zero main-loop lag or freezing.
"""

from dataclasses import dataclass, field
import threading
import time
from typing import Callable, Dict, List, Optional

try:
    from gi.repository import GLib
    HAS_GLIB = True
except ImportError:
    HAS_GLIB = False

from .hardware.battery import get_battery_info, get_battery_thresholds
from .hardware.fan import get_current_fan_level, get_current_fan_speed_rpm
from .hardware.monitor import collect_quick_cpu_mem, collect_system_stats
from .hardware.performance import (
    get_cpu_info,
    get_power_profile,
    get_turbo_boost_status,
)
from .hardware.thermal import get_cpu_temperature, get_sensor_data
from ..models.fan import SensorData
from ..models.monitor import SystemMonitor


@dataclass
class TelemetrySnapshot:
    """Thread-safe snapshot of system hardware metrics."""
    cpu_percent: float = 0.0
    cpu_temp: Optional[int] = None
    mem_percent: float = 0.0
    mem_used: int = 0
    mem_total: int = 0
    fan_rpm: int = 0
    fan_rpm_str: str = "-- RPM"
    fan_level: str = "--"
    battery_capacity: int = 0
    battery_status: str = "Unknown"
    battery_health: int = 100
    has_battery: bool = False
    power_profile: str = "balanced"
    power_profile_available: List[str] = field(default_factory=lambda: ["power-saver", "balanced", "performance"])
    turbo_enabled: bool = False
    turbo_supported: bool = False
    governor: str = "powersave"
    governor_available: List[str] = field(default_factory=list)
    threshold_start: int = 0
    threshold_stop: int = 100
    monitor_stats: Optional[SystemMonitor] = None
    sensor_data: Optional[SensorData] = None


class TelemetryService:
    """Background hardware sampling daemon."""

    def __init__(self, poll_interval: float = 2.0):
        self._poll_interval = poll_interval
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._subscribers: Dict[str, Callable[[TelemetrySnapshot], None]] = {}
        self._active_view: str = "home"
        self._snapshot = TelemetrySnapshot()
        self._security_tick: int = 25

        # Initial fast sample to populate startup cache
        try:
            self._snapshot = self._sample()
        except Exception:
            pass

    @property
    def snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._snapshot

    def set_active_view(self, view_name: str) -> None:
        """Inform service of current visible view to dynamically tune polling workload."""
        with self._lock:
            self._active_view = view_name
        self._wake_event.set()

    def subscribe(self, name: str, callback: Callable[[TelemetrySnapshot], None]) -> None:
        """Register a callback to receive TelemetrySnapshot on GTK idle."""
        with self._lock:
            self._subscribers[name] = callback
        # Deliver current cached snapshot immediately if GLib is available
        snap = self.snapshot
        if HAS_GLIB:
            GLib.idle_add(callback, snap)
        else:
            callback(snap)

    def unsubscribe(self, name: str) -> None:
        """Remove a registered callback."""
        with self._lock:
            self._subscribers.pop(name, None)

    def request_poll(self) -> None:
        """Trigger an immediate background poll (e.g. after setting change)."""
        self._wake_event.set()

    def start(self) -> None:
        """Start the background sampling thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="ThinkNuxTelemetry"
        )
        self._thread.start()

    def stop(self) -> None:
        """Gracefully stop the background sampling thread."""
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _sample(self) -> TelemetrySnapshot:
        """Perform hardware reads off the main thread."""
        with self._lock:
            active = self._active_view

        # Fast CPU & memory sampling
        cpu_p, mem_p, mem_used, mem_total = collect_quick_cpu_mem()
        cpu_temp = get_cpu_temperature()

        # Fan
        rpm, rpm_str = get_current_fan_speed_rpm()
        fan_level = get_current_fan_level()

        # Battery
        bats = get_battery_info()
        has_bat = len(bats) > 0
        bat_cap = bats[0].capacity if has_bat else 0
        bat_status = bats[0].status if has_bat else "N/A"
        bat_health = bats[0].health if has_bat else 100

        # Power profile (fast sysfs)
        prof = get_power_profile()

        # Governor & Turbo
        cpu_info = get_cpu_info()
        turbo = get_turbo_boost_status()
        thresh = get_battery_thresholds()

        # View-specific on-demand detailed sampling
        monitor_stats = None
        if active == "monitor":
            monitor_stats = collect_system_stats(include_processes=True)

        sensor_data = None
        if active == "fan":
            sensor_data = get_sensor_data()

        return TelemetrySnapshot(
            cpu_percent=cpu_p,
            cpu_temp=cpu_temp,
            mem_percent=mem_p,
            mem_used=mem_used,
            mem_total=mem_total,
            fan_rpm=rpm,
            fan_rpm_str=rpm_str if rpm > 0 else "0 RPM (Idle)",
            fan_level=fan_level,
            battery_capacity=bat_cap,
            battery_status=bat_status,
            battery_health=bat_health,
            has_battery=has_bat,
            power_profile=prof.current,
            power_profile_available=prof.available,
            turbo_enabled=turbo.enabled,
            turbo_supported=turbo.supported,
            governor=cpu_info.governor,
            governor_available=cpu_info.available_governors,
            threshold_start=thresh.start,
            threshold_stop=thresh.stop,
            monitor_stats=monitor_stats,
            sensor_data=sensor_data,
        )

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                snapshot = self._sample()
                with self._lock:
                    self._snapshot = snapshot
                    subscribers = list(self._subscribers.values())

                for callback in subscribers:
                    if HAS_GLIB:
                        GLib.idle_add(callback, snapshot)
                    else:
                        callback(snapshot)
            except Exception:
                pass

            # Periodic background security protection check (~every 60s)
            self._security_tick += 1
            if self._security_tick >= 30:
                self._security_tick = 0
                self._run_security_check()

            self._wake_event.wait(timeout=self._poll_interval)
            self._wake_event.clear()

    def _run_security_check(self) -> None:
        try:
            from .security import run_auto_protection_cycle
            from .settings import get_settings_manager
            user_cfg = get_settings_manager().settings.user
            if user_cfg.clamav_auto_update or user_cfg.clamav_auto_scan:
                threading.Thread(
                    target=run_auto_protection_cycle,
                    args=(
                        user_cfg.clamav_auto_update,
                        user_cfg.clamav_auto_scan,
                        user_cfg.clamav_scan_interval_hours,
                        user_cfg.clamav_scan_target,
                        user_cfg.clamav_pause_on_battery,
                        user_cfg.clamav_max_file_size_mb,
                    ),
                    daemon=True,
                    name="ClamAVAutoProtection",
                ).start()
        except Exception:
            pass


_telemetry_service: Optional[TelemetryService] = None


def get_telemetry_service() -> TelemetryService:
    """Singleton accessor for TelemetryService."""
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service
