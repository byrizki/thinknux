"""ThinkPad ACPI fan control interface.

Handles reading fan status, speed, RPM, capability validation, and commanding
fan levels via direct write or privileged helper with firmware watchdog support.
"""

from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple

from ...models.fan import FanCapability, FanReadiness

PROC_FAN = "/proc/acpi/ibm/fan"
MODPROBE_CONF_PATH = "/etc/modprobe.d/thinkpad_acpi.conf"
FAN_WATCHDOG_SECS = 30

VALID_FAN_SPEEDS = [
    "auto",
    "full-speed",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
]

HELPER_CANDIDATES = [
    "/usr/lib/thinknux/thinknux-fan-control",
    "/usr/libexec/thinknux/thinknux-fan-control",
    "/usr/local/bin/thinknux-fan-control",
    "/usr/lib/thinkutils/thinkutils-fan-control",
    "/usr/libexec/thinkutils/thinkutils-fan-control",
    "/usr/local/bin/thinkutils-fan-control",
]

HELPER_SELF_INSTALL_PATH = "/usr/local/bin/thinknux-fan-control"
POLKIT_RULE_PATH = "/etc/polkit-1/rules.d/50-thinknux.rules"
POLKIT_RULE_PACKAGED_PATH = "/usr/share/polkit-1/rules.d/50-thinknux.rules"


def helper_path() -> Optional[str]:
    """Return the first existing privileged fan helper binary path."""
    for candidate in HELPER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def helper_is_packaged() -> bool:
    """True if helper is installed in system package locations."""
    for candidate in HELPER_CANDIDATES[:2]:
        if Path(candidate).is_file():
            return True
    return False


def is_valid_speed(speed: str) -> bool:
    """Validate fan speed against exact allowed whitelist."""
    return speed in VALID_FAN_SPEEDS


def parse_fan_proc(content: str) -> Dict[str, str]:
    """Parse /proc/acpi/ibm/fan key-value format."""
    info: Dict[str, str] = {}
    commands: List[str] = []
    for line in content.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key == "commands":
                commands.append(val)
            elif key == "speed":
                info["speed"] = val
                info["Fan1"] = f"{val} RPM"
            else:
                info[key] = val
    if commands:
        info["commands"] = ", ".join(commands)
    return info


def fan_control_is_enabled(content: str) -> bool:
    """Check if the thinkpad_acpi module was loaded with fan_control=1."""
    return any(line.strip().startswith("commands:") for line in content.splitlines())


def get_fan_status() -> Tuple[bool, Dict[str, str], Optional[str]]:
    """Read current fan metrics from /proc/acpi/ibm/fan.
    
    Returns (success, data_dict, error_message).
    """
    proc_path = Path(PROC_FAN)
    if not proc_path.exists():
        return False, {}, f"Fan interface {PROC_FAN} does not exist"
    try:
        content = proc_path.read_text(encoding="utf-8", errors="replace")
        return True, parse_fan_proc(content), None
    except Exception as exc:
        return False, {}, str(exc)


def get_current_fan_speed_rpm() -> Tuple[int, str]:
    """Read live fan speed RPM from /proc/acpi/ibm/fan, sysfs hwmon, or sensors."""
    # 1. /proc/acpi/ibm/fan
    proc_path = Path(PROC_FAN)
    if proc_path.is_file():
        try:
            content = proc_path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_fan_proc(content)
            if "speed" in parsed:
                rpm = int(parsed["speed"])
                return rpm, f"{rpm} RPM"
        except Exception:
            pass

    # 2. Sysfs hwmon fan input
    import glob
    for p_str in (
        glob.glob("/sys/devices/platform/thinkpad_hwmon/hwmon/hwmon*/fan*_input")
        + glob.glob("/sys/class/hwmon/hwmon*/fan*_input")
    ):
        p = Path(p_str)
        if p.is_file():
            try:
                rpm = int(p.read_text().strip())
                return rpm, f"{rpm} RPM"
            except Exception:
                pass

    # 3. sensors command
    import shutil
    if shutil.which("sensors"):
        try:
            res = subprocess.run(["sensors"], capture_output=True, text=True, timeout=2, check=False)
            import re
            for line in res.stdout.splitlines():
                if "rpm" in line.lower() and ":" in line:
                    match = re.search(r"(\d+)\s*RPM", line, re.IGNORECASE)
                    if match:
                        rpm = int(match.group(1))
                        return rpm, f"{rpm} RPM"
        except Exception:
            pass

    return 0, "0 RPM"


