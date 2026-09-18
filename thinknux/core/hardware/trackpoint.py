"""ThinkPad TrackPoint hardware interface.

Interacts with the Linux serio psmouse driver at
/sys/devices/platform/i8042/serio1/serio2/ to manage TrackPoint sensitivity,
press-to-select (tap-to-click), resolution, and reporting rate.
"""

from pathlib import Path
import subprocess
from typing import Optional, Tuple

from ...models.trackpoint import TrackpointConfig

DEFAULT_TRACKPOINT_PATH = Path("/sys/devices/platform/i8042/serio1/serio2")


def find_trackpoint_dir() -> Optional[Path]:
    """Locate the sysfs directory for the hardware TrackPoint."""
    if DEFAULT_TRACKPOINT_PATH.is_dir() and (DEFAULT_TRACKPOINT_PATH / "sensitivity").is_file():
        return DEFAULT_TRACKPOINT_PATH

    # Search alternative serio paths under i8042
    base = Path("/sys/devices/platform/i8042")
    if base.is_dir():
        for p in base.glob("serio*/serio*"):
            if (p / "sensitivity").is_file():
                return p
    return None


def get_trackpoint_config() -> TrackpointConfig:
    """Read active TrackPoint parameters from hardware sysfs."""
    tp_dir = find_trackpoint_dir()
    if not tp_dir:
        return TrackpointConfig(supported=False)

    def read_int(fname: str, default: int) -> int:
        f = tp_dir / fname
        if f.is_file():
            try:
                return int(f.read_text(encoding="utf-8").strip())
            except Exception:
                pass
        return default

    sensitivity = read_int("sensitivity", 128)
    press_to_select = read_int("press_to_select", 0) == 1
    rate = read_int("rate", 100)
    resolution = read_int("resolution", 200)

    return TrackpointConfig(
        supported=True,
        sensitivity=sensitivity,
        press_to_select=press_to_select,
        rate=rate,
        resolution=resolution,
    )


def _write_attribute(attr_name: str, value_str: str) -> Tuple[bool, Optional[str]]:
    """Write an attribute to the TrackPoint sysfs directory with pkexec fallback."""
    tp_dir = find_trackpoint_dir()
    if not tp_dir:
        return False, "TrackPoint device not found"

    target = tp_dir / attr_name
    if not target.is_file():
        return False, f"TrackPoint attribute '{attr_name}' not available"

    # 1. Direct write attempt
    try:
        target.write_text(value_str, encoding="utf-8")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # 2. Privileged write via pkexec
    cmd = ["pkexec", "sh", "-c", f"echo '{value_str}' > '{target}'"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Permission denied on TrackPoint write"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"


def set_trackpoint_sensitivity(sensitivity: int) -> Tuple[bool, Optional[str]]:
    """Set TrackPoint cursor sensitivity (0-255, standard default is 128)."""
    bounded = max(0, min(255, sensitivity))
    return _write_attribute("sensitivity", str(bounded))


def set_trackpoint_press_to_select(enabled: bool) -> Tuple[bool, Optional[str]]:
    """Enable or disable TrackPoint press-to-select (tap-to-click)."""
    return _write_attribute("press_to_select", "1" if enabled else "0")


def reset_trackpoint_defaults() -> Tuple[bool, Optional[str]]:
    """Reset TrackPoint configuration to factory standards (sensitivity: 128, tap: off)."""
    ok1, err1 = set_trackpoint_sensitivity(128)
    if not ok1:
        return False, err1
    ok2, err2 = set_trackpoint_press_to_select(False)
    if not ok2:
        return False, err2
    return True, None
