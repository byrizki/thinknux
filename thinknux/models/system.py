"""System specifications data model."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class SystemInfo:
    hostname: str
    os: str
    kernel: str
    model: str
    cpu: str
    memory: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "hostname": self.hostname,
            "os": self.os,
            "kernel": self.kernel,
            "model": self.model,
            "cpu": self.cpu,
            "memory": self.memory,
        }
