"""Intel RAPL (Running Average Power Limit) TDP package management interface.

Reads and configures processor package power limits (PL1 sustained and PL2 burst)
via /sys/class/powercap/intel-rapl/ to eliminate aggressive firmware thermal throttling.
"""

from pathlib import Path
import subprocess
from typing import Optional, Tuple

from ...models.rapl import RaplLimits

RAPL_PACKAGE_PATH = Path("/sys/class/powercap/intel-rapl/intel-rapl:0")


def is_rapl_supported() -> bool:
    """Check if Intel RAPL powercap interface is available for package-0."""
    return RAPL_PACKAGE_PATH.is_dir() and (RAPL_PACKAGE_PATH / "constraint_0_power_limit_uw").is_file()


def get_rapl_limits() -> RaplLimits:
    """Read active PL1 and PL2 power limits from hardware sysfs."""
    if not is_rapl_supported():
        return RaplLimits(supported=False)

    def read_int(fname: str) -> int:
        f = RAPL_PACKAGE_PATH / fname
        if f.is_file():
            try:
                return int(f.read_text(encoding="utf-8").strip())
            except Exception:
                pass
        return 0

    pl1_uw = read_int("constraint_0_power_limit_uw")
    pl2_uw = read_int("constraint_1_power_limit_uw")
    pl1_time_us = read_int("constraint_0_time_window_us")
    pl2_time_us = read_int("constraint_1_time_window_us")

    enabled_file = RAPL_PACKAGE_PATH / "enabled"
    enabled = True
    if enabled_file.is_file():
        try:
            enabled = enabled_file.read_text(encoding="utf-8").strip() == "1"
        except Exception:
            pass

    return RaplLimits(
        supported=True,
        name="package-0",
        pl1_watts=round(pl1_uw / 1_000_000.0, 1),
        pl2_watts=round(pl2_uw / 1_000_000.0, 1),
        pl1_time_window_sec=round(pl1_time_us / 1_000_000.0, 2),
        pl2_time_window_sec=round(pl2_time_us / 1_000_000.0, 2),
        enabled=enabled,
    )


def set_rapl_limits(pl1_watts: float, pl2_watts: float) -> Tuple[bool, Optional[str]]:
    """Configure PL1 (sustained) and PL2 (burst) power caps in Watts."""
    if not is_rapl_supported():
        return False, "Intel RAPL is not supported on this platform"

    if pl1_watts <= 0 or pl2_watts <= 0:
        return False, "Power limits must be greater than 0 Watts"

    if pl1_watts > pl2_watts:
        return False, "PL1 sustained limit cannot exceed PL2 burst limit"

    pl1_uw = str(int(pl1_watts * 1_000_000))
    pl2_uw = str(int(pl2_watts * 1_000_000))

    target_pl1 = RAPL_PACKAGE_PATH / "constraint_0_power_limit_uw"
    target_pl2 = RAPL_PACKAGE_PATH / "constraint_1_power_limit_uw"

    # 1. Direct write attempt
    try:
        target_pl1.write_text(pl1_uw, encoding="utf-8")
        target_pl2.write_text(pl2_uw, encoding="utf-8")
        return True, None
    except PermissionError:
        pass
    except Exception as exc:
        return False, str(exc)

    # 2. Privileged write via pkexec
    cmd = [
        "pkexec",
        "sh",
        "-c",
        f"echo '{pl1_uw}' > '{target_pl1}' && echo '{pl2_uw}' > '{target_pl2}'",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        if res.returncode == 0:
            return True, None
        return False, res.stderr.strip() or "Permission denied updating RAPL limits"
    except Exception as exc:
        return False, f"Failed to execute pkexec: {exc}"
