"""
Post-Session Mode - Review completed session.

Shows:
    - Session summary (status, protocol, mouse, duration, save path)
    - New Session button to return to setup
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class PostSessionMode(ttk.Frame):
    """
    Post-session mode - shows session summary and new session button.
    """
    
    def __init__(self, parent: tk.Widget, on_new_session: Callable[[], None]):
        """
        Args:
            parent: Parent widget
            on_new_session: Callback when new session is clicked
        """
        super().__init__(parent)
        self._on_new_session = on_new_session
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the post-session UI widgets."""
        # Session complete header
        self._header = ttk.Label(
            self, text="Session Complete",
            font=("Helvetica", 18, "bold")
        )
        self._header.pack(pady=20)
        
        # Session summary
        summary_frame = ttk.LabelFrame(self, text="Session Summary", padding=(15, 10))
        summary_frame.pack(fill="x", padx=20, pady=10)
        
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
            row.pack(fill="x", pady=3)
            ttk.Label(
                row, text=label_text,
                font=("TkDefaultFont", 10, "bold"), width=15, anchor="e"
            ).pack(side="left")
            value_label = ttk.Label(row, text="", font=("TkDefaultFont", 10))
            value_label.pack(side="left", padx=10)
            self._summary_labels[key] = value_label
        
        # Performance Report Section
        self._perf_frame = ttk.LabelFrame(self, text="Performance Report", padding=(15, 10))
        self._perf_frame.pack(fill="x", padx=20, pady=10)
        
        # Create two-column grid layout for performance stats
        perf_container = ttk.Frame(self._perf_frame)
        perf_container.pack(fill="x")
        
        # Configure grid columns to expand properly
        perf_container.columnconfigure(0, weight=0)  # Left label
        perf_container.columnconfigure(1, weight=1)  # Left value
        perf_container.columnconfigure(2, weight=0, minsize=20)  # Spacer
        perf_container.columnconfigure(3, weight=0)  # Right label
        perf_container.columnconfigure(4, weight=1)  # Right value
        
        self._perf_labels = {}
        
        # Left column: Trial counts
        left_items = [
            ("total_trials", "Total Trials:"),
            ("successes", "Successes:"),
            ("failures", "Failures:"),
            ("timeouts", "Timeouts:"),
        ]
        
        # Right column: Accuracy stats
        right_items = [
            ("accuracy", "Success (excl. TO):"),
            ("accuracy_with_to", "Success (incl. TO):"),
            ("timeout_rate", "Timeout Rate:"),
        ]
        
        # Create rows with left and right items
        max_rows = max(len(left_items), len(right_items))
        for row_idx in range(max_rows):
            # Left side
            if row_idx < len(left_items):
                key, label_text = left_items[row_idx]
                ttk.Label(
                    perf_container, text=label_text,
                    font=("TkDefaultFont", 10, "bold"), anchor="e"
                ).grid(row=row_idx, column=0, sticky="e", pady=2)
                value_label = ttk.Label(perf_container, text="-", font=("TkDefaultFont", 10))
                value_label.grid(row=row_idx, column=1, sticky="w", padx=(5, 0), pady=2)
                self._perf_labels[key] = value_label
            
            # Right side
            if row_idx < len(right_items):
                key, label_text = right_items[row_idx]
                ttk.Label(
                    perf_container, text=label_text,
                    font=("TkDefaultFont", 10, "bold"), anchor="e"
                ).grid(row=row_idx, column=3, sticky="e", pady=2)
                value_label = ttk.Label(perf_container, text="-", font=("TkDefaultFont", 10))
                value_label.grid(row=row_idx, column=4, sticky="w", padx=(5, 0), pady=2)
                self._perf_labels[key] = value_label
        
        # Additional stats row
        extra_row = ttk.Frame(self._perf_frame)
        extra_row.pack(fill="x", pady=(10, 0))
        extra_row.columnconfigure(1, weight=1)
        extra_row.columnconfigure(4, weight=1)
        
        ttk.Label(
            extra_row, text="Trial Rate:",
            font=("TkDefaultFont", 10, "bold"), anchor="e"
        ).grid(row=0, column=0, sticky="e")
        self._perf_labels["trial_rate"] = ttk.Label(extra_row, text="-", font=("TkDefaultFont", 10))
        self._perf_labels["trial_rate"].grid(row=0, column=1, sticky="w", padx=(5, 0))
        
        ttk.Label(
            extra_row, text="Last 20 Accuracy:",
            font=("TkDefaultFont", 10, "bold"), anchor="e"
        ).grid(row=0, column=3, sticky="e", padx=(20, 0))
        self._perf_labels["rolling_20"] = ttk.Label(extra_row, text="-", font=("TkDefaultFont", 10))
        self._perf_labels["rolling_20"].grid(row=0, column=4, sticky="w", padx=(5, 0))
        
        # No trials message (hidden by default)
        self._no_trials_label = ttk.Label(
            self._perf_frame, 
            text="No trials were recorded during this session.",
            font=("TkDefaultFont", 10, "italic"),
            foreground="gray"
        )
        
        # Spacer
        ttk.Frame(self).pack(fill="both", expand=True)
        
        # New session button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        self._new_session_button = ttk.Button(
            button_frame, text="New Session",
            command=self._on_new_session_clicked
        )
        self._new_session_button.pack(side="right", padx=5)
    
    def activate(self, session_result: dict) -> None:
        """
        Called when this mode becomes active.
        
        Args:
            session_result: Dict with status, protocol_name, mouse_id, 
                          elapsed_time, save_path, and optionally performance_report
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
        status_colors = {
            "Completed": "darkgreen",
            "Stopped": "darkorange",
            "Error": "red",
        }
        color = status_colors.get(status, "black")
        self._summary_labels["status"].config(foreground=color)
        
        # Update performance report
        self._update_performance_report(session_result.get("performance_report"))
    
    def _update_performance_report(self, report: dict | None) -> None:
        """
        Update the performance report section with session statistics.
        
        Args:
            report: Performance report dict from PerformanceTracker.get_report(),
                   or None if no trials were recorded
        """
        # Hide/show the no trials message based on whether we have data
        if report is None or report.get("total_trials", 0) == 0:
            # No trials - show message, hide stats
            self._no_trials_label.pack(pady=10)
            for label in self._perf_labels.values():
                label.config(text="-")
            return
        
        # Hide no trials message
        self._no_trials_label.pack_forget()
        
        # Update trial counts
        self._perf_labels["total_trials"].config(text=str(report.get("total_trials", 0)))
        self._perf_labels["successes"].config(
            text=str(report.get("successes", 0)),
            foreground="darkgreen"
        )
        self._perf_labels["failures"].config(
            text=str(report.get("failures", 0)),
            foreground="darkred"
        )
        self._perf_labels["timeouts"].config(
            text=str(report.get("timeouts", 0)),
            foreground="darkorange"
        )
        
        # Update accuracy stats
        accuracy = report.get("accuracy", 0)
        self._perf_labels["accuracy"].config(
            text=f"{accuracy:.1f}%",
            foreground="black"
        )
        
        accuracy_with_to = report.get("accuracy_with_timeouts", 0)
        self._perf_labels["accuracy_with_to"].config(
            text=f"{accuracy_with_to:.1f}%",
            foreground="black"
        )
        
        timeout_rate = report.get("timeout_rate", 0)
        self._perf_labels["timeout_rate"].config(
            text=f"{timeout_rate:.1f}%",
            foreground="darkorange" if timeout_rate > 20 else "black"
        )
        
        # Update trial rate
        trials_per_min = report.get("trials_per_minute", 0)
        self._perf_labels["trial_rate"].config(
            text=f"{trials_per_min:.1f} trials/min" if trials_per_min > 0 else "-"
        )
        
        # Update rolling accuracy
        rolling_20 = report.get("rolling_accuracy_20", 0)
        self._perf_labels["rolling_20"].config(
            text=f"{rolling_20:.1f}%",
            foreground=self._get_accuracy_color(rolling_20)
        )
    
    def _get_accuracy_color(self, accuracy: float) -> str:
        """Get color for accuracy value (green=good, orange=ok, red=poor)."""
        if accuracy >= 70:
            return "darkgreen"
        elif accuracy >= 50:
            return "darkorange"
        else:
            return "darkred"
    
    def _on_new_session_clicked(self) -> None:
        """Handle new session button click."""
        if self._on_new_session:
            self._on_new_session()
