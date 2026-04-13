"""
Startup Overlay — loading screen shown during session initialization.

Displays a progress indicator, status label, scrolled log, and cancel
button while the background thread connects to hardware peripherals.

DearPyGui implementation — uses a modal window with show/hide.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

import dearpygui.dearpygui as dpg

from .dpg_app import frame_poller
from .theme import Theme, hex_to_rgba


class StartupOverlay:
    """
    Overlay shown during the startup sequence.

    Provides a progress indicator, live status label, timestamped log,
    and a cancel button.
    """

    def __init__(self, parent: int | str, on_cancel: Callable[[], None]) -> None:
        self._parent = parent
        self._on_cancel = on_cancel
        self._window_id: int | None = None
        self._status_text: int | None = None
        self._progress_bar: int | None = None
        self._log_container: int | None = None
        self._action_btn: int | None = None
        self._title_text: int | None = None
        self._progress_value: float = 0.0
        self._animating: bool = False
        self._build()

    def _build(self) -> None:
        palette = Theme.palette

        self._window_id = dpg.add_window(
            label="Starting Session",
            modal=True, no_resize=True, no_collapse=True, no_close=True,
            width=560, height=420, show=False, pos=[40, 80],
        )

        with dpg.group(parent=self._window_id):
            dpg.add_spacer(height=6)
            self._title_text = dpg.add_text(
                "Starting Session...",
                color=hex_to_rgba(palette.text_primary),
            )
            if Theme.font_heading():
                dpg.bind_item_font(self._title_text, Theme.font_heading())

            self._status_text = dpg.add_text(
                "Initializing...",
                color=hex_to_rgba(palette.accent_primary),
            )

            dpg.add_spacer(height=6)
            self._progress_bar = dpg.add_progress_bar(
                default_value=0.0, width=-1,
            )

            dpg.add_spacer(height=6)
            dpg.add_text("Startup Log:",
                         color=hex_to_rgba(palette.text_secondary))

            self._log_container = dpg.add_child_window(
                height=220, horizontal_scrollbar=True,
            )

            dpg.add_spacer(height=8)
            self._action_btn = dpg.add_button(
                label="Cancel", callback=lambda: self._on_cancel(),
                width=100,
            )
            if Theme.danger_button_theme:
                dpg.bind_item_theme(self._action_btn, Theme.danger_button_theme)

    def _animate_progress(self) -> None:
        """Cycle the progress bar for indeterminate mode."""
        if not self._animating:
            return
        self._progress_value = (self._progress_value + 0.02) % 1.0
        if self._progress_bar and dpg.does_item_exist(self._progress_bar):
            dpg.set_value(self._progress_bar, self._progress_value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Reset state and show the overlay."""
        # Clear log
        if self._log_container and dpg.does_item_exist(self._log_container):
            for child in dpg.get_item_children(self._log_container, 1) or []:
                dpg.delete_item(child)

        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.set_value(self._status_text, "Initializing...")
        if self._title_text and dpg.does_item_exist(self._title_text):
            dpg.set_value(self._title_text, "Starting Session...")
            dpg.configure_item(self._title_text, color=hex_to_rgba(Theme.palette.text_primary))
        if self._action_btn and dpg.does_item_exist(self._action_btn):
            dpg.configure_item(self._action_btn, label="Cancel")
            dpg.set_item_callback(self._action_btn, lambda: self._on_cancel())

        self._animating = True
        frame_poller.register(33, self._animate_progress)

        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=True)

    def hide(self) -> None:
        """Stop progress and hide the overlay."""
        self._animating = False
        frame_poller.unregister(self._animate_progress)
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=False)

    def update_status(self, message: str) -> None:
        """Update the status label and append a timestamped line to the log."""
        short = message.split("]", 1)[-1].strip() if "]" in message else message
        display = short[:60] + "..." if len(short) > 60 else short
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.set_value(self._status_text, display)

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if self._log_container and dpg.does_item_exist(self._log_container):
            dpg.add_text(
                f"[{timestamp}] {message}",
                parent=self._log_container,
                color=hex_to_rgba(Theme.palette.text_primary),
            )
            # Auto-scroll
            dpg.set_y_scroll(self._log_container,
                             dpg.get_y_scroll_max(self._log_container))

    def show_error(self, error_msg: str, on_close: Callable[[], None]) -> None:
        """Switch the overlay to error state with a Close button."""
        self._animating = False
        frame_poller.unregister(self._animate_progress)

        palette = Theme.palette
        if self._title_text and dpg.does_item_exist(self._title_text):
            dpg.set_value(self._title_text, "Startup Failed")
            dpg.configure_item(self._title_text, color=hex_to_rgba(palette.error))
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.set_value(self._status_text, error_msg[:80])
        self.update_status(f"ERROR: {error_msg}")
        if self._action_btn and dpg.does_item_exist(self._action_btn):
            dpg.configure_item(self._action_btn, label="Close")
            dpg.set_item_callback(self._action_btn, lambda: on_close())
