"""ThinkPad TrackPoint hardware configuration data models."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TrackpointConfig:
    supported: bool = False
    sensitivity: int = 128
    press_to_select: bool = False
    rate: int = 100
    resolution: int = 200

    def to_dict(self) -> Dict[str, object]:
        return {
            "supported": self.supported,
            "sensitivity": self.sensitivity,
            "press_to_select": self.press_to_select,
            "rate": self.rate,
            "resolution": self.resolution,
        }
