"""Battery data models."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class BatteryInfo:
    name: str
    status: str
    capacity: int
    health: int
    cycles: int
    voltage: float
    current: float
    power: float
    energy_now: float
    energy_full: float
    energy_design: float
    technology: str
    manufacturer: str
    charge_behaviour: str = "auto"

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "capacity": self.capacity,
            "health": self.health,
            "cycles": self.cycles,
            "voltage": self.voltage,
            "current": self.current,
            "power": self.power,
            "energy_now": self.energy_now,
            "energy_full": self.energy_full,
            "energy_design": self.energy_design,
            "technology": self.technology,
            "manufacturer": self.manufacturer,
            "charge_behaviour": self.charge_behaviour,
        }


@dataclass
class BatteryThresholds:
    start: int = 0
    stop: int = 100

    def to_dict(self) -> Dict[str, int]:
        return {"start": self.start, "stop": self.stop}

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "BatteryThresholds":
        return cls(start=int(data.get("start", 0)), stop=int(data.get("stop", 100)))
