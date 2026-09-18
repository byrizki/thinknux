"""System activity monitor for CPU, memory, disk, network, and processes."""

import os
from typing import List

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from ...models.monitor import (
    CoreStats,
    CpuStats,
    DiskStats,
    LoadAverage,
    MemoryStats,
    NetworkStats,
    ProcessInfo,
    SystemMonitor,
)


from typing import List, Tuple


def collect_quick_cpu_mem() -> Tuple[float, float, int, int]:
    """Fast-path reading of (cpu_percent, mem_percent, mem_used_bytes, mem_total_bytes) in <2ms."""
    if not HAS_PSUTIL:
        return 0.0, 0.0, 0, 0
    cpu = psutil.cpu_percent(interval=None)
    vm = psutil.virtual_memory()
    return float(cpu), float(vm.percent), int(vm.used), int(vm.total)


def collect_system_stats(include_processes: bool = True) -> SystemMonitor:
    """Collect hardware and OS resource utilization metrics.
    
    If include_processes is False, skips scanning the full process table (saves ~250ms).
    """
    # 1. Load Average
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1, load5, load15 = 0.0, 0.0, 0.0
    load_avg = LoadAverage(one_min=load1, five_min=load5, fifteen_min=load15)

    # 2. CPU
    if HAS_PSUTIL:
        overall_cpu = psutil.cpu_percent(interval=None)
        per_core_pct = psutil.cpu_percent(interval=None, percpu=True)
        freqs = psutil.cpu_freq(percpu=True) or []
        cores: List[CoreStats] = []
        for idx, pct in enumerate(per_core_pct):
            freq = int(freqs[idx].current) if idx < len(freqs) and freqs[idx] else 0
            cores.append(CoreStats(core_id=idx, usage_percent=pct, frequency=freq))
        cpu_stats = CpuStats(usage_percent=overall_cpu, cores=cores, load_avg=load_avg)
    else:
        cpu_stats = CpuStats(usage_percent=0.0, cores=[], load_avg=load_avg)

    # 3. Memory
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        mem_stats = MemoryStats(
            total=vm.total,
            used=vm.used,
            available=vm.available,
            usage_percent=vm.percent,
            swap_total=swap.total,
            swap_used=swap.used,
        )
    else:
        mem_stats = MemoryStats(
            total=0, used=0, available=0, usage_percent=0.0, swap_total=0, swap_used=0
        )

    # 4. Disk
    disks: List[DiskStats] = []
    if HAS_PSUTIL:
        for part in psutil.disk_partitions(all=False):
            # Skip read-only loop devices or snaps
            if part.mountpoint.startswith(("/snap", "/var/lib/snapd", "/boot/efi")):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append(
                    DiskStats(
                        device=part.device,
                        mount_point=part.mountpoint,
                        total=usage.total,
                        used=usage.used,
                        available=usage.free,
                        usage_percent=usage.percent,
                        filesystem=part.fstype,
                    )
                )
            except (PermissionError, FileNotFoundError):
                continue

    # 5. Network
    nets: List[NetworkStats] = []
    if HAS_PSUTIL:
        net_io = psutil.net_io_counters(pernic=True)
        for iface, stats in net_io.items():
            if iface.startswith("lo"):
                continue
            nets.append(
                NetworkStats(
                    interface=iface,
                    rx_bytes=stats.bytes_recv,
                    tx_bytes=stats.bytes_sent,
                    rx_packets=stats.packets_recv,
                    tx_packets=stats.packets_sent,
                )
            )

    # 6. Top Processes (only scanned if requested)
    processes: List[ProcessInfo] = []
    if HAS_PSUTIL and include_processes:
        proc_list = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
            try:
                info = p.info
                cpu_p = float(info.get("cpu_percent") or 0.0)
                mem_mb = 0.0
                mem_info = info.get("memory_info")
                if mem_info:
                    mem_mb = round(mem_info.rss / (1024 * 1024), 1)
                proc_list.append(
                    ProcessInfo(
                        pid=int(info["pid"]),
                        name=str(info.get("name") or "unknown"),
                        cpu_percent=cpu_p,
                        memory_mb=mem_mb,
                        status=str(info.get("status") or "unknown"),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU descending, take top 15
        proc_list.sort(key=lambda x: x.cpu_percent, reverse=True)
        processes = proc_list[:15]

    return SystemMonitor(
        cpu=cpu_stats,
        memory=mem_stats,
        disk=disks,
        network=nets,
        processes=processes,
    )
