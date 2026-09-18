"""System monitor metrics data models."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CoreStats:
    core_id: int
    usage_percent: float
    frequency: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "core_id": self.core_id,
            "usage_percent": self.usage_percent,
            "frequency": self.frequency,
        }


@dataclass
class LoadAverage:
    one_min: float
    five_min: float
    fifteen_min: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "one_min": self.one_min,
            "five_min": self.five_min,
            "fifteen_min": self.fifteen_min,
        }


@dataclass
class CpuStats:
    usage_percent: float
    cores: List[CoreStats] = field(default_factory=list)
    load_avg: LoadAverage = field(default_factory=lambda: LoadAverage(0.0, 0.0, 0.0))

    def to_dict(self) -> Dict[str, object]:
        return {
            "usage_percent": self.usage_percent,
            "cores": [c.to_dict() for c in self.cores],
            "load_avg": self.load_avg.to_dict(),
        }


@dataclass
class MemoryStats:
    total: int
    used: int
    available: int
    usage_percent: float
    swap_total: int
    swap_used: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "total": self.total,
            "used": self.used,
            "available": self.available,
            "usage_percent": self.usage_percent,
            "swap_total": self.swap_total,
            "swap_used": self.swap_used,
        }


@dataclass
class DiskStats:
    device: str
    mount_point: str
    total: int
    used: int
    available: int
    usage_percent: float
    filesystem: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "device": self.device,
            "mount_point": self.mount_point,
            "total": self.total,
            "used": self.used,
            "available": self.available,
            "usage_percent": self.usage_percent,
            "filesystem": self.filesystem,
        }


@dataclass
class NetworkStats:
    interface: str
    rx_bytes: int
    tx_bytes: int
    rx_packets: int
    tx_packets: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "interface": self.interface,
            "rx_bytes": self.rx_bytes,
            "tx_bytes": self.tx_bytes,
            "rx_packets": self.rx_packets,
            "tx_packets": self.tx_packets,
        }


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    status: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "pid": self.pid,
            "name": self.name,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "status": self.status,
        }


@dataclass
class SystemMonitor:
    cpu: CpuStats
    memory: MemoryStats
    disk: List[DiskStats] = field(default_factory=list)
    network: List[NetworkStats] = field(default_factory=list)
    processes: List[ProcessInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "cpu": self.cpu.to_dict(),
            "memory": self.memory.to_dict(),
            "disk": [d.to_dict() for d in self.disk],
            "network": [n.to_dict() for n in self.network],
            "processes": [p.to_dict() for p in self.processes],
        }
