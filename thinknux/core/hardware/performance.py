"""CPU performance, governor scaling, power profiles, and turbo boost control."""

import glob
from pathlib import Path
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from ...models.performance import CpuInfo, PowerProfile, TurboBoostStatus

CPU0_FREQ = "/sys/devices/system/cpu/cpu0/cpufreq"
CPU_GOV_GLOB = "/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor"
INTEL_TURBO = "/sys/devices/system/cpu/intel_pstate/no_turbo"
GENERIC_BOOST = "/sys/devices/system/cpu/cpufreq/boost"


def read_sysfs_str(path_str: str, default: str = "") -> str:
    p = Path(path_str)
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            pass
    return default


def read_sysfs_int(path_str: str, default: int = 0) -> int:
    val = read_sysfs_str(path_str, "")
    try:
        return int(val)
    except ValueError:
        return default


def read_available_governors() -> List[str]:
    avail = read_sysfs_str(f"{CPU0_FREQ}/scaling_available_governors")
    return avail.split() if avail else []


def validate_governor(governor: str) -> Tuple[bool, Optional[str]]:
    """Validate governor name against safety rules and available list."""
    if not governor or len(governor) > 32:
        return False, "Invalid governor name length."
    if not re.match(r"^[a-z_]+$", governor):
        return False, "Governor name contains invalid characters."

    available = read_available_governors()
    if available and governor not in available:
        return False, f"Governor '{governor}' is not available. Options: {', '.join(available)}"
    return True, None


def get_cpu_info() -> CpuInfo:
    """Retrieve frequency scaling metrics and governors for CPU0."""
    governor = read_sysfs_str(f"{CPU0_FREQ}/scaling_governor", "unknown")
    min_freq = read_sysfs_int(f"{CPU0_FREQ}/scaling_min_freq", 0) // 1000
    max_freq = read_sysfs_int(f"{CPU0_FREQ}/scaling_max_freq", 0) // 1000
    cur_freq = read_sysfs_int(f"{CPU0_FREQ}/scaling_cur_freq", 0) // 1000
    available = read_available_governors()

    return CpuInfo(
        governor=governor,
        min_freq=min_freq,
        max_freq=max_freq,
        current_freq=cur_freq,
        available_governors=available,
    )


