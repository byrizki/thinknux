"""System tray indicator integration using D-Bus StatusNotifierItem (SNI) and DBusMenu.

Provides native Linux taskbar / system tray icon support for GTK4 applications
without requiring legacy GTK3 AyatanaAppIndicator libraries.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import os
import threading

try:
    from gi.repository import GLib
    HAS_GLIB = True
except ImportError:
    HAS_GLIB = False

from ...core.hardware.battery import get_battery_thresholds, set_battery_thresholds
from ...core.hardware.fan import PROC_FAN, parse_fan_proc, set_fan_speed
from ...core.hardware.performance import get_power_profile, set_power_profile
from ...core.security import resolve_scan_target, scan_path
from ...core.settings import get_settings_manager
from ...models.settings import BatteryThresholds


class _DBusMenu:
    """
    <node>
      <interface name='com.canonical.dbusmenu'>
        <property name='Version' type='u' access='read'/>
        <property name='TextDirection' type='s' access='read'/>
        <property name='Status' type='s' access='read'/>
        <property name='IconThemePath' type='as' access='read'/>
        <method name='GetLayout'>
          <arg type='i' name='parentId' direction='in'/>
          <arg type='i' name='recursionDepth' direction='in'/>
          <arg type='as' name='propertyNames' direction='in'/>
          <arg type='u' name='revision' direction='out'/>
          <arg type='(ia{sv}av)' name='layout' direction='out'/>
        </method>
        <method name='GetGroupProperties'>
          <arg type='ai' name='ids' direction='in'/>
          <arg type='as' name='propertyNames' direction='in'/>
          <arg type='a(ia{sv})' name='properties' direction='out'/>
        </method>
        <method name='GetProperty'>
          <arg type='i' name='id' direction='in'/>
          <arg type='s' name='name' direction='in'/>
          <arg type='v' name='value' direction='out'/>
        </method>
        <method name='Event'>
          <arg type='i' name='id' direction='in'/>
          <arg type='s' name='eventId' direction='in'/>
          <arg type='v' name='data' direction='in'/>
          <arg type='u' name='timestamp' direction='in'/>
        </method>
        <method name='AboutToShow'>
          <arg type='i' name='id' direction='in'/>
          <arg type='b' name='needUpdate' direction='out'/>
        </method>
      </interface>
    </node>
    """

    Version = 3
    TextDirection = "ltr"
    Status = "normal"
    IconThemePath = []

    _MENU_ITEMS: List[int] = [1, 2, 10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 40, 41, 99]

    def __init__(self, on_toggle: Callable[[], None], on_quit: Callable[[], None]):
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._override_power: Optional[str] = None
        self._override_fan: Optional[str] = None
        self._override_bat: Optional[int] = None

    def _query_live_states(self) -> Tuple[str, str, int]:
        """Query active power profile, fan level, and battery stop threshold."""
        # 1. Power profile
        if self._override_power:
            prof = self._override_power
        else:
            try:
                prof = get_power_profile().current
            except Exception:
                prof = "balanced"

        # 2. Fan level
        if self._override_fan:
            fan_lvl = self._override_fan
        else:
            fan_lvl = "auto"
            try:
                p = Path(PROC_FAN)
                if p.is_file():
                    parsed = parse_fan_proc(p.read_text(encoding="utf-8", errors="replace"))
                    fan_lvl = parsed.get("level", "auto").strip().lower()
            except Exception:
                pass

        # 3. Battery stop threshold
        if self._override_bat is not None:
            bat_stop = self._override_bat
        else:
            bat_stop = 100
            try:
                bat_stop = get_battery_thresholds().stop
            except Exception:
                pass

        return prof, fan_lvl, bat_stop

    def _get_items_props(self) -> Dict[int, Dict[str, Any]]:
        if not HAS_GLIB:
            return {}

        prof, fan_lvl, bat_stop = self._query_live_states()

        is_perf = 1 if prof == "performance" else 0
        is_balanced = 1 if prof == "balanced" else 0
        is_saver = 1 if prof == "power-saver" else 0

        is_fan_auto = 1 if fan_lvl in ("auto", "") else 0
        is_fan_quiet = 1 if fan_lvl in ("1", "level 1") else 0
        is_fan_full = 1 if fan_lvl in ("full-speed", "disengaged", "7") else 0

        is_bat_80 = 1 if bat_stop <= 85 else 0
        is_bat_100 = 1 if bat_stop > 85 else 0

        return {
            1: {"label": GLib.Variant("s", "Show / Hide ThinkNux"), "enabled": GLib.Variant("b", True)},
            2: {"type": GLib.Variant("s", "separator")},

            10: {
                "label": GLib.Variant("s", "Power: Performance"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_perf),
            },
            11: {
                "label": GLib.Variant("s", "Power: Balanced"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_balanced),
            },
            12: {
                "label": GLib.Variant("s", "Power: Power Saver"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_saver),
            },
            13: {"type": GLib.Variant("s", "separator")},

            20: {
                "label": GLib.Variant("s", "Fan: Auto (BIOS)"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_fan_auto),
            },
            21: {
                "label": GLib.Variant("s", "Fan: Level 1 (Quiet)"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_fan_quiet),
            },
            22: {
                "label": GLib.Variant("s", "Fan: Full Speed"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_fan_full),
            },
            23: {"type": GLib.Variant("s", "separator")},

            30: {
                "label": GLib.Variant("s", "Battery: 80% Conservation Limit"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_bat_80),
            },
            31: {
                "label": GLib.Variant("s", "Battery: 100% Full Charge"),
                "enabled": GLib.Variant("b", True),
                "toggle-type": GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", is_bat_100),
            },
            32: {"type": GLib.Variant("s", "separator")},

            40: {"label": GLib.Variant("s", "ClamAV: Quick Antivirus Scan"), "enabled": GLib.Variant("b", True)},
            41: {"type": GLib.Variant("s", "separator")},

            99: {"label": GLib.Variant("s", "Quit ThinkNux"), "enabled": GLib.Variant("b", True)},
        }

    def GetLayout(self, parentId, recursionDepth, propertyNames):
        def _make_child_variant(item_id, props):
            child_tuple = (item_id, props, [])
            return GLib.Variant("(ia{sv}av)", child_tuple)

        items_props = self._get_items_props()

        if parentId != 0:
            props = items_props.get(parentId, {})
            return (1, (parentId, props, []))

        children = [_make_child_variant(idx, items_props[idx]) for idx in self._MENU_ITEMS if idx in items_props]
        root = (0, {}, children)
        return (1, root)

    def GetGroupProperties(self, ids, propertyNames):
        items_props = self._get_items_props()
        res = []
        for i in ids:
            if i in items_props:
                res.append((i, items_props[i]))
        return res

    def GetProperty(self, id, name):
        items_props = self._get_items_props()
        if id in items_props and name in items_props[id]:
            return items_props[id][name]
        if HAS_GLIB:
            return GLib.Variant("s", "")
        return ""

    def Event(self, id, eventId, data, timestamp):
        if eventId != "clicked":
            return

        if id == 1:
            if HAS_GLIB:
                GLib.idle_add(self._on_toggle)
            else:
                self._on_toggle()

        elif id in (10, 11, 12):
            prof_map = {10: "performance", 11: "balanced", 12: "power-saver"}
            prof = prof_map[id]
            self._override_power = prof
            threading.Thread(target=lambda: set_power_profile(prof), daemon=True).start()

        elif id == 20:
            self._override_fan = "auto"
            threading.Thread(target=lambda: set_fan_speed("auto"), daemon=True).start()
        elif id == 21:
            self._override_fan = "1"
            threading.Thread(target=lambda: set_fan_speed("1"), daemon=True).start()
        elif id == 22:
            self._override_fan = "full-speed"
            threading.Thread(target=lambda: set_fan_speed("full-speed"), daemon=True).start()

        elif id == 30:
            self._override_bat = 80
            def _apply_bat_80():
                set_battery_thresholds(75, 80)
                try:
                    mgr = get_settings_manager()
                    app_s = mgr.settings
                    app_s.battery_thresholds = BatteryThresholds(start=75, stop=80)
                    mgr.save(app_s)
                except Exception:
                    pass
            threading.Thread(target=_apply_bat_80, daemon=True).start()

        elif id == 31:
            self._override_bat = 100
            def _apply_bat_100():
                set_battery_thresholds(0, 100)
                try:
                    mgr = get_settings_manager()
                    app_s = mgr.settings
                    app_s.battery_thresholds = BatteryThresholds(start=0, stop=100)
                    mgr.save(app_s)
                except Exception:
                    pass
            threading.Thread(target=_apply_bat_100, daemon=True).start()

        elif id == 40:
            def _quick_scan():
                target = resolve_scan_target("downloads")
                scan_path(target, low_priority=True)
            threading.Thread(target=_quick_scan, daemon=True).start()

        elif id == 99:
            if HAS_GLIB:
                GLib.idle_add(self._on_quit)
            else:
                self._on_quit()

    def AboutToShow(self, id):
        self._override_power = None
        self._override_fan = None
        self._override_bat = None
        return True


class _StatusNotifierItem:
    """
    <node>
      <interface name='org.kde.StatusNotifierItem'>
        <property name='Category' type='s' access='read'/>
        <property name='Id' type='s' access='read'/>
        <property name='Title' type='s' access='read'/>
        <property name='Status' type='s' access='read'/>
        <property name='IconName' type='s' access='read'/>
        <property name='IconThemePath' type='s' access='read'/>
        <property name='Menu' type='o' access='read'/>
        <property name='ItemIsMenu' type='b' access='read'/>
        <method name='ContextMenu'>
          <arg type='i' name='x' direction='in'/>
          <arg type='i' name='y' direction='in'/>
        </method>
        <method name='Activate'>
          <arg type='i' name='x' direction='in'/>
          <arg type='i' name='y' direction='in'/>
        </method>
        <method name='SecondaryActivate'>
          <arg type='i' name='x' direction='in'/>
          <arg type='i' name='y' direction='in'/>
        </method>
        <method name='Scroll'>
          <arg type='i' name='delta' direction='in'/>
          <arg type='s' name='orientation' direction='in'/>
        </method>
      </interface>
    </node>
    """

    Category = "ApplicationStatus"
    Id = "com.byrizki.thinknux"
    Title = "ThinkNux"
    Status = "Active"
    IconName = "utilities-system-monitor-symbolic"
    IconThemePath = ""
    Menu = "/StatusNotifierMenu"
    ItemIsMenu = False

    def __init__(self, on_activate: Callable[[], None]):
        self._on_activate = on_activate

    def ContextMenu(self, x, y):
        pass

    def Activate(self, x, y):
        if HAS_GLIB:
            GLib.idle_add(self._on_activate)
        else:
            self._on_activate()

    def SecondaryActivate(self, x, y):
        self.Activate(x, y)

    def Scroll(self, delta, orientation):
        pass


class TrayIndicator:
    """Manages system taskbar tray indicator icon via D-Bus StatusNotifierItem."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_hide: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._on_show = on_show
        self._on_hide = on_hide
        self._on_quit = on_quit
        self._is_visible = True
        self._server = None

        self._init_indicator()

    def set_window_visible(self, visible: bool) -> None:
        """Inform indicator of window visibility state."""
        self._is_visible = visible

    def toggle_window(self) -> None:
        """Toggle between presenting and hiding the application window."""
        if self._is_visible:
            self._on_hide()
        else:
            self._on_show()

    def _init_indicator(self) -> None:
        try:
            import pydbus
            bus = pydbus.SessionBus()
            bus_name = f"org.kde.StatusNotifierItem-thinknux-{os.getpid()}"

            sni = _StatusNotifierItem(on_activate=self.toggle_window)
            menu = _DBusMenu(on_toggle=self.toggle_window, on_quit=self._on_quit)

            self._server = bus.publish(
                bus_name,
                ("/StatusNotifierItem", sni),
                ("/StatusNotifierMenu", menu),
            )

            try:
                watcher = bus.get("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher")
                watcher.RegisterStatusNotifierItem("/StatusNotifierItem")
            except Exception:
                pass
        except Exception:
            self._server = None

    def stop(self) -> None:
        """Cleanly unpublish indicator from D-Bus."""
        if self._server:
            try:
                self._server.unpublish()
            except Exception:
                pass
            self._server = None
