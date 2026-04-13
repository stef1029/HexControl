"""
Scales Plot Widget - Live weight readout using DearPyGui native plotting.

Displays a rolling 20-second window of scales weight readings at ~10Hz.
Uses dpg.add_plot() with line series — replaces the 477-line tkinter
Canvas implementation.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional, Protocol

import dearpygui.dearpygui as dpg

from hexcontrol.gui.dpg_app import frame_poller
from hexcontrol.gui.theme import Theme, hex_to_rgba


class ScalesClientProtocol(Protocol):
    """Protocol for scales client interface (duck typing)."""
    def get_weight(self) -> Optional[float]: ...


class ScalesPlotWidget:
    """
    Live-updating weight plot widget using DPG native plotting.

    Polls a scales client at ~10Hz and displays a rolling 20-second
    line chart.
    """

    POLL_INTERVAL_MS = 100
    WINDOW_SECONDS = 20.0
    DEFAULT_Y_MIN = -2.0
    DEFAULT_Y_MAX = 40.0

    def __init__(self, parent: int | str):
        self._parent = parent
        self._scales_client: Optional[ScalesClientProtocol] = None
        self._is_active = False

        # Data buffer
        self._data: deque[tuple[float, float]] = deque(maxlen=250)

        # Threshold
        self._threshold_value: Optional[float] = None

        # Battery detection
        self._battery_detection_enabled: bool = True
        self._static_threshold_seconds: float = 30.0
        self._static_jitter_tolerance: float = 0.01
        self._last_varied_time: float = 0.0
        self._static_alert_shown: bool = False
        self._last_weight: Optional[float] = None

        # DPG item IDs
        self._group_id: int | None = None
        self._weight_text: int | None = None
        self._status_text: int | None = None
        self._plot_id: int | None = None
        self._x_axis: int | None = None
        self._y_axis: int | None = None
        self._line_series: int | None = None
        self._threshold_series: int | None = None

        self._build()

    def _build(self) -> None:
        palette = Theme.palette
        with dpg.group(parent=self._parent) as self._group_id:
            # Header row
            with dpg.group(horizontal=True):
                dpg.add_text("Current weight:", color=hex_to_rgba(palette.text_primary))
                self._weight_text = dpg.add_text(
                    "-- g", color=hex_to_rgba(palette.accent_primary),
                )
                dpg.add_spacer(width=20)
                self._status_text = dpg.add_text(
                    "", color=hex_to_rgba(palette.text_secondary),
                )

            # Plot
            with dpg.plot(label="Scales", height=-1, width=-1) as self._plot_id:
                dpg.add_plot_legend()
                self._x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)")
                self._y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Weight (g)")
                dpg.set_axis_limits(self._y_axis, self.DEFAULT_Y_MIN, self.DEFAULT_Y_MAX)

                self._line_series = dpg.add_line_series(
                    [], [], parent=self._y_axis, label="Weight",
                )
                self._threshold_series = dpg.add_inf_line_series(
                    [], parent=self._y_axis, label="Threshold",
                    horizontal=True,
                )

    def set_scales_client(self, client: Optional[ScalesClientProtocol]) -> None:
        self._scales_client = client

    def set_threshold(self, value: Optional[float]) -> None:
        self._threshold_value = value
        if value is not None and self._threshold_series is not None:
            dpg.set_value(self._threshold_series, [[value]])
        elif self._threshold_series is not None:
            dpg.set_value(self._threshold_series, [[]])

    def set_battery_detection(self, enabled: bool) -> None:
        self._battery_detection_enabled = enabled

    def start(self) -> None:
        if self._is_active:
            return
        self._is_active = True
        self._data.clear()
        if self._status_text:
            dpg.set_value(self._status_text, "Live")
        frame_poller.register(self.POLL_INTERVAL_MS, self._poll)

    def stop(self) -> None:
        self._is_active = False
        frame_poller.unregister(self._poll)
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.set_value(self._status_text, "Stopped")

    def _poll(self) -> None:
        if not self._is_active:
            return

        now = time.monotonic()

        if self._scales_client is not None:
            try:
                weight = self._scales_client.get_weight()
            except Exception:
                weight = None

            if weight is not None:
                self._data.append((now, weight))
                if self._weight_text and dpg.does_item_exist(self._weight_text):
                    dpg.set_value(self._weight_text, f"{weight:.2f} g")

                # Battery detection
                if self._battery_detection_enabled and self._last_weight is not None:
                    if abs(weight - self._last_weight) > self._static_jitter_tolerance:
                        self._last_varied_time = now
                        self._static_alert_shown = False
                elif self._battery_detection_enabled:
                    self._last_varied_time = now
                self._last_weight = weight

                if (self._battery_detection_enabled
                        and now - self._last_varied_time > self._static_threshold_seconds
                        and not self._static_alert_shown):
                    self._static_alert_shown = True
                    self._show_battery_warning()
            else:
                if self._weight_text and dpg.does_item_exist(self._weight_text):
                    dpg.set_value(self._weight_text, "-- g")

        # Prune old data
        cutoff = now - self.WINDOW_SECONDS - 1.0
        while self._data and self._data[0][0] < cutoff:
            self._data.popleft()

        self._update_plot(now)

    def _update_plot(self, now: float) -> None:
        if not self._data:
            return

        # Build series data (time relative to now)
        times = []
        weights = []
        for t, w in self._data:
            age = now - t
            if age <= self.WINDOW_SECONDS:
                times.append(-age)
                weights.append(w)

        if self._line_series and dpg.does_item_exist(self._line_series):
            dpg.set_value(self._line_series, [times, weights])

        if self._x_axis and dpg.does_item_exist(self._x_axis):
            dpg.set_axis_limits(self._x_axis, -self.WINDOW_SECONDS, 0)

        # Auto-scale Y if data exceeds defaults
        if weights:
            data_min = min(weights)
            data_max = max(weights)
            y_min = min(self.DEFAULT_Y_MIN, data_min - 1)
            y_max = max(self.DEFAULT_Y_MAX, data_max + 1)
            if self._y_axis and dpg.does_item_exist(self._y_axis):
                dpg.set_axis_limits(self._y_axis, y_min, y_max)

    def _show_battery_warning(self) -> None:
        """Show a non-blocking warning popup about possible battery issue."""
        from .dpg_dialogs import show_warning
        show_warning(
            "Scales Warning",
            f"Scales may be out of battery!\n"
            f"No weight variation detected for "
            f"{self._static_threshold_seconds:.0f}+ seconds.",
        )
