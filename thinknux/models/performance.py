"""CPU performance and power profile data models."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CpuInfo:
    governor: str
    min_freq: int
    max_freq: int
    current_freq: int
    available_governors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "governor": self.governor,
            "min_freq": self.min_freq,
            "max_freq": self.max_freq,
            "current_freq": self.current_freq,
            "available_governors": self.available_governors,
        }


@dataclass
class PowerProfile:
    current: str
    available: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "current": self.current,
            "available": self.available,
        }


@dataclass
class TurboBoostStatus:
    supported: bool
    enabled: bool

    def to_dict(self) -> Dict[str, bool]:
        return {
            "supported": self.supported,
            "enabled": self.enabled,
        }
