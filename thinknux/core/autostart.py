"""Desktop autostart configuration via XDG autostart desktop entries."""

from pathlib import Path
import shutil
import sys

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "com.byrizki.thinknux.desktop"


def get_executable_path() -> str:
    """Resolve the absolute path to the thinknux executable."""
    # Check if installed in system PATH
    system_bin = shutil.which("thinknux")
    if system_bin:
        return system_bin

    # Fallback to current project wrapper script
    project_bin = Path(__file__).resolve().parent.parent.parent / "bin" / "thinknux"
    if project_bin.exists():
        return str(project_bin)

    return f"{sys.executable} -m thinknux.main"


def is_autostart_enabled() -> bool:
    """Check whether the ThinkNux autostart entry is configured and active."""
    if not AUTOSTART_FILE.is_file():
        return False

    try:
        content = AUTOSTART_FILE.read_text(encoding="utf-8")
        if "X-GNOME-Autostart-enabled=false" in content:
            return False
        return True
    except Exception:
        return False


def set_autostart(enabled: bool) -> bool:
    """Enable or disable autostart on user session login."""
    try:
        if enabled:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            exec_cmd = f"{get_executable_path()} --minimized"
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=ThinkNux
Comment=ThinkPad Hardware and Power Management Utility (inspired by ThinkUtils)
Exec={exec_cmd}
Icon=com.byrizki.thinknux
Terminal=false
Categories=System;HardwareSettings;
X-GNOME-Autostart-enabled=true
"""
            AUTOSTART_FILE.write_text(desktop_content, encoding="utf-8")
        else:
            if AUTOSTART_FILE.exists():
                AUTOSTART_FILE.unlink()
        return True
    except Exception:
        return False
