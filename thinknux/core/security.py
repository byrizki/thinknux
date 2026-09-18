"""ClamAV antivirus integration and file scanning."""

import datetime
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Callable, List, Optional, Tuple

from ..models.security import ScanResult, SecurityStatus, ThreatInfo


def check_clamav_installed() -> bool:
    """Check whether clamscan binary is available in PATH."""
    return shutil.which("clamscan") is not None


def check_clamd_running() -> bool:
    """Check if ClamAV daemon is currently active."""
    for service in ["clamav-daemon", "clamd@scan", "clamd"]:
        try:
            res = subprocess.run(
                ["systemctl", "is-active", service],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if res.returncode == 0 and "active" in res.stdout:
                return True
        except Exception:
            pass
    return False


def get_database_info() -> Tuple[str, str, str]:
    """Extract database version, last update timestamp, and definitions count."""
    daily_cvd = Path("/var/lib/clamav/daily.cvd")
    main_cvd = Path("/var/lib/clamav/main.cvd")

    db_version = "Unknown"
    last_update = "Unknown"
    definitions_count = "Unknown"

    if daily_cvd.is_file() or main_cvd.is_file():
        target = daily_cvd if daily_cvd.is_file() else main_cvd
        try:
            mtime = target.stat().st_mtime
            last_update = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    if shutil.which("sigtool"):
        try:
            res = subprocess.run(
                ["sigtool", "--info", "/var/lib/clamav/daily.cvd"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            for line in res.stdout.splitlines():
                if "Version:" in line:
                    db_version = line.split(":", 1)[1].strip()
                elif "Signatures:" in line:
                    definitions_count = line.split(":", 1)[1].strip()
        except Exception:
            pass

    return db_version, last_update, definitions_count


def get_security_status() -> SecurityStatus:
    """Query current ClamAV installation, daemon, and definition state."""
    installed = check_clamav_installed()
    if not installed:
        return SecurityStatus(
            clamav_installed=False,
            clamav_running=False,
            database_version="N/A",
            last_update="N/A",
            definitions_count="N/A",
        )

    running = check_clamd_running()
    db_ver, last_up, count = get_database_info()
    return SecurityStatus(
        clamav_installed=True,
        clamav_running=running,
        database_version=db_ver,
        last_update=last_up,
        definitions_count=count,
    )


def get_security_log_path() -> Path:
    """Return the path to the persistent clamav scan log file."""
    return Path.home() / ".config" / "thinknux" / "clamav_scan.log"


def append_security_log(line: str) -> None:
    """Append a log line to the persistent clamav scan log file."""
    try:
        log_file = get_security_log_path()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Bounded log file: if size > 2MB, prune to last 1000 lines
        if log_file.exists() and log_file.stat().st_size > 2 * 1024 * 1024:
            try:
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                log_file.write_text("\n".join(lines[-1000:]) + "\n", encoding="utf-8")
            except Exception:
                pass
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_recent_security_logs(max_lines: int = 150) -> List[str]:
    """Read the latest log lines from the persistent security log."""
    log_file = get_security_log_path()
    if not log_file.exists():
        return []
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-max_lines:]
    except Exception:
        return []


def clear_security_log() -> None:
    """Clear the persistent security log file."""
    try:
        log_file = get_security_log_path()
        if log_file.exists():
            log_file.write_text("", encoding="utf-8")
    except Exception:
        pass


def update_virus_definitions(log_cb: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
    """Execute freshclam to update virus database signatures."""
    if not shutil.which("freshclam"):
        msg = "freshclam is not installed"
        append_security_log(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Definitions Update] Error: {msg}")
        return False, msg

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_msg = f"[{ts}] [Definitions Update] Starting freshclam signature update..."
    if log_cb:
        log_cb(start_msg)
    append_security_log(start_msg)

    try:
        proc = subprocess.Popen(
            ["pkexec", "freshclam"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output_lines: List[str] = []
        if proc.stdout:
            for line in proc.stdout:
                line_clean = line.strip()
                if not line_clean:
                    continue
                output_lines.append(line_clean)
                if log_cb:
                    log_cb(line_clean)
                append_security_log(line_clean)

        proc.wait(timeout=120)
        res_msg = "Definitions updated successfully." if proc.returncode == 0 else f"freshclam exited with code {proc.returncode}"
        done_msg = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Definitions Update] {res_msg}"
        if log_cb:
            log_cb(done_msg)
        append_security_log(done_msg)
        return (proc.returncode == 0), res_msg
    except Exception as exc:
        err_msg = f"Failed to run freshclam: {exc}"
        append_security_log(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Definitions Update] {err_msg}")
        return False, err_msg


def check_freshclam_service_active() -> bool:
    """Check if clamav-freshclam.service is active."""
    try:
        res = subprocess.run(
            ["systemctl", "is-active", "clamav-freshclam.service"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return res.returncode == 0 and "active" in res.stdout
    except Exception:
        return False


def set_freshclam_service(enabled: bool) -> Tuple[bool, str]:
    """Enable and start or disable clamav-freshclam.service."""
    action = "enable --now" if enabled else "disable --now"
    try:
        res = subprocess.run(
            ["pkexec", "systemctl", *action.split(), "clamav-freshclam.service"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0:
            return True, "Freshclam service updated."
        return False, res.stderr or res.stdout
    except Exception as exc:
        return False, str(exc)


_last_auto_scan_time: float = 0.0
_last_auto_update_time: float = 0.0


def is_on_battery() -> bool:
    """Check if the system is currently running on battery power."""
    ps_dir = Path("/sys/class/power_supply")
    if not ps_dir.is_dir():
        return False

    for p in ps_dir.glob("*"):
        type_file = p / "type"
        online_file = p / "online"
        if type_file.is_file() and online_file.is_file():
            try:
                t = type_file.read_text(encoding="utf-8").strip()
                o = online_file.read_text(encoding="utf-8").strip()
                if t in ("Mains", "USB") and o == "1":
                    return False
            except Exception:
                pass

    for p in ps_dir.glob("BAT*"):
        status_file = p / "status"
        if status_file.is_file():
            try:
                st = status_file.read_text(encoding="utf-8").strip().lower()
                if st == "discharging":
                    return True
            except Exception:
                pass

    return False


def resolve_scan_target(target_key: str) -> str:
    """Resolve target key to filesystem path."""
    home = Path.home()
    if target_key == "downloads":
        dl = home / "Downloads"
        return str(dl) if dl.exists() else str(home)
    elif target_key == "documents":
        doc = home / "Documents"
        return str(doc) if doc.exists() else str(home)
    return str(home)


def scan_path(
    target_path: str,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
    low_priority: bool = False,
    max_filesize_mb: int = 25,
) -> ScanResult:
    """Run clamscan on the specified directory or file and collect findings."""
    if not check_clamav_installed():
        err_msg = "clamscan is not installed"
        append_security_log(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scan error: {err_msg}")
        return ScanResult(
            success=False,
            scanned_files=0,
            infected_files=0,
            scan_time="0s",
            error=err_msg,
        )

    start_time = time.time()
    dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_msg = f"[{dt_str}] Starting scan of {target_path} (max file size: {max_filesize_mb}MB)..."
    if log_cb:
        log_cb(start_msg)
    append_security_log(start_msg)

    base_cmd = ["clamscan", "-r"]
    if max_filesize_mb > 0:
        base_cmd.extend([
            f"--max-filesize={max_filesize_mb}M",
            f"--max-scansize={max(100, max_filesize_mb * 4)}M",
        ])
    base_cmd.append(target_path)

    if low_priority:
        prefix = ["nice", "-n", "19"]
        if shutil.which("ionice"):
            prefix = ["ionice", "-c", "3"] + prefix
        cmd = prefix + base_cmd
    else:
        cmd = base_cmd

    threats: List[ThreatInfo] = []
    logs: List[str] = []
    scanned_files = 0
    infected_files = 0
    last_report_time = time.time()
    in_summary = False

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if proc.stdout:
            for line in proc.stdout:
                line_str = line.strip()
                if not line_str:
                    continue
                logs.append(line_str)

                # Check for FOUND threat line: /path/to/file: Threat.Name FOUND
                if "FOUND" in line_str and ":" in line_str:
                    file_p, rest = line_str.split(":", 1)
                    threat_name = rest.replace("FOUND", "").strip()
                    threats.append(ThreatInfo(file_path=file_p.strip(), threat_name=threat_name))
                    threat_msg = f"[THREAT DETECTED] {line_str}"
                    if log_cb:
                        log_cb(threat_msg)
                    append_security_log(threat_msg)

                elif line_str.endswith(": OK"):
                    scanned_files += 1
                    now = time.time()
                    if now - last_report_time >= 0.8 or scanned_files % 50 == 0:
                        last_report_time = now
                        fname = Path(line_str[:-4]).name
                        progress_msg = f"Scanning ({scanned_files} files checked)... {fname}"
                        if log_cb:
                            log_cb(progress_msg)
                        if progress_cb:
                            progress_cb(scanned_files)

                elif "----------- SCAN SUMMARY -----------" in line_str or in_summary:
                    in_summary = True
                    if log_cb:
                        log_cb(line_str)
                    append_security_log(line_str)

                # Parse summary metrics at end of scan
                if "Scanned files:" in line_str:
                    match = re.search(r"Scanned files:\s+(\d+)", line_str)
                    if match:
                        scanned_files = int(match.group(1))
                if "Infected files:" in line_str:
                    match = re.search(r"Infected files:\s+(\d+)", line_str)
                    if match:
                        infected_files = int(match.group(1))

        proc.wait(timeout=3600)
        duration = round(time.time() - start_time, 1)

        end_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        end_msg = f"[{end_dt}] Scan finished: {scanned_files} files scanned, {infected_files or len(threats)} threat(s) detected in {duration}s."
        if log_cb:
            log_cb(end_msg)
        append_security_log(end_msg)

        return ScanResult(
            success=True,
            scanned_files=scanned_files,
            infected_files=infected_files or len(threats),
            scan_time=f"{duration}s",
            threats=threats,
            logs=logs[-50:],
            error=None,
        )
    except Exception as exc:
        err_msg = f"Scan error: {exc}"
        append_security_log(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {err_msg}")
        return ScanResult(
            success=False,
            scanned_files=0,
            infected_files=0,
            scan_time="0s",
            error=str(exc),
        )


def run_auto_protection_cycle(
    auto_update: bool,
    auto_scan: bool,
    scan_interval_hours: int,
    scan_target_key: str,
    pause_on_battery: bool = True,
    max_file_size_mb: int = 25,
    threat_cb: Optional[Callable[[ScanResult], None]] = None,
) -> None:
    """Invoked by background daemon to execute scheduled update and scan if due."""
    global _last_auto_scan_time, _last_auto_update_time
    now = time.time()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if pause_on_battery and is_on_battery():
        interval_secs = max(1, scan_interval_hours) * 3600
        if auto_scan and (now - _last_auto_scan_time > interval_secs):
            _last_auto_scan_time = now
            append_security_log(f"[{ts}] [Auto-Protection] Scheduled scan postponed: running on battery power.")
        return

    # 1. Auto update definitions if due (every 12 hours)
    if auto_update and (now - _last_auto_update_time > 12 * 3600):
        _last_auto_update_time = now
        _, last_up, _ = get_database_info()
        if last_up == "Unknown" or not check_freshclam_service_active():
            append_security_log(f"[{ts}] [Auto-Protection] Triggering background definition update...")
            update_virus_definitions()

    # 2. Auto scan if due
    interval_secs = max(1, scan_interval_hours) * 3600
    if auto_scan and (now - _last_auto_scan_time > interval_secs):
        _last_auto_scan_time = now
        target_path = resolve_scan_target(scan_target_key)
        append_security_log(f"[{ts}] [Auto-Protection] Triggering background scan on {target_path} (low priority, max {max_file_size_mb}MB)...")
        res = scan_path(target_path, low_priority=True, max_filesize_mb=max_file_size_mb)
        if res.infected_files > 0 and threat_cb:
            threat_cb(res)
