"""ThinkPad hardware LED indicator control interface.

Manages ThinkPad LEDs such as the glowing red lid dot (tpacpi::lid_logo_dot),
power button ring (tpacpi::power), and hardware indicators via /sys/class/leds/.
"""

from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple

from ...models.leds import LedDevice

LEDS_DIR = Path("/sys/class/leds")


def get_available_leds() -> List[LedDevice]:
    """Scan and list all detected ThinkPad ACPI LEDs."""
    devices: List[LedDevice] = []
    if not LEDS_DIR.is_dir():
        return devices

    for p in sorted(LEDS_DIR.iterdir()):
        name = p.name
        if not (name.startswith("tpacpi::") or name.startswith("platform::")):
            continue

        b_file = p / "brightness"
        max_file = p / "max_brightness"
        trig_file = p / "trigger"

        if not b_file.is_file():
            continue

        try:
            brightness = int(b_file.read_text(encoding="utf-8").strip())
        except Exception:
            brightness = 0

        try:
            max_b = int(max_file.read_text(encoding="utf-8").strip()) if max_file.is_file() else 255
        except Exception:
            max_b = 255

        cur_trig = "none"
        avail_trigs: List[str] = []
        if trig_file.is_file():
            try:
                raw = trig_file.read_text(encoding="utf-8").strip()
                for token in raw.split():
                    if token.startswith("[") and token.endswith("]"):
                        cur_trig = token[1:-1]
                        avail_trigs.append(cur_trig)
                    else:
                        avail_trigs.append(token)
            except Exception:
                pass

        devices.append(
            LedDevice(
                name=name,
                sysfs_path=str(p),
                brightness=brightness,
                max_brightness=max_b,
                current_trigger=cur_trig,
                available_triggers=avail_trigs,
            )
        )
    return devices


def _write_led_file(led_name: str, filename: str, value: str) -> Tuple[bool, Optional[str]]:
    """Write a value to an LED attribute file with pkexec fallback."""
    target = LEDS_DIR / led_name / filename
    if not target.is_file():
        return False, f"LED '{led_name}' attribute '{filename}' not found"

    # 1. Direct write
    try:
        target.write_text(value, encoding="utf-8")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # 2. Privileged write
    cmd = ["pkexec", "sh", "-c", f"echo '{value}' > '{target}'"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Permission denied writing LED"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"


def set_led_brightness(led_name: str, brightness: int) -> Tuple[bool, Optional[str]]:
    """Set the brightness level of a ThinkPad LED (0 to max_brightness)."""
    # Reset trigger to none first so manual brightness applies
    _write_led_file(led_name, "trigger", "none")
    return _write_led_file(led_name, "brightness", str(max(0, brightness)))


def set_led_trigger(led_name: str, trigger: str) -> Tuple[bool, Optional[str]]:
    """Assign a hardware kernel trigger (e.g. none, disk-activity, cpu) to an LED."""
    return _write_led_file(led_name, "trigger", trigger)


def set_lid_logo_dot_mode(mode: str) -> Tuple[bool, Optional[str]]:
    """Convenience helper for the outer lid glowing red dot.
    
    Modes:
      - 'off': turns off LED
      - 'solid': turns on full brightness
      - 'disk': pulses on disk read/write
      - 'cpu': pulses with CPU activity
    """
    led = "tpacpi::lid_logo_dot"
    if mode == "off":
        return set_led_brightness(led, 0)
    elif mode == "solid":
        return set_led_brightness(led, 255)
    elif mode == "disk":
        return set_led_trigger(led, "disk-activity")
    elif mode == "cpu":
        return set_led_trigger(led, "cpu")
    return False, f"Unknown mode '{mode}'"
