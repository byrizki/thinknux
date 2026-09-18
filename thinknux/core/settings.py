"""Settings management and JSON persistence."""

import json
import os
from pathlib import Path
import threading
from typing import Optional

from ..models.settings import AppSettings, UserSettings

CONFIG_DIR = Path(os.path.expanduser("~/.config/thinknux"))
CONFIG_FILE = CONFIG_DIR / "config.json"
AUTOSTART_DIR = Path(os.path.expanduser("~/.config/autostart"))
AUTOSTART_FILE = AUTOSTART_DIR / "com.byrizki.thinknux.desktop"

AUTOSTART_TEMPLATE = """[Desktop Entry]
Type=Application
Name=ThinkNux
Comment=ThinkPad Management Application (inspired by ThinkUtils)
Exec=thinknux --minimized
Icon=com.byrizki.thinknux
Terminal=false
Categories=Utility;Settings;HardwareSettings;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""


class SettingsManager:
    """Thread-safe manager for loading, saving, and updating application settings."""

    def __init__(self, config_file: Path = CONFIG_FILE):
        self._config_file = config_file
        self._lock = threading.Lock()
        self._settings = self._load()

    @property
    def settings(self) -> AppSettings:
        with self._lock:
            return self._settings

    def _load(self) -> AppSettings:
        if self._config_file.is_file():
            try:
                data = json.loads(self._config_file.read_text(encoding="utf-8"))
                return AppSettings.from_dict(data)
            except Exception:
                pass
        return AppSettings()

    def save(self, settings: Optional[AppSettings] = None) -> bool:
        """Write configuration to disk safely."""
        with self._lock:
            if settings is not None:
                self._settings = settings

            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                tmp_file = self._config_file.with_suffix(".tmp")
                tmp_file.write_text(
                    json.dumps(self._settings.to_dict(), indent=2),
                    encoding="utf-8",
                )
                tmp_file.replace(self._config_file)
                self._apply_autostart(self._settings.user.auto_start)
                return True
            except Exception:
                return False

    def update_user_settings(self, user: UserSettings) -> bool:
        with self._lock:
            self._settings.user = user
        return self.save()

    def _apply_autostart(self, enabled: bool) -> None:
        try:
            if enabled:
                AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
                AUTOSTART_FILE.write_text(AUTOSTART_TEMPLATE, encoding="utf-8")
            elif AUTOSTART_FILE.exists():
                AUTOSTART_FILE.unlink()
        except Exception:
            pass


# Global singleton instance
_default_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = SettingsManager()
    return _default_manager
