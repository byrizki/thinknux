"""Lenovo ThinkLMI BIOS / UEFI firmware configuration interface.

Interacts with the Linux kernel think-lmi driver at
/sys/class/firmware-attributes/thinklmi/attributes/ to query and configure
firmware attributes like FnCtrlKeySwap, FnKeyAsPrimary, AlwaysOnUSB, SleepState, etc.
"""

from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple

from ...models.firmware import FirmwareAttribute, ThinkLmiStatus

THINKLMI_BASE = Path("/sys/class/firmware-attributes/thinklmi")
THINKLMI_ATTRS = THINKLMI_BASE / "attributes"
THINKLMI_AUTH = THINKLMI_BASE / "authentication"

# High-priority ThinkPad hardware attributes
FEATURED_ATTRIBUTES = [
    "FnCtrlKeySwap",
    "FnKeyAsPrimary",
    "AlwaysOnUSB",
    "ChargeInBatteryMode",
    "CoolQuietOnLap",
    "SleepState",
    "KeyboardBeep",
]


def is_thinklmi_supported() -> bool:
    """Check if the thinklmi driver and attributes interface are available."""
    return THINKLMI_ATTRS.is_dir()


def has_bios_admin_password() -> bool:
    """Check if a BIOS supervisor/admin password is set."""
    is_enabled_file = THINKLMI_AUTH / "Admin" / "is_enabled"
    if is_enabled_file.is_file():
        try:
            val = is_enabled_file.read_text(encoding="utf-8").strip()
            return val == "1"
        except Exception:
            pass
    return False


def get_firmware_attribute(attr_name: str) -> Optional[FirmwareAttribute]:
    """Read a specific ThinkLMI attribute details and current value."""
    attr_dir = THINKLMI_ATTRS / attr_name
    if not attr_dir.is_dir():
        return None

    def read_file(fname: str, default: str = "") -> str:
        f = attr_dir / fname
        if f.is_file():
            try:
                return f.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                pass
        return default

    disp_name = read_file("display_name", attr_name)
    raw_possibles = read_file("possible_values", "")
    possible_values = [p.strip() for p in raw_possibles.split(";") if p.strip()]
    attr_type = read_file("type", "enumeration")
    current_val = read_file("current_value", "")

    return FirmwareAttribute(
        name=attr_name,
        display_name=disp_name,
        current_value=current_val,
        possible_values=possible_values,
        attr_type=attr_type,
    )


def get_firmware_status() -> ThinkLmiStatus:
    """Retrieve full status of supported and featured ThinkPad BIOS attributes."""
    if not is_thinklmi_supported():
        return ThinkLmiStatus(supported=False)

    attrs: Dict[str, FirmwareAttribute] = {}
    for name in FEATURED_ATTRIBUTES:
        attr = get_firmware_attribute(name)
        if attr:
            attrs[name] = attr

    return ThinkLmiStatus(
        supported=True,
        attributes=attrs,
        has_admin_password=has_bios_admin_password(),
    )


def set_firmware_attribute(attr_name: str, new_value: str) -> Tuple[bool, Optional[str]]:
    """Write a new value to a ThinkLMI attribute.
    
    Tries direct sysfs write first; falls back to pkexec if root elevation is required.
    """
    attr_dir = THINKLMI_ATTRS / attr_name
    target_file = attr_dir / "current_value"
    if not target_file.is_file():
        return False, f"Attribute '{attr_name}' not found on this system"

    # Validate against known possible values if file exists
    possibles_file = attr_dir / "possible_values"
    if possibles_file.is_file():
        try:
            possibles = [p.strip() for p in possibles_file.read_text(encoding="utf-8").split(";") if p.strip()]
            if possibles and new_value not in possibles:
                return False, f"Invalid value '{new_value}'. Allowed: {', '.join(possibles)}"
        except Exception:
            pass

    # 1. Direct write attempt
    try:
        target_file.write_text(new_value, encoding="utf-8")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # 2. Privileged write via pkexec
    cmd = ["pkexec", "sh", "-c", f"echo '{new_value}' > '{target_file}'"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Privileged write failed"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"
