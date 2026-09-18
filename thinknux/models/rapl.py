"""Intel RAPL / Running Average Power Limit (PL1 / PL2) data models."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class RaplLimits:
    supported: bool = False
    name: str = "package-0"
    pl1_watts: float = 0.0
    pl2_watts: float = 0.0
    pl1_time_window_sec: float = 0.0
    pl2_time_window_sec: float = 0.0
    enabled: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "supported": self.supported,
            "name": self.name,
            "pl1_watts": self.pl1_watts,
            "pl2_watts": self.pl2_watts,
            "pl1_time_window_sec": self.pl1_time_window_sec,
            "pl2_time_window_sec": self.pl2_time_window_sec,
            "enabled": self.enabled,
        }
