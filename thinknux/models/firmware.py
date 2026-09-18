"""ThinkPad BIOS / UEFI ThinkLMI firmware attributes data models."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FirmwareAttribute:
    name: str
    display_name: str
    current_value: str
    possible_values: List[str] = field(default_factory=list)
    attr_type: str = "enumeration"

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "current_value": self.current_value,
            "possible_values": self.possible_values,
            "attr_type": self.attr_type,
        }


@dataclass
class ThinkLmiStatus:
    supported: bool = False
    attributes: Dict[str, FirmwareAttribute] = field(default_factory=dict)
    has_admin_password: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "supported": self.supported,
            "attributes": {k: v.to_dict() for k, v in self.attributes.items()},
            "has_admin_password": self.has_admin_password,
        }
