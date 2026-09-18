"""Interactive Cairo-based fan curve editor canvas with drag-and-drop point manipulation."""

from typing import Callable, List, Optional

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gtk

from ...models.fan import CurvePoint

TEMP_MIN = 30
TEMP_MAX = 100
LEVEL_MIN = 0
LEVEL_MAX = 7
POINT_RADIUS = 6.0


class FanCurveEditor(Gtk.DrawingArea):
    """Canvas for visualizing and interactively editing fan speed curve points."""

    def __init__(
        self,
        points: Optional[List[CurvePoint]] = None,
        on_changed: Optional[Callable[[List[CurvePoint]], None]] = None,
    ):
        super().__init__()
        self._points = sorted(
            list(points)
            if points
            else [
                CurvePoint(temp=40, level=0),
                CurvePoint(temp=50, level=1),
                CurvePoint(temp=60, level=3),
                CurvePoint(temp=70, level=5),
                CurvePoint(temp=80, level=7),
            ],
            key=lambda p: p.temp,
        )
        self._on_changed = on_changed
        self._current_temp: Optional[int] = None
        self._active_point_idx: Optional[int] = None

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_content_height(180)
        self.set_content_width(380)
        self.add_css_class("curve-editor-container")

        self.set_draw_func(self._draw)

        # Gestures for interaction
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    @property
    def points(self) -> List[CurvePoint]:
        return list(self._points)

    def set_points(self, points: List[CurvePoint]) -> None:
        self._points = sorted(list(points), key=lambda p: p.temp)
        self.queue_draw()

    def set_current_temperature(self, temp: Optional[int]) -> None:
        self._current_temp = temp
        self.queue_draw()

    def _temp_to_x(self, temp: float, width: float, pad_x: float) -> float:
        usable_w = width - 2 * pad_x
        ratio = (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
        return pad_x + ratio * usable_w

    def _level_to_y(self, level: float, height: float, pad_y: float) -> float:
        usable_h = height - 2 * pad_y
        # Inverted: level 7 is at top, level 0 is at bottom
        ratio = (level - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)
        return height - pad_y - ratio * usable_h

    def _x_to_temp(self, x: float, width: float, pad_x: float) -> int:
        usable_w = width - 2 * pad_x
        ratio = max(0.0, min(1.0, (x - pad_x) / usable_w))
        temp = TEMP_MIN + ratio * (TEMP_MAX - TEMP_MIN)
        return int(round(temp))

    def _y_to_level(self, y: float, height: float, pad_y: float) -> int:
        usable_h = height - 2 * pad_y
        ratio = max(0.0, min(1.0, (height - pad_y - y) / usable_h))
        level = LEVEL_MIN + ratio * (LEVEL_MAX - LEVEL_MIN)
        return int(round(level))

    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        pad_x = 45.0
        pad_y = 22.0

        # Background
        cr.set_source_rgba(0.12, 0.12, 0.14, 0.8)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Grid lines and labels (Y Axis: Levels 0-7)
        cr.set_line_width(0.75)
        cr.set_font_size(10.0)
        for lvl in range(LEVEL_MIN, LEVEL_MAX + 1):
            y = self._level_to_y(lvl, height, pad_y)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.1)
            cr.move_to(pad_x, y)
            cr.line_to(width - pad_x, y)
            cr.stroke()

            cr.set_source_rgba(0.7, 0.7, 0.7, 0.9)
            cr.move_to(12, y + 4)
            cr.show_text(f"Lvl {lvl}")

        # Grid lines and labels (X Axis: Temps)
        for t in range(TEMP_MIN, TEMP_MAX + 1, 10):
            x = self._temp_to_x(t, width, pad_x)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.1)
            cr.move_to(x, pad_y)
            cr.line_to(x, height - pad_y)
            cr.stroke()

            cr.set_source_rgba(0.7, 0.7, 0.7, 0.9)
            cr.move_to(x - 10, height - 10)
            cr.show_text(f"{t}°C")

        # Current temperature marker line
        if self._current_temp is not None:
            cur_x = self._temp_to_x(self._current_temp, width, pad_x)
            cr.set_source_rgba(0.3, 0.7, 1.0, 0.7)
            cr.set_line_width(1.5)
            cr.move_to(cur_x, pad_y)
            cr.line_to(cur_x, height - pad_y)
            cr.stroke()

            cr.set_source_rgba(0.3, 0.7, 1.0, 1.0)
            cr.move_to(cur_x - 14, pad_y - 8)
            cr.show_text(f"{self._current_temp}°C")

        # Plot fan curve connecting lines
        if self._points:
            cr.set_source_rgba(0.89, 0.14, 0.10, 0.9)  # ThinkPad Red (#e2231a)
            cr.set_line_width(2.5)

            # Start from min temp
            first_p = self._points[0]
            cr.move_to(
                self._temp_to_x(TEMP_MIN, width, pad_x),
                self._level_to_y(first_p.level, height, pad_y),
            )
            for p in self._points:
                cr.line_to(
                    self._temp_to_x(p.temp, width, pad_x),
                    self._level_to_y(p.level, height, pad_y),
                )
            # Extend to max temp
            last_p = self._points[-1]
            cr.line_to(
                self._temp_to_x(TEMP_MAX, width, pad_x),
                self._level_to_y(last_p.level, height, pad_y),
            )
            cr.stroke()

        # Plot control points
        for idx, p in enumerate(self._points):
            px = self._temp_to_x(p.temp, width, pad_x)
            py = self._level_to_y(p.level, height, pad_y)

            # Outer ring
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.arc(px, py, POINT_RADIUS + 2.0, 0, 2 * 3.14159)
            cr.fill()

            # Center fill (active point gets red, others dark)
            if idx == self._active_point_idx:
                cr.set_source_rgba(0.89, 0.14, 0.10, 1.0)
            else:
                cr.set_source_rgba(0.18, 0.18, 0.22, 1.0)
            cr.arc(px, py, POINT_RADIUS, 0, 2 * 3.14159)
            cr.fill()

    def _find_point_near(self, x: float, y: float) -> Optional[int]:
        width = self.get_width()
        height = self.get_height()
        pad_x = 45.0
        pad_y = 22.0

        for idx, p in enumerate(self._points):
            px = self._temp_to_x(p.temp, width, pad_x)
            py = self._level_to_y(p.level, height, pad_y)
            dist_sq = (px - x) ** 2 + (py - y) ** 2
            if dist_sq <= (POINT_RADIUS + 12.0) ** 2:
                return idx
        return None

    def _on_drag_begin(self, gesture: Gtk.GestureDrag, start_x: float, start_y: float) -> None:
        self._active_point_idx = self._find_point_near(start_x, start_y)
        if self._active_point_idx is not None:
            self.queue_draw()

    def _on_drag_update(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        if self._active_point_idx is None:
            return

        success, start_x, start_y = gesture.get_start_point()
        if not success:
            return

        cur_x = start_x + offset_x
        cur_y = start_y + offset_y

        width = self.get_width()
        height = self.get_height()
        pad_x = 45.0
        pad_y = 22.0

        new_temp = self._x_to_temp(cur_x, width, pad_x)
        new_level = self._y_to_level(cur_y, height, pad_y)

        # Ensure temperature monotonicity relative to neighbours
        idx = self._active_point_idx
        min_temp = self._points[idx - 1].temp + 2 if idx > 0 else TEMP_MIN
        max_temp = self._points[idx + 1].temp - 2 if idx < len(self._points) - 1 else TEMP_MAX

        bounded_temp = max(min_temp, min(max_temp, new_temp))
        self._points[idx] = CurvePoint(temp=bounded_temp, level=new_level)
        self.queue_draw()

    def _on_drag_end(self, _gesture: Gtk.GestureDrag, _offset_x: float, _offset_y: float) -> None:
        if self._active_point_idx is not None:
            self._active_point_idx = None
            self.queue_draw()
            if self._on_changed:
                self._on_changed(self._points)
