"""System permissions checking and privilege elevation setup."""

import glob
import os
from pathlib import Path
import subprocess
from typing import List, Tuple

from .hardware.battery import threshold_paths
from .hardware.fan import (
    HELPER_CANDIDATES,
    HELPER_SELF_INSTALL_PATH,
    POLKIT_RULE_PATH,
    PROC_FAN,
    helper_is_packaged,
    helper_path,
)

BASE_REQUIRED_FILES = [
    "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
    "/sys/devices/system/cpu/intel_pstate/no_turbo",
    "/sys/devices/system/cpu/cpufreq/boost",
]

HELPER_SCRIPT_CONTENT = """#!/bin/bash
set -e
FAN="/proc/acpi/ibm/fan"
# Exact-match whitelist. "watchdog 30" is permitted because the firmware
# watchdog can only ever return the fan to automatic control -- it is the
# recovery path if this app dies while holding a manual level.
case "$1" in
    "level auto"|"level full-speed"|"level 0"|"level 1"|"level 2"|"level 3"|"level 4"|"level 5"|"level 6"|"level 7"|"watchdog 30")
        echo "$1" > "$FAN"
        ;;
    *)
        echo "Invalid command" >&2
        exit 1
        ;;
esac
"""


def polkit_rule() -> str:
    """Generate Polkit JavaScript rule granting passwordless execution to helper."""
    allowed = " ||\n".join(
        f'            program == "{cand}"' for cand in HELPER_CANDIDATES
    )
    return f"""/* ThinkNux: passwordless fan control via the dedicated helper only. */
polkit.addRule(function(action, subject) {{
    if (action.id == "org.freedesktop.policykit.exec") {{
        var program = action.lookup("program");
        if (
{allowed}
        ) {{
            if (subject.local && subject.active &&
                (subject.isInGroup("wheel") || subject.isInGroup("sudo"))) {{
                return polkit.Result.YES;
            }}
        }}
    }}
}});
"""