def set_cpu_governor(governor: str) -> Tuple[bool, Optional[str]]:
    """Apply scaling governor to all active online CPU cores."""
    valid, err = validate_governor(governor)
    if not valid:
        return False, err

    gov_files = glob.glob(CPU_GOV_GLOB)
    if not gov_files:
        return False, "No CPU scaling governor interfaces found."

    # Try direct write first if permissions are already set
    all_written = True
    for f in gov_files:
        try:
            Path(f).write_text(governor, encoding="utf-8")
        except Exception:
            all_written = False
            break

    if all_written:
        return True, None

    # Fallback to pkexec batch script
    script = (
        "#!/bin/bash\n"
        "set -u\n"
        "applied=0\n"
        f"for f in {CPU_GOV_GLOB}; do\n"
        '  [ -e "$f" ] || continue\n'
        f"  if echo '{governor}' > \"$f\" 2>/dev/null; then\n"
        "    applied=$((applied + 1))\n"
        "  fi\n"
        "done\n"
        'if [ "$applied" -eq 0 ]; then\n'
        '  echo "No CPU accepted the governor" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
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
        return False, res.stderr.strip() or "Failed to set CPU governor"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"


SYSFS_PLATFORM_PROFILE = "/sys/firmware/acpi/platform_profile"
SYSFS_PLATFORM_PROFILE_CHOICES = "/sys/firmware/acpi/platform_profile_choices"

SYSFS_TO_PROFILE_MAP = {
    "low-power": "power-saver",
    "balanced": "balanced",
    "performance": "performance",
}
PROFILE_TO_SYSFS_MAP = {
    "power-saver": "low-power",
    "balanced": "balanced",
    "performance": "performance",
}


def get_power_profile() -> PowerProfile:
    """Read active power profile and available profiles."""
    # 1. Fast-path: check direct ACPI platform profile in sysfs (<1ms)
    prof_path = Path(SYSFS_PLATFORM_PROFILE)
    choices_path = Path(SYSFS_PLATFORM_PROFILE_CHOICES)
    if prof_path.is_file():
        try:
            raw_cur = prof_path.read_text(encoding="utf-8").strip()
            current = SYSFS_TO_PROFILE_MAP.get(raw_cur, raw_cur)
            available = []
            if choices_path.is_file():
                raw_choices = choices_path.read_text(encoding="utf-8").split()
                for c in raw_choices:
                    mapped = SYSFS_TO_PROFILE_MAP.get(c, c)
                    if mapped in ["power-saver", "balanced", "performance"] and mapped not in available:
                        available.append(mapped)
            if not available:
                available = ["power-saver", "balanced", "performance"]
            return PowerProfile(current=current, available=available)
        except Exception:
            pass

    # 2. Try powerprofilesctl
    if shutil.which("powerprofilesctl"):
        try:
            curr_res = subprocess.run(
                ["powerprofilesctl", "get"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if curr_res.returncode == 0:
                current = curr_res.stdout.strip()
                list_res = subprocess.run(
                    ["powerprofilesctl", "list"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                available = []
                for line in list_res.stdout.splitlines():
                    cleaned = line.strip().lstrip("* ").split(":")[0].strip()
                    if cleaned in ["power-saver", "balanced", "performance"]:
                        if cleaned not in available:
                            available.append(cleaned)
                if not available:
                    available = ["power-saver", "balanced", "performance"]
                return PowerProfile(current=current, available=available)
        except Exception:
            pass

    # 3. Fallback to TLP
    if shutil.which("tlp-stat"):
        try:
            stat_res = subprocess.run(
                ["tlp-stat", "-s"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if stat_res.returncode == 0:
                curr = "performance" if "AC" in stat_res.stdout else "power-saver"
                return PowerProfile(current=curr, available=["power-saver", "performance"])
        except Exception:
            pass

    return PowerProfile(current="unknown", available=[])


PROFILE_RAPL_MAPPING: Dict[str, Tuple[float, float]] = {
    "power-saver": (15.0, 20.0),
    "balanced": (28.0, 35.0),
    "performance": (45.0, 54.0),
}


def apply_rapl_for_profile(profile: str) -> Tuple[bool, Optional[str]]:
    """Apply default TDP PL1/PL2 power caps corresponding to a power profile."""
    if profile not in PROFILE_RAPL_MAPPING:
        return False, f"No RAPL mapping for profile: {profile}"
    try:
        from .rapl import is_rapl_supported, set_rapl_limits
        if not is_rapl_supported():
            return False, "RAPL not supported"
        pl1, pl2 = PROFILE_RAPL_MAPPING[profile]
        return set_rapl_limits(pl1, pl2)
    except Exception as exc:
        return False, str(exc)


def set_power_profile(profile: str, auto_rapl: Optional[bool] = None) -> Tuple[bool, Optional[str]]:
    """Switch active power profile using direct sysfs, powerprofilesctl, or TLP."""
    success = False
    err_msg = None

    # 1. Try direct sysfs write if platform_profile is writable
    sysfs_target = PROFILE_TO_SYSFS_MAP.get(profile, profile)
    prof_path = Path(SYSFS_PLATFORM_PROFILE)
    if prof_path.is_file():
        try:
            prof_path.write_text(sysfs_target, encoding="utf-8")
            success = True
        except PermissionError:
            pass
        except Exception:
            pass

    if not success and shutil.which("powerprofilesctl"):
        try:
            res = subprocess.run(
                ["powerprofilesctl", "set", profile],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                success = True
            else:
                err_msg = res.stderr.strip() or "powerprofilesctl set failed"
        except Exception as exc:
            err_msg = str(exc)

    if not success and shutil.which("tlp"):
        tlp_mode = "BAT" if profile == "power-saver" else "AC"
        try:
            res = subprocess.run(
                ["pkexec", "tlp", tlp_mode],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                success = True
            else:
                err_msg = res.stderr.strip() or "tlp command failed"
        except Exception as exc:
            err_msg = str(exc)

    if not success and err_msg is None:
        return False, "No power management daemon found (install power-profiles-daemon or TLP)."

    if success:
        # Check auto_adjust_rapl setting
        if auto_rapl is None:
            try:
                from ..settings import get_settings_manager
                auto_rapl = get_settings_manager().settings.user.auto_adjust_rapl
            except Exception:
                auto_rapl = False

        if auto_rapl:
            apply_rapl_for_profile(profile)

        return True, None

    return False, err_msg


def get_turbo_boost_status() -> TurboBoostStatus:
    """Read CPU Turbo Boost / Boost state."""
    # Intel pstate
    if Path(INTEL_TURBO).is_file():
        val = read_sysfs_str(INTEL_TURBO)
        return TurboBoostStatus(supported=True, enabled=(val == "0"))

    # Generic AMD / acpi-cpufreq boost
    if Path(GENERIC_BOOST).is_file():
        val = read_sysfs_str(GENERIC_BOOST)
        return TurboBoostStatus(supported=True, enabled=(val == "1"))

    return TurboBoostStatus(supported=False, enabled=False)


def set_turbo_boost(enabled: bool) -> Tuple[bool, Optional[str]]:
    """Enable or disable CPU Turbo Boost."""
    intel_path = Path(INTEL_TURBO)
    generic_path = Path(GENERIC_BOOST)

    target_path = None
    target_val = ""

    if intel_path.is_file():
        target_path = intel_path
        target_val = "0" if enabled else "1"  # 0 means no_turbo is off (boost enabled)
    elif generic_path.is_file():
        target_path = generic_path
        target_val = "1" if enabled else "0"  # 1 means boost is on
    else:
        return False, "Turbo boost control is not supported on this machine."

    # Direct write
    try:
        target_path.write_text(target_val, encoding="utf-8")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # Privileged write
    script = f"#!/bin/bash\necho '{target_val}' > '{target_path}'\nexit 0\n"
    try:
        res = subprocess.run(
            ["pkexec", "bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Privileged write failed"
    except Exception as exc:
        return False, f"Failed to set turbo boost: {exc}"
