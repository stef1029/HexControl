"""
Post-Session Mode - Review completed session (DearPyGui).

Shows:
    - Session summary (status, protocol, mouse, duration, save path)
    - Per-tracker performance report with stats and plots
    - Close Window / New Session button
"""

import os
import subprocess
import sys
from typing import Callable

import dearpygui.dearpygui as dpg

from hexcontrol.gui.theme import Theme, hex_to_rgba
from hexcontrol.gui.tracker_report_widget import TrackerReportWidget


class PostSessionMode:
    """Post-session mode — shows session summary and action buttons."""

    def __init__(
        self,
        parent: int | str,
        on_new_session: Callable[[], None],
        on_close_window: Callable[[], None] | None = None,
    ):
        self._parent = parent
        self._on_new_session = on_new_session
        self._on_close_window = on_close_window
        self._save_path: str = ""

        # DPG IDs
        self._window_id: int | None = None
        self._header_text: int | None = None
        self._summary_labels: dict[str, int] = {}
        self._perf_container: int | None = None

        self._build()

    def _build(self) -> None:
        palette = Theme.palette
        self._window_id = dpg.add_group(parent=self._parent, show=False)
        root = self._window_id

        # Header
        self._header_text = dpg.add_text(
            "Session Complete", parent=root,
            color=hex_to_rgba(palette.text_primary),
        )
        if Theme.font_title():
            dpg.bind_item_font(self._header_text, Theme.font_title())

        dpg.add_spacer(height=8, parent=root)

        # Summary
        with dpg.collapsing_header(label="Session Summary", default_open=True, parent=root):
            for key, label_text in [
                ("status", "Status:"),
                ("protocol", "Protocol:"),
                ("mouse", "Mouse:"),
                ("duration", "Duration:"),
                ("save_path", "Data saved to:"),
            ]:
                with dpg.group(horizontal=True):
                    dpg.add_text(label_text, color=hex_to_rgba(palette.text_secondary))
                    self._summary_labels[key] = dpg.add_text("")

        # Performance Report
        with dpg.collapsing_header(label="Performance Report", default_open=True, parent=root):
            self._perf_container = dpg.add_group()

        # Buttons
        dpg.add_spacer(height=8, parent=root)
        with dpg.group(horizontal=True, parent=root):
            close_btn = dpg.add_button(
                label="Close Window",
                callback=lambda: self._on_close_click(),
            )
            if Theme.primary_button_theme:
                dpg.bind_item_theme(close_btn, Theme.primary_button_theme)

            new_btn = dpg.add_button(
                label="New Session",
                callback=lambda: self._on_new_session_click(),
            )
            if Theme.secondary_button_theme:
                dpg.bind_item_theme(new_btn, Theme.secondary_button_theme)

            dpg.add_text(
                "  (New Session keeps the same session folder)",
                color=hex_to_rgba(palette.text_secondary),
            )

    def activate(self, session_result: dict) -> None:
        """Called when this mode becomes active."""
        palette = Theme.palette

        # Format duration
        elapsed = session_result.get("elapsed_time", 0)
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        self._save_path = session_result.get("save_path", "")

        # Set summary values
        status = session_result.get("status", "Unknown")
        _set(self._summary_labels.get("status"), str(status))
        _set(self._summary_labels.get("protocol"), session_result.get("protocol_name", ""))
        _set(self._summary_labels.get("mouse"), session_result.get("mouse_id", ""))
        _set(self._summary_labels.get("duration"), duration_str)
        _set(self._summary_labels.get("save_path"), session_result.get("save_path", ""))

        # Color-code status
        status_colors = {
            "Completed": palette.success,
            "Stopped": palette.warning,
            "Error": palette.error,
        }
        color = status_colors.get(str(status), palette.text_primary)
        status_id = self._summary_labels.get("status")
        if status_id and dpg.does_item_exist(status_id):
            dpg.configure_item(status_id, color=hex_to_rgba(color))

        # Build tracker report
        self._update_performance_reports(session_result.get("performance_reports"))

    def _update_performance_reports(self, reports) -> None:
        if self._perf_container and dpg.does_item_exist(self._perf_container):
            for child in dpg.get_item_children(self._perf_container, 1) or []:
                dpg.delete_item(child)
            TrackerReportWidget(self._perf_container, reports or {})

    def _on_close_click(self) -> None:
        if self._on_close_window:
            self._on_close_window()

    def _on_new_session_click(self) -> None:
        if self._on_new_session:
            self._on_new_session()

    # ----- Show / hide -----

    def show(self) -> None:
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=True)

    def hide(self) -> None:
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=False)


def _set(item_id: int | None, text: str) -> None:
    if item_id is not None and dpg.does_item_exist(item_id):
        dpg.set_value(item_id, text)
