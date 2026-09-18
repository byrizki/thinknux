"""Thermal sensors and temperature discovery interface."""

import glob
from pathlib import Path
import re
import shutil
import subprocess
from typing import Dict, Optional

from ...models.fan import SensorData
from .fan import PROC_FAN, parse_fan_proc


def get_cpu_temperature() -> Optional[int]:
    """Retrieve primary CPU temperature in degrees Celsius."""
    # 1. Try hwmon coretemp/k10temp/thinkpad
    for temp_input in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
        label_file = temp_input.replace("_input", "_label")
        label = ""
        if Path(label_file).is_file():
            try:
                label = Path(label_file).read_text().strip().lower()
            except Exception:
                pass

        # If label matches cpu/package or fallback if first sensor
        if not label or any(k in label for k in ["cpu", "package", "core", "tctl"]):
            try:
                milli = int(Path(temp_input).read_text().strip())
                temp = milli // 1000
                if 0 < temp < 125:
                    return temp
            except Exception:
                continue

    # 2. Try thermal zones
    for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        try:
            milli = int(Path(zone).read_text().strip())
            temp = milli // 1000
            if 0 < temp < 125:
                return temp
        except Exception:
            continue

    # 3. Try sensors command
    if shutil.which("sensors"):
        try:
            res = subprocess.run(
                ["sensors"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            for line in res.stdout.splitlines():
                if any(k in line.lower() for k in ["package id 0", "cpu", "tctl"]):
                    match = re.search(r"\+?([0-9]+(?:\.[0-9]+)?)°C", line)
                    if match:
                        return int(float(match.group(1)))
        except Exception:
            pass

    return None


def get_sensor_data() -> SensorData:
    """Retrieve full sensor metrics (temperatures and fan RPMs)."""
    temps: Dict[str, str] = {}
    fans: Dict[str, str] = {}

    # Fan metrics from proc, hwmon, and sensors
    from .fan import get_current_fan_level, get_current_fan_speed_rpm
    rpm, rpm_str = get_current_fan_speed_rpm()
    level = get_current_fan_level()
    fans["Fan Speed"] = rpm_str if rpm > 0 else "0 RPM (Idle)"
    fans["Fan Level"] = level

    proc_file = Path(PROC_FAN)
    if proc_file.is_file():
        try:
            content = proc_file.read_text(encoding="utf-8", errors="replace")
            parsed = parse_fan_proc(content)
            if "status" in parsed:
                fans["Fan Status"] = parsed["status"]
        except Exception:
            pass

    # Temperatures and RPM from sensors
    if shutil.which("sensors"):
        try:
            # Try thinkpad specific first, then generic
            cmd = ["sensors", "thinkpad-isa-0000"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
            if res.returncode != 0 or not res.stdout.strip():
                cmd = ["sensors"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)

            if res.returncode == 0:
                temp_re = re.compile(r"^(.+?):\s+\+?([0-9.]+°C)")
                rpm_re = re.compile(r"(\d+\s*RPM)")

                for line in res.stdout.splitlines():
                    t_match = temp_re.match(line)
                    if t_match:
                        label = t_match.group(1).strip()
                        val = t_match.group(2).strip()
                        temps[label] = val

                    if "RPM" in line and ":" in line:
                        label, rest = line.split(":", 1)
                        r_match = rpm_re.search(rest)
                        if r_match:
                            fans[label.strip()] = r_match.group(1).strip()
        except Exception as exc:
            temps["Info"] = f"Sensors check error: {exc}"
    else:
        temps["Info"] = "Install lm-sensors for detailed hardware temperatures"

    # If no temps found, probe thermal zones
    if not temps or (len(temps) == 1 and "Info" in temps):
        for idx, zone in enumerate(sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp"))):
            try:
                milli = int(Path(zone).read_text().strip())
                temps[f"Zone {idx}"] = f"{milli // 1000}°C"
            except Exception:
                continue

    return SensorData(temps=temps, fans=fans)
