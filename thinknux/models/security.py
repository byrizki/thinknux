"""Security and antivirus data models."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ThreatInfo:
    file_path: str
    threat_name: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "file_path": self.file_path,
            "threat_name": self.threat_name,
        }


@dataclass
class SecurityStatus:
    clamav_installed: bool
    clamav_running: bool
    database_version: str
    last_update: str
    definitions_count: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "clamav_installed": self.clamav_installed,
            "clamav_running": self.clamav_running,
            "database_version": self.database_version,
            "last_update": self.last_update,
            "definitions_count": self.definitions_count,
        }


@dataclass
class ScanResult:
    success: bool
    scanned_files: int
    infected_files: int
    scan_time: str
    threats: List[ThreatInfo] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "success": self.success,
            "scanned_files": self.scanned_files,
            "infected_files": self.infected_files,
            "scan_time": self.scan_time,
            "threats": [t.to_dict() for t in self.threats],
            "logs": self.logs,
            "error": self.error,
        }


@dataclass
class InstallResponse:
    success: bool
    message: str
    logs: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "success": self.success,
            "message": self.message,
            "logs": self.logs,
            "error": self.error,
        }