def required_files() -> List[str]:
    """Resolve all sysfs and control paths this machine exposes."""
    files: List[str] = [
        "/sys/devices/system/cpu/intel_pstate/no_turbo",
        "/sys/devices/system/cpu/cpufreq/boost",
    ]

    # Include all CPU cores governor paths
    for gov in sorted(glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")):
        files.append(gov)

    b_pair = threshold_paths()
    if b_pair:
        files.extend(b_pair)

    # Battery charge behaviour (inhibit-charge, force-discharge)
    for cb in glob.glob("/sys/class/power_supply/BAT*/charge_behaviour"):
        files.append(cb)

    # Trackpoint attributes
    for tp_attr in ["sensitivity", "press_to_select", "rate", "resolution"]:
        for tp_path in glob.glob(f"/sys/devices/platform/i8042/serio*/serio*/{tp_attr}"):
            files.append(tp_path)

    # Intel RAPL power limits
    for rapl in [
        "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw",
        "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_1_power_limit_uw",
    ]:
        if Path(rapl).exists():
            files.append(rapl)

    # ThinkPad LEDs (lid logo dot, power, etc.)
    for led_attr in glob.glob("/sys/class/leds/tpacpi::*/brightness"):
        files.append(led_attr)
    for led_trig in glob.glob("/sys/class/leds/tpacpi::*/trigger"):
        files.append(led_trig)

    for pwm in glob.glob("/sys/devices/platform/thinkpad_hwmon/hwmon/hwmon*/pwm1"):
        if Path(pwm).exists():
            files.append(pwm)

    return files


def check_permissions_status() -> Tuple[bool, List[str]]:
    """Check write accessibility of all required hardware surfaces.
    
    Returns (has_permissions, missing_files).
    """
    missing: List[str] = []

    for f_path in required_files():
        p = Path(f_path)
        if p.exists() and not os.access(f_path, os.W_OK):
            missing.append(f_path)

    # Fan check
    if helper_path() is None:
        fan_p = Path(PROC_FAN)
        if fan_p.exists() and not os.access(PROC_FAN, os.W_OK):
            missing.append("Fan control helper (not installed)")

    return len(missing) == 0, missing


def setup_permissions() -> Tuple[bool, str]:
    """Execute privileged setup script with pkexec to configure permissions and Polkit."""
    user = os.environ.get("USER", "root")
    if not all(c.isalnum() or c in "-_" for c in user):
        return False, "Invalid username detected"

    script_lines = [
        "#!/bin/bash",
        "set -e",
        "echo 'Configuring ThinkNux hardware permissions...'",
    ]

    # Chmod all CPU core scaling governors
    script_lines.append("for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do")
    script_lines.append('  [ -e "$f" ] || continue')
    script_lines.append('  chmod 666 "$f" 2>/dev/null || true')
    script_lines.append(f'  chown {user}:root "$f" 2>/dev/null || true')
    script_lines.append("done")

    for f_path in required_files():
        if Path(f_path).exists():
            script_lines.append(f"if [ -f '{f_path}' ]; then")
            script_lines.append(f"  chmod 666 '{f_path}' 2>/dev/null || true")
            script_lines.append(f"  chown {user}:root '{f_path}' 2>/dev/null || true")
            script_lines.append("fi")

    # Install tmpfiles.d rule to maintain permissions across reboots
    script_lines.append("mkdir -p /etc/tmpfiles.d")
    script_lines.append("cat > /etc/tmpfiles.d/thinknux.conf << 'TMPFILESEOF'")
    script_lines.append("z /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 0666 - - -")
    script_lines.append("z /sys/devices/system/cpu/intel_pstate/no_turbo 0666 - - -")
    script_lines.append("z /sys/devices/system/cpu/cpufreq/boost 0666 - - -")
    script_lines.append("z /sys/class/power_supply/BAT*/charge_control_* 0666 - - -")
    script_lines.append("z /sys/class/power_supply/BAT*/charge_*_threshold 0666 - - -")
    script_lines.append("z /sys/class/power_supply/BAT*/charge_behaviour 0666 - - -")
    script_lines.append("z /sys/devices/platform/i8042/serio*/serio*/sensitivity 0666 - - -")
    script_lines.append("z /sys/devices/platform/i8042/serio*/serio*/press_to_select 0666 - - -")
    script_lines.append("z /sys/devices/platform/i8042/serio*/serio*/rate 0666 - - -")
    script_lines.append("z /sys/devices/platform/i8042/serio*/serio*/resolution 0666 - - -")
    script_lines.append("z /sys/class/leds/tpacpi::*/brightness 0666 - - -")
    script_lines.append("z /sys/class/leds/tpacpi::*/trigger 0666 - - -")
    script_lines.append("TMPFILESEOF")
    script_lines.append("systemd-tmpfiles --create /etc/tmpfiles.d/thinknux.conf 2>/dev/null || true")

    # Install helper and polkit rule if not package-managed
    if helper_is_packaged():
        script_lines.append("echo 'Packaged helper detected; preserving existing helper files'")
    else:
        helper_dir = os.path.dirname(HELPER_SELF_INSTALL_PATH)
        script_lines.append(f"mkdir -p '{helper_dir}'")
        script_lines.append(f"cat > '{HELPER_SELF_INSTALL_PATH}' << 'HELPEREOF'")
        script_lines.append(HELPER_SCRIPT_CONTENT.strip())
        script_lines.append("HELPEREOF")
        script_lines.append(f"chmod 755 '{HELPER_SELF_INSTALL_PATH}'")

        script_lines.append("mkdir -p /etc/polkit-1/rules.d")
        script_lines.append(f"cat > '{POLKIT_RULE_PATH}' << 'RULEEOF'")
        script_lines.append(polkit_rule().strip())
        script_lines.append("RULEEOF")
        script_lines.append(
            "systemctl reload polkit 2>/dev/null || killall -HUP polkitd 2>/dev/null || true"
        )

    script_lines.append("echo 'ThinkNux permissions successfully configured!'")
    script_lines.append("exit 0")

    script_content = "\n".join(script_lines)

    try:
        res = subprocess.run(
            ["pkexec", "bash", "-c", script_content],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        if res.returncode == 0:
            return True, "Permissions configured successfully."
        return False, res.stderr.strip() or f"pkexec returned error code {res.returncode}"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"
