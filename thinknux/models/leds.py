"""ThinkPad LED indicator device data models."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class LedDevice:
    name: str
    sysfs_path: str
    brightness: int = 0
    max_brightness: int = 255
    current_trigger: str = "none"
    available_triggers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "sysfs_path": self.sysfs_path,
            "brightness": self.brightness,
            "max_brightness": self.max_brightness,
            "current_trigger": self.current_trigger,
            "available_triggers": self.available_triggers,
        }
