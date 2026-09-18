"""System specifications and hardware identification."""

from pathlib import Path
import platform
import socket

from ...models.system import SystemInfo


def get_system_info() -> SystemInfo:
    """Gather hardware model, OS name, kernel, CPU, and RAM capacity."""
    # 1. Hostname
    hostname = socket.gethostname() or platform.node() or "Unknown"

    # 2. OS Pretty Name
    os_name = "Linux"
    os_release = Path("/etc/os-release")
    if os_release.is_file():
        try:
            for line in os_release.read_text(encoding="utf-8").splitlines():
                if line.startswith("PRETTY_NAME="):
                    os_name = line.split("=", 1)[1].strip('"')
                    break
        except Exception:
            pass

    # 3. Kernel version
    kernel = platform.release() or "Unknown"

    # 4. Machine / ThinkPad model
    model = "ThinkPad"
    dmi_version = Path("/sys/devices/virtual/dmi/id/product_version")
    dmi_name = Path("/sys/devices/virtual/dmi/id/product_name")
    if dmi_version.is_file():
        try:
            val = dmi_version.read_text(encoding="utf-8").strip()
            if val and val != "None":
                model = val
        except Exception:
            pass
    elif dmi_name.is_file():
        try:
            val = dmi_name.read_text(encoding="utf-8").strip()
            if val:
                model = val
        except Exception:
            pass

    # 5. CPU model
    cpu_model = platform.processor() or "Unknown CPU"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        try:
            for line in cpuinfo.read_text(encoding="utf-8").splitlines():
                if "model name" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

    # 6. Total Memory
    mem_total_str = "Unknown"
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    kb = int(parts[1])
                    gb = round(kb / (1024 * 1024), 1)
                    mem_total_str = f"{gb} GB"
                    break
        except Exception:
            pass

    return SystemInfo(
        hostname=hostname,
        os=os_name,
        kernel=kernel,
        model=model,
        cpu=cpu_model,
        memory=mem_total_str,
    )