def get_current_fan_level() -> str:
    """Read current active fan level (e.g. 'auto', '0'-'7', 'full-speed')."""
    proc_path = Path(PROC_FAN)
    if proc_path.is_file():
        try:
            content = proc_path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_fan_proc(content)
            return parsed.get("level", "auto")
        except Exception:
            pass
    return "auto"


def get_fan_capability() -> FanCapability:
    """Probe system for ThinkPad fan readiness and module options."""
    modprobe_conf = Path(MODPROBE_CONF_PATH)
    modprobe_conf_present = False
    if modprobe_conf.exists():
        try:
            content = modprobe_conf.read_text(encoding="utf-8", errors="replace")
            modprobe_conf_present = "fan_control=1" in content
        except Exception:
            modprobe_conf_present = False

    proc_path = Path(PROC_FAN)
    if not proc_path.exists():
        return FanCapability(
            readiness=FanReadiness.NO_THINKPAD_FAN,
            modprobe_conf_present=modprobe_conf_present,
            message="No ThinkPad fan interface found. Load the thinkpad_acpi module, or this model may not be supported.",
        )

    try:
        content = proc_path.read_text(encoding="utf-8", errors="replace")
        if fan_control_is_enabled(content):
            return FanCapability(
                readiness=FanReadiness.READY,
                modprobe_conf_present=modprobe_conf_present,
                message="Fan control is available.",
            )
        elif modprobe_conf_present:
            return FanCapability(
                readiness=FanReadiness.NEEDS_MODULE_PARAM,
                modprobe_conf_present=True,
                message="Fan control is configured but not active yet. Reboot or reload thinkpad_acpi module.",
            )
        else:
            return FanCapability(
                readiness=FanReadiness.NEEDS_MODULE_PARAM,
                modprobe_conf_present=False,
                message="The thinkpad_acpi module was loaded without fan_control=1. Kernel module setting required.",
            )
    except Exception as exc:
        return FanCapability(
            readiness=FanReadiness.NO_THINKPAD_FAN,
            modprobe_conf_present=modprobe_conf_present,
            message=f"Failed to read fan interface: {exc}",
        )


def write_fan_command(command: str) -> Tuple[bool, Optional[str]]:
    """Execute a fan command (e.g. 'level auto', 'level 3', 'watchdog 30').
    
    Tries direct write first, falls back to privileged helper via pkexec.
    """
    proc_path = Path(PROC_FAN)
    if not proc_path.exists():
        return False, f"Fan control file {PROC_FAN} does not exist"

    # 1. Try direct write if permissions permit
    try:
        with open(proc_path, "w", encoding="utf-8") as f:
            f.write(f"{command}\n")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # 2. Try installed helper
    helper = helper_path()
    if helper:
        try:
            res = subprocess.run(
                ["pkexec", helper, command],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                return True, None
            return False, res.stderr.strip() or f"Helper exited with code {res.returncode}"
        except Exception as exc:
            return False, f"Failed to execute helper: {exc}"

    # 3. Fallback: run pkexec with exact-whitelist command
    try:
        bash_cmd = f'echo "{command}" > {PROC_FAN}'
        res = subprocess.run(
            ["pkexec", "bash", "-c", bash_cmd],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Privileged write failed"
    except Exception as exc:
        return False, str(exc)


def set_fan_speed(speed: str) -> Tuple[bool, Optional[str]]:
    """Set fan speed (validates speed against allowed values)."""
    if not is_valid_speed(speed):
        return False, f"Invalid fan speed: {speed}. Allowed: {', '.join(VALID_FAN_SPEEDS)}"
    return write_fan_command(f"level {speed}")


def arm_fan_watchdog() -> Tuple[bool, Optional[str]]:
    """Arm the firmware watchdog timer (reverts to auto if process hangs)."""
    return write_fan_command(f"watchdog {FAN_WATCHDOG_SECS}")


def restore_fan_to_auto_blocking() -> bool:
    """Restores the fan to automatic control immediately (blocking).
    
    Must be called during application shutdown / crash handler.
    """
    success, _ = write_fan_command("level auto")
    return success
