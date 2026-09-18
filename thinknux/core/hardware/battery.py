"""ThinkPad Battery management interface.

Reads battery metrics from sysfs for BAT0/BAT1, detects dual batteries,
tracks health degradation and charge cycles, and controls charging thresholds
with firmware-safe ordering.
"""

from pathlib import Path
import subprocess
from typing import List, Optional, Tuple

from ...models.battery import BatteryInfo, BatteryThresholds

BAT0_PATH = "/sys/class/power_supply/BAT0"
BAT1_PATH = "/sys/class/power_supply/BAT1"

THRESHOLD_ATTRS = [
    ("charge_control_start_threshold", "charge_control_end_threshold"),
    ("charge_start_threshold", "charge_stop_threshold"),
]


def threshold_paths(bat_path: str = BAT0_PATH) -> Optional[Tuple[str, str]]:
    """Return the (start_path, stop_path) pair exposed by the machine, or None."""
    for start_attr, stop_attr in THRESHOLD_ATTRS:
        start_p = Path(bat_path) / start_attr
        stop_p = Path(bat_path) / stop_attr
        if start_p.is_file() and stop_p.is_file():
            return str(start_p), str(stop_p)
    return None


def read_battery_info(bat_path: str, index: int) -> Optional[BatteryInfo]:
    """Read full status and health metrics from a specific battery sysfs directory."""
    path = Path(bat_path)
    if not path.is_dir():
        return None

    def read_str(filename: str, default: str = "Unknown") -> str:
        f = path / filename
        if f.is_file():
            try:
                return f.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                pass
        return default

    def read_int(filename: str, default: int = 0) -> int:
        val = read_str(filename, "")
        try:
            return int(val)
        except ValueError:
            return default

    def read_micro(filename: str) -> float:
        # Converts micro-units (uV, uA, uWh) to standard units (V, A, Wh)
        val = read_int(filename, 0)
        return float(val) / 1_000_000.0

    capacity = read_int("capacity", 0)
    energy_now = read_micro("energy_now")
    energy_full = read_micro("energy_full")
    energy_design = read_micro("energy_full_design")

    # Fallback to charge_* if energy_* is absent (some kernels use charge_now)
    if energy_now == 0.0 and (path / "charge_now").is_file():
        energy_now = read_micro("charge_now")
        energy_full = read_micro("charge_full")
        energy_design = read_micro("charge_full_design")

    health = 100
    if energy_design > 0.0:
        health = min(100, max(0, int((energy_full / energy_design) * 100.0)))

    voltage = read_micro("voltage_now")
    current = read_micro("current_now")
    power = read_micro("power_now")
    if power == 0.0 and voltage > 0.0 and current > 0.0:
        power = voltage * current

    cycles = read_int("cycle_count", 0)

    # Read current charge behaviour mode (e.g. auto, inhibit-charge, force-discharge)
    charge_behaviour = "auto"
    cb_file = path / "charge_behaviour"
    if cb_file.is_file():
        try:
            for token in cb_file.read_text(encoding="utf-8").split():
                if token.startswith("[") and token.endswith("]"):
                    charge_behaviour = token[1:-1]
                    break
        except Exception:
            pass

    return BatteryInfo(
        name=f"BAT{index}",
        status=read_str("status", "Unknown"),
        capacity=capacity,
        health=health,
        cycles=cycles,
        voltage=voltage,
        current=current,
        power=power,
        energy_now=energy_now,
        energy_full=energy_full,
        energy_design=energy_design,
        technology=read_str("technology", "Unknown"),
        manufacturer=read_str("manufacturer", "Unknown"),
        charge_behaviour=charge_behaviour,
    )


def get_battery_info() -> List[BatteryInfo]:
    """Scan and return metrics for all detected batteries (BAT0, BAT1)."""
    batteries: List[BatteryInfo] = []
    for idx, path in enumerate([BAT0_PATH, BAT1_PATH]):
        info = read_battery_info(path, idx)
        if info is not None:
            batteries.append(info)
    return batteries


def get_battery_thresholds() -> BatteryThresholds:
    """Read current start and stop charge thresholds."""
    pair = threshold_paths(BAT0_PATH)
    if pair is None:
        return BatteryThresholds(start=0, stop=100)

    start_path, stop_path = pair
    start_val = 0
    stop_val = 100

    try:
        start_val = int(Path(start_path).read_text(encoding="utf-8").strip())
    except Exception:
        pass

    try:
        stop_val = int(Path(stop_path).read_text(encoding="utf-8").strip())
    except Exception:
        pass

    return BatteryThresholds(start=start_val, stop=stop_val)


def write_start_first(current_start: int, new_stop: int) -> bool:
    """Determine whether new start threshold must be written before new stop threshold.
    
    Firmware rejects intermediate states where start >= stop.
    """
    return new_stop <= current_start


def set_battery_thresholds(start: int, stop: int) -> Tuple[bool, Optional[str]]:
    """Configure start and stop charge limits safely."""
    if start >= stop:
        return False, "Start threshold must be less than stop threshold"

    if not (0 <= start <= 100) or not (0 <= stop <= 100):
        return False, "Thresholds must be between 0 and 100"

    pair = threshold_paths(BAT0_PATH)
    if pair is None:
        return False, "This machine exposes no battery charge threshold controls"

    start_path, stop_path = pair
    current = get_battery_thresholds()

    if write_start_first(current.start, stop):
        first_path, first_val = start_path, str(start)
        second_path, second_val = stop_path, str(stop)
    else:
        first_path, first_val = stop_path, str(stop)
        second_path, second_val = start_path, str(start)

    # 1. Try direct writes
    try:
        Path(first_path).write_text(first_val, encoding="utf-8")
        Path(second_path).write_text(second_val, encoding="utf-8")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # 2. Fallback to privileged write via pkexec
    script = (
        f"#!/bin/bash\n"
        f"set -e\n"
        f"echo '{first_val}' > '{first_path}'\n"
        f"echo '{second_val}' > '{second_path}'\n"
        f"exit 0\n"
    )

    try:
        res = subprocess.run(
            ["pkexec", "bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Permission denied or write failed"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"


def get_charge_behaviour(bat_path: str = BAT0_PATH) -> str:
    """Read active charge behaviour mode (auto, inhibit-charge, force-discharge)."""
    cb_file = Path(bat_path) / "charge_behaviour"
    if cb_file.is_file():
        try:
            for token in cb_file.read_text(encoding="utf-8").split():
                if token.startswith("[") and token.endswith("]"):
                    return token[1:-1]
        except Exception:
            pass
    return "auto"


def set_charge_behaviour(mode: str, bat_path: str = BAT0_PATH) -> Tuple[bool, Optional[str]]:
    """Set battery charge behaviour (auto, inhibit-charge, force-discharge)."""
    valid_modes = ["auto", "inhibit-charge", "force-discharge"]
    if mode not in valid_modes:
        return False, f"Invalid charge behaviour '{mode}'. Allowed: {', '.join(valid_modes)}"

    target = Path(bat_path) / "charge_behaviour"
    if not target.is_file():
        return False, "charge_behaviour interface is not supported on this battery"

    # 1. Direct write attempt
    try:
        target.write_text(mode, encoding="utf-8")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # 2. Privileged write fallback
    cmd = ["pkexec", "sh", "-c", f"echo '{mode}' > '{target}'"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Permission denied updating charge behaviour"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"

