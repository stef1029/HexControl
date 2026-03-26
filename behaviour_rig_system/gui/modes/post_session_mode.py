"""
Post-Session Mode - Review completed session.

Shows:
    - Session summary (status, protocol, mouse, duration, save path)
    - Per-tracker performance report with stats and plots
    - Close Window / New Session button
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from gui.theme import Theme
from gui.tracker_report_widget import TrackerReportWidget


class PostSessionMode(ttk.Frame):
    """
    Post-session mode - shows session summary and new session button.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_new_session: Callable[[], None],
        on_close_window: Callable[[], None] | None = None,
    ):
        """
        Args:
            parent: Parent widget
            on_new_session: Callback when Ctrl+click (new session in same folder)
            on_close_window: Callback when normal click (close window)
        """
        super().__init__(parent)
        self._on_new_session = on_new_session
        self._on_close_window = on_close_window

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create the post-session UI widgets."""
        palette = Theme.palette

        # Session complete header
        self._header = ttk.Label(
            self, text="Session Complete",
            style="Title.TLabel"
        )
        self._header.pack(pady=14)

        # Session summary
        summary_frame = ttk.LabelFrame(self, text="Session Summary", padding=(14, 10))
        summary_frame.pack(fill="x", padx=18, pady=8)

        self._summary_labels = {}
        summary_items = [
            ("status", "Status:"),
            ("protocol", "Protocol:"),
            ("mouse", "Mouse:"),
            ("duration", "Duration:"),
            ("save_path", "Data saved to:"),
        ]

        for key, label_text in summary_items:
            row = ttk.Frame(summary_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(
                row, text=label_text,
                style="Subheading.TLabel", width=16, anchor="e"
            ).pack(side="left")
            value_label = ttk.Label(
                row, text="",
                foreground=palette.text_secondary,
                font=Theme.font_body()
            )
            value_label.pack(side="left", padx=8)
            self._summary_labels[key] = value_label

        # Performance Report Section (populated dynamically in activate())
        self._perf_frame = ttk.LabelFrame(self, text="Performance Report", padding=(14, 10))
        self._perf_frame.pack(fill="both", expand=True, padx=18, pady=8)

        # Close / New Session button (packed at bottom so it's always visible)
        button_frame = ttk.Frame(self)
        button_frame.pack(side="bottom", fill="x", padx=18, pady=14)

        hint = ttk.Label(
            button_frame,
            text="Ctrl+click for new session (same session folder)",
            style="Muted.TLabel"
        )
        hint.pack(side="right", padx=10)

        self._new_session_button = ttk.Button(
            button_frame, text="Close Window",
            style="Primary.TButton"
        )
        self._new_session_button.pack(side="right", padx=5)
        self._new_session_button.bind("<Button-1>", self._on_button_click)

    def activate(self, session_result: dict) -> None:
        """
        Called when this mode becomes active.

        Args:
            session_result: Dict with status, protocol_name, mouse_id,
                          elapsed_time, save_path, and performance_reports
        """
        # Format duration
        elapsed = session_result.get("elapsed_time", 0)
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Set summary values
        status = session_result.get("status", "Unknown")
        self._summary_labels["status"].config(text=status)
        self._summary_labels["protocol"].config(text=session_result.get("protocol_name", ""))
        self._summary_labels["mouse"].config(text=session_result.get("mouse_id", ""))
        self._summary_labels["duration"].config(text=duration_str)
        self._summary_labels["save_path"].config(text=session_result.get("save_path", ""))

        # Color-code status
        palette = Theme.palette
        status_colors = {
            "Completed": palette.success,
            "Stopped": palette.warning,
            "Error": palette.error,
        }
        color = status_colors.get(status, "black")
        self._summary_labels["status"].config(foreground=color)

        # Build tracker report widget
        self._update_performance_reports(session_result.get("performance_reports"))

    def _update_performance_reports(self, reports: dict[str, dict] | None) -> None:
        """Replace the performance section with a TrackerReportWidget."""
        for child in self._perf_frame.winfo_children():
            child.destroy()

        widget = TrackerReportWidget(self._perf_frame, reports or {})
        widget.pack(fill="both", expand=True)

    def _on_button_click(self, event: tk.Event) -> None:
        """Handle button click: Ctrl+click = new session, normal click = close window."""
        if event.state & 0x4:  # Ctrl key held
            if self._on_new_session:
                self._on_new_session()
        else:
            if self._on_close_window:
                self._on_close_window()
