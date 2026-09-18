"""Application and user settings data models."""

from dataclasses import dataclass, field
from typing import Dict, Optional

from .battery import BatteryThresholds
from .fan import FanCurveConfig


@dataclass
class UserSettings:
    fan_mode: str = "auto"
    fan_level: int = 0
    auto_start: bool = False
    minimize_to_tray: bool = True
    theme: str = "system"
    battery_start_threshold: Optional[int] = 40
    battery_stop_threshold: Optional[int] = 80
    clamav_auto_update: bool = True
    clamav_auto_scan: bool = True
    clamav_scan_interval_hours: int = 24
    clamav_scan_target: str = "downloads"
    clamav_pause_on_battery: bool = True
    clamav_max_file_size_mb: int = 25
    auto_adjust_rapl: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "fan_mode": self.fan_mode,
            "fan_level": self.fan_level,
            "auto_start": self.auto_start,
            "minimize_to_tray": self.minimize_to_tray,
            "theme": self.theme,
            "battery_start_threshold": self.battery_start_threshold,
            "battery_stop_threshold": self.battery_stop_threshold,
            "clamav_auto_update": self.clamav_auto_update,
            "clamav_auto_scan": self.clamav_auto_scan,
            "clamav_scan_interval_hours": self.clamav_scan_interval_hours,
            "clamav_scan_target": self.clamav_scan_target,
            "clamav_pause_on_battery": self.clamav_pause_on_battery,
            "clamav_max_file_size_mb": self.clamav_max_file_size_mb,
            "auto_adjust_rapl": self.auto_adjust_rapl,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "UserSettings":
        return cls(
            fan_mode=str(data.get("fan_mode", "auto")),
            fan_level=int(data.get("fan_level", 0)),
            auto_start=bool(data.get("auto_start", False)),
            minimize_to_tray=bool(data.get("minimize_to_tray", True)),
            theme=str(data.get("theme", "system")),
            battery_start_threshold=(
                int(data["battery_start_threshold"])
                if data.get("battery_start_threshold") is not None
                else None
            ),
            battery_stop_threshold=(
                int(data["battery_stop_threshold"])
                if data.get("battery_stop_threshold") is not None
                else None
            ),
            clamav_auto_update=bool(data.get("clamav_auto_update", True)),
            clamav_auto_scan=bool(data.get("clamav_auto_scan", True)),
            clamav_scan_interval_hours=int(data.get("clamav_scan_interval_hours", 24)),
            clamav_scan_target=str(data.get("clamav_scan_target", "downloads")),
            clamav_pause_on_battery=bool(data.get("clamav_pause_on_battery", True)),
            clamav_max_file_size_mb=int(data.get("clamav_max_file_size_mb", 25)),
            auto_adjust_rapl=bool(data.get("auto_adjust_rapl", True)),
        )


@dataclass
class AppSettings:
    user: UserSettings = field(default_factory=UserSettings)
    fan_curve: FanCurveConfig = field(default_factory=FanCurveConfig)
    battery_thresholds: BatteryThresholds = field(default_factory=lambda: BatteryThresholds(40, 80))

    def to_dict(self) -> Dict[str, object]:
        return {
            "user": self.user.to_dict(),
            "fan_curve": self.fan_curve.to_dict(),
            "battery_thresholds": self.battery_thresholds.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "AppSettings":
        user_data = data.get("user", {})
        fan_curve_data = data.get("fan_curve", {})
        battery_data = data.get("battery_thresholds", {})
        return cls(
            user=UserSettings.from_dict(user_data) if isinstance(user_data, dict) else UserSettings(),
            fan_curve=FanCurveConfig.from_dict(fan_curve_data) if isinstance(fan_curve_data, dict) else FanCurveConfig(),
            battery_thresholds=BatteryThresholds.from_dict(battery_data) if isinstance(battery_data, dict) else BatteryThresholds(40, 80),
        )
