"""Automated fan curve calculation and background control loop with watchdog management."""

import threading
import time
from typing import Callable, List, Optional

from ..models.fan import CurvePoint, FanCurveConfig
from .hardware.fan import arm_fan_watchdog, restore_fan_to_auto_blocking, set_fan_speed
from .hardware.thermal import get_cpu_temperature


def calculate_fan_level(temp: int, points: List[CurvePoint]) -> int:
    """Calculate the target fan level for a given temperature via linear interpolation."""
    if not points:
        return 0

    sorted_points = sorted(points, key=lambda p: p.temp)

    # Temperature below first threshold
    if temp <= sorted_points[0].temp:
        return sorted_points[0].level

    # Temperature above last threshold
    if temp >= sorted_points[-1].temp:
        return sorted_points[-1].level

    # Linear interpolation between adjacent points
    for i in range(len(sorted_points) - 1):
        p1 = sorted_points[i]
        p2 = sorted_points[i + 1]
        if p1.temp <= temp <= p2.temp:
            if p2.temp == p1.temp:
                return p1.level
            ratio = (temp - p1.temp) / (p2.temp - p1.temp)
            interpolated = p1.level + ratio * (p2.level - p1.level)
            return max(0, min(7, int(round(interpolated))))

    return sorted_points[-1].level


class FanCurveManager:
    """Manages fan curve state, background loop, and safety watchdog."""

    def __init__(self, config: Optional[FanCurveConfig] = None):
        self._config = config or FanCurveConfig()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_level: Optional[int] = None
        self._last_watchdog_time: float = 0.0
        self._on_update: Optional[Callable[[int, int], None]] = None  # (temp, level) callback

    @property
    def config(self) -> FanCurveConfig:
        with self._lock:
            return FanCurveConfig(
                enabled=self._config.enabled,
                points=list(self._config.points),
            )

    def set_config(self, config: FanCurveConfig) -> None:
        with self._lock:
            self._config = config
        if not config.enabled:
            # Revert immediately when disabled
            restore_fan_to_auto_blocking()
            self._last_level = None

    def set_on_update(self, callback: Optional[Callable[[int, int], None]]) -> None:
        self._on_update = callback

    def start(self) -> None:
        """Start the 2-second background temperature check and watchdog loop."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ThinkNuxFanCurve")
        self._thread.start()

    def stop(self) -> None:
        """Stop the background loop and restore fan to auto."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        restore_fan_to_auto_blocking()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop_event.wait(timeout=2.0)

    def _tick(self) -> None:
        with self._lock:
            enabled = self._config.enabled
            points = list(self._config.points)

        if not enabled:
            return

        temp = get_cpu_temperature()
        if temp is None:
            # Failsafe: if sensor reading fails, hand back to firmware auto
            if self._last_level is not None:
                restore_fan_to_auto_blocking()
                self._last_level = None
            return

        target_level = calculate_fan_level(temp, points)
        now = time.time()

        # Re-arm watchdog every 10 seconds or when level changes
        watchdog_due = (now - self._last_watchdog_time) >= 10.0
        level_changed = target_level != self._last_level

        if level_changed:
            set_fan_speed(str(target_level))
            self._last_level = target_level
            arm_fan_watchdog()
            self._last_watchdog_time = now
        elif watchdog_due:
            arm_fan_watchdog()
            self._last_watchdog_time = now

        if self._on_update:
            try:
                self._on_update(temp, target_level)
            except Exception:
                pass
