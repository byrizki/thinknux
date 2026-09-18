"""Feature views for ThinkNux application."""

from .battery_view import BatteryView
from .fan_view import FanView
from .hardware_tweaks_view import HardwareTweaksView
from .home_view import HomeView
from .monitor_view import MonitorView
from .performance_view import PerformanceView
from .security_view import SecurityView
from .system_view import SystemView

__all__ = [
    "HomeView",
    "FanView",
    "BatteryView",
    "PerformanceView",
    "HardwareTweaksView",
    "MonitorView",
    "SystemView",
    "SecurityView",
]
