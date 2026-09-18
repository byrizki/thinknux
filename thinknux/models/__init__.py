"""Domain data models for ThinkNux."""

from .battery import BatteryInfo, BatteryThresholds
from .fan import CurvePoint, FanCapability, FanCurveConfig, FanReadiness, SensorData
from .firmware import FirmwareAttribute, ThinkLmiStatus
from .leds import LedDevice
from .monitor import (
    CoreStats,
    CpuStats,
    DiskStats,
    LoadAverage,
    MemoryStats,
    NetworkStats,
    ProcessInfo,
    SystemMonitor,
)
from .performance import CpuInfo, PowerProfile, TurboBoostStatus
from .rapl import RaplLimits
from .security import InstallResponse, ScanResult, SecurityStatus, ThreatInfo
from .settings import AppSettings, UserSettings
from .system import SystemInfo
from .trackpoint import TrackpointConfig

__all__ = [
    "BatteryInfo",
    "BatteryThresholds",
    "CurvePoint",
    "FanCapability",
    "FanCurveConfig",
    "FanReadiness",
    "SensorData",
    "FirmwareAttribute",
    "ThinkLmiStatus",
    "TrackpointConfig",
    "LedDevice",
    "RaplLimits",
    "CoreStats",
    "CpuStats",
    "DiskStats",
    "LoadAverage",
    "MemoryStats",
    "NetworkStats",
    "ProcessInfo",
    "SystemMonitor",
    "CpuInfo",
    "PowerProfile",
    "TurboBoostStatus",
    "InstallResponse",
    "ScanResult",
    "SecurityStatus",
    "ThreatInfo",
    "AppSettings",
    "UserSettings",
    "SystemInfo",
]
