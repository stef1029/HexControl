"""
Running Mode - Monitor an active session.

Shows:
    - Session summary (protocol, mouse, save path)
    - Performance stats (accuracy, rolling accuracy)
    - Elapsed timer
    - Status indicator
    - Event log
    - Stop button
"""

import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk
from typing import Callable, TYPE_CHECKING

from core.protocol_base import ProtocolEvent, ProtocolStatus

if TYPE_CHECKING:
    from core.performance_tracker import PerformanceTracker


class RunningMode(ttk.Frame):
    """
    Running mode - shows session progress, logging, and stop button.
    """
    
    def __init__(self, parent: tk.Widget, on_stop: Callable[[], None]):
        """
        Args:
            parent: Parent widget
            on_stop: Callback when stop is clicked
        """
        super().__init__(parent)
        self._on_stop = on_stop
        self._start_time: datetime | None = None
        self._timer_id: str | None = None
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the running UI widgets."""
        # Session summary at top
        summary_frame = ttk.LabelFrame(self, text="Session", padding=(10, 5))
        summary_frame.pack(fill="x", padx=10, pady=5)
        
        self._summary_labels = {}
        for key, label_text in [("protocol", "Protocol:"), ("mouse", "Mouse:"), ("save_path", "Saving to:")]:
            row = ttk.Frame(summary_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label_text, font=("TkDefaultFont", 9, "bold")).pack(side="left")
            value_label = ttk.Label(row, text="", font=("TkDefaultFont", 9))
            value_label.pack(side="left", padx=5)
            self._summary_labels[key] = value_label
        
        # Performance stats frame
        perf_frame = ttk.LabelFrame(self, text="Performance", padding=(10, 5))
        perf_frame.pack(fill="x", padx=10, pady=5)
        
        # Main stats row
        stats_row = ttk.Frame(perf_frame)
        stats_row.pack(fill="x", pady=2)
        
        # Trials counter
        ttk.Label(stats_row, text="Trials:", font=("TkDefaultFont", 9, "bold")).pack(side="left")
        self._trials_label = ttk.Label(stats_row, text="0", font=("Consolas", 11))
        self._trials_label.pack(side="left", padx=(5, 15))
        
        # Overall accuracy
        ttk.Label(stats_row, text="Accuracy:", font=("TkDefaultFont", 9, "bold")).pack(side="left")
        self._accuracy_label = ttk.Label(stats_row, text="--", font=("Consolas", 11, "bold"), foreground="blue")
        self._accuracy_label.pack(side="left", padx=(5, 15))
        
        # Rolling accuracy (last 20)
        ttk.Label(stats_row, text="Last 20:", font=("TkDefaultFont", 9, "bold")).pack(side="left")
        self._rolling_label = ttk.Label(stats_row, text="--", font=("Consolas", 11), foreground="darkblue")
        self._rolling_label.pack(side="left", padx=(5, 15))
        
        # Breakdown row
        breakdown_row = ttk.Frame(perf_frame)
        breakdown_row.pack(fill="x", pady=2)
        
        ttk.Label(breakdown_row, text="Correct:", font=("TkDefaultFont", 9)).pack(side="left")
        self._correct_label = ttk.Label(breakdown_row, text="0", font=("Consolas", 10), foreground="green")
        self._correct_label.pack(side="left", padx=(5, 15))
        
        ttk.Label(breakdown_row, text="Incorrect:", font=("TkDefaultFont", 9)).pack(side="left")
        self._incorrect_label = ttk.Label(breakdown_row, text="0", font=("Consolas", 10), foreground="red")
        self._incorrect_label.pack(side="left", padx=(5, 15))
        
        ttk.Label(breakdown_row, text="Timeouts:", font=("TkDefaultFont", 9)).pack(side="left")
        self._timeout_label = ttk.Label(breakdown_row, text="0", font=("Consolas", 10), foreground="gray")
        self._timeout_label.pack(side="left", padx=(5, 15))
        
        # Timer and status row
        timer_frame = ttk.Frame(self)
        timer_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(timer_frame, text="Elapsed:", font=("TkDefaultFont", 10, "bold")).pack(side="left")
        self._timer_label = ttk.Label(
            timer_frame, text="00:00:00",
            font=("Consolas", 24, "bold"), foreground="green"
        )
        self._timer_label.pack(side="left", padx=10)
        
        self._status_label = ttk.Label(
            timer_frame, text="RUNNING",
            font=("TkDefaultFont", 12, "bold"), foreground="green"
        )
        self._status_label.pack(side="right", padx=10)
        
        # Event log
        log_frame = ttk.LabelFrame(self, text="Session Log", padding=(5, 5))
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self._log_text = scrolledtext.ScrolledText(
            log_frame, height=15, font=("Consolas", 9), state="disabled"
        )
        self._log_text.pack(fill="both", expand=True)
        
        # Stop button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        self._stop_button = ttk.Button(
            button_frame, text="Stop Session",
            command=self._on_stop_clicked
        )
        self._stop_button.pack(side="right", padx=5)
    
    def activate(self, session_config: dict) -> None:
        """
        Called when this mode becomes active.
        
        Args:
            session_config: Dict with protocol_name, mouse_id, save_path
        """
        # Reset UI state
        self._clear_log()
        self._stop_button.config(state="normal", text="Stop Session")
        
        # Set session info
        self._summary_labels["protocol"].config(text=session_config.get("protocol_name", ""))
        self._summary_labels["mouse"].config(text=session_config.get("mouse_id", ""))
        self._summary_labels["save_path"].config(text=session_config.get("save_path", ""))
        
        # Reset performance stats
        self._reset_performance_display()
        
        # Reset timer state
        self._start_time = None
        self._timer_label.config(text="00:00:00")
    
    def _reset_performance_display(self) -> None:
        """Reset all performance stats to initial state."""
        self._trials_label.config(text="0")
        self._accuracy_label.config(text="--")
        self._rolling_label.config(text="--")
        self._correct_label.config(text="0")
        self._incorrect_label.config(text="0")
        self._timeout_label.config(text="0")
    
    def update_performance(self, tracker: "PerformanceTracker") -> None:
        """
        Update the performance display from a tracker.
        
        Called by the tracker's on_update callback.
        Thread-safe: schedules update on main thread.
        
        Args:
            tracker: The PerformanceTracker instance with current stats.
        """
        # Schedule update on main thread (called from protocol thread)
        self.after(0, lambda: self._update_performance_display(tracker))
    
    def _update_performance_display(self, tracker: "PerformanceTracker") -> None:
        """Actually update the performance display (must be called on main thread)."""
        self._trials_label.config(text=str(tracker.total_trials))
        self._correct_label.config(text=str(tracker.successes))
        self._incorrect_label.config(text=str(tracker.failures))
        self._timeout_label.config(text=str(tracker.timeouts))
        
        # Overall accuracy
        if tracker.responses > 0:
            acc = tracker.accuracy
            self._accuracy_label.config(text=f"{acc:.0f}%")
            # Color based on performance
            if acc >= 70:
                self._accuracy_label.config(foreground="green")
            elif acc >= 50:
                self._accuracy_label.config(foreground="orange")
            else:
                self._accuracy_label.config(foreground="red")
        else:
            self._accuracy_label.config(text="--", foreground="blue")
        
        # Rolling accuracy (last 20)
        if tracker.total_trials > 0:
            rolling = tracker.rolling_accuracy(20)
            self._rolling_label.config(text=f"{rolling:.0f}%")
        else:
            self._rolling_label.config(text="--")
    
    def deactivate(self) -> dict:
        """
        Called when leaving this mode.
        
        Returns:
            Context dict with elapsed_time and final log
        """
        self._stop_timer()
        
        return {
            "elapsed_time": self.get_elapsed_time(),
        }
    
    def _update_timer(self) -> None:
        """Update the timer display."""
        if self._start_time:
            elapsed = datetime.now() - self._start_time
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            self._timer_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            self._timer_id = self.after(1000, self._update_timer)
    
    def _stop_timer(self) -> None:
        """Stop the elapsed time timer."""
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
    
    def start_timer(self) -> None:
        """Start the elapsed time timer (public interface)."""
        self._start_time = datetime.now()
        self._update_timer()
    
    def stop_timer(self) -> None:
        """Stop the elapsed time timer (public interface)."""
        self._stop_timer()
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if self._start_time:
            return (datetime.now() - self._start_time).total_seconds()
        return 0.0
    
    def log_message(self, message: str) -> None:
        """Add a message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        self._log_text.config(state="normal")
        self._log_text.insert(tk.END, log_line)
        self._log_text.see(tk.END)
        self._log_text.config(state="disabled")
    
    def log_event(self, event: ProtocolEvent) -> None:
        """Log a protocol event."""
        message = event.data.get("message", event.event_type)
        self.log_message(message)
    
    def set_status(self, status: ProtocolStatus) -> None:
        """Update the status display (public interface)."""
        self._set_status(status)
    
    def _set_status(self, status: ProtocolStatus) -> None:
        """Update the status display."""
        status_config = {
            ProtocolStatus.IDLE: ("IDLE", "gray"),
            ProtocolStatus.RUNNING: ("RUNNING", "green"),
            ProtocolStatus.COMPLETED: ("COMPLETED", "darkgreen"),
            ProtocolStatus.ABORTED: ("ABORTED", "darkorange"),
            ProtocolStatus.ERROR: ("ERROR", "red"),
        }
        text, color = status_config.get(status, ("UNKNOWN", "black"))
        self._status_label.config(text=text, foreground=color)
        self._timer_label.config(foreground=color)
    
    def set_stopping(self) -> None:
        """Update UI to show stopping state."""
        self._stop_button.config(state="disabled", text="Stopping...")
        self._status_label.config(text="STOPPING", foreground="orange")
    
    def _clear_log(self) -> None:
        """Clear the log."""
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state="disabled")
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self._on_stop:
            self._on_stop()
