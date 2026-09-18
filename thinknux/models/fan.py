"""Fan and thermal sensor data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class FanReadiness(str, Enum):
    READY = "Ready"
    NEEDS_MODULE_PARAM = "NeedsModuleParam"
    NO_THINKPAD_FAN = "NoThinkpadFan"


@dataclass
class FanCapability:
    readiness: FanReadiness
    modprobe_conf_present: bool
    message: str


@dataclass
class SensorData:
    temps: Dict[str, str] = field(default_factory=dict)
    fans: Dict[str, str] = field(default_factory=dict)


@dataclass
class CurvePoint:
    temp: int
    level: int

    def to_dict(self) -> Dict[str, int]:
        return {"temp": self.temp, "level": self.level}

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "CurvePoint":
        return cls(temp=int(data["temp"]), level=int(data["level"]))


@dataclass
class FanCurveConfig:
    enabled: bool = False
    points: List[CurvePoint] = field(
        default_factory=lambda: [
            CurvePoint(temp=40, level=0),
            CurvePoint(temp=50, level=1),
            CurvePoint(temp=60, level=3),
            CurvePoint(temp=70, level=5),
            CurvePoint(temp=80, level=7),
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "points": [p.to_dict() for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "FanCurveConfig":
        points_raw = data.get("points", [])
        points = [CurvePoint.from_dict(p) for p in points_raw] if points_raw else [
            CurvePoint(temp=40, level=0),
            CurvePoint(temp=50, level=1),
            CurvePoint(temp=60, level=3),
            CurvePoint(temp=70, level=5),
            CurvePoint(temp=80, level=7),
        ]
        return cls(enabled=bool(data.get("enabled", False)), points=points)
