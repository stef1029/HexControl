"""
Running Mode - Monitor an active session.

Shows:
    - Session summary (protocol, mouse, save path)
    - Performance stats (accuracy, rolling accuracy)
    - Elapsed timer
    - Status indicator
    - Trial log (resizable pane)
    - Live scales plot (resizable pane)
    - Session event log (resizable pane)
    - Stop button
"""

import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk
from typing import Callable, TYPE_CHECKING

from core.protocol_base import ProtocolStatus
from gui.theme import Theme, style_scrolled_text, get_accuracy_color
from gui.scales_plot_widget import ScalesPlotWidget

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
        self._last_logged_trial: int = 0
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the running UI widgets."""
        palette = Theme.palette
        
        # Session summary at top
        summary_frame = ttk.LabelFrame(self, text="Session", padding=(10, 6))
        summary_frame.pack(fill="x", padx=10, pady=6)
        
        self._summary_labels = {}
        for key, label_text in [("protocol", "Protocol:"), ("mouse", "Mouse:"), ("save_path", "Saving to:")]:
            row = ttk.Frame(summary_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label_text, style="Subheading.TLabel").pack(side="left")
            value_label = ttk.Label(row, text="", foreground=palette.text_secondary)
            value_label.pack(side="left", padx=6)
            self._summary_labels[key] = value_label
        
        # Performance stats (non-resizable)
        perf_frame = ttk.LabelFrame(self, text="Performance", padding=(10, 6))
        perf_frame.pack(fill="x", padx=10, pady=5)
        
        # Main stats row
        stats_row = ttk.Frame(perf_frame)
        stats_row.pack(fill="x", pady=3)
        
        # Trials counter
        ttk.Label(stats_row, text="Trials:", style="Subheading.TLabel").pack(side="left")
        self._trials_label = ttk.Label(
            stats_row, text="0", 
            font=Theme.font_mono(size=12),
            foreground=palette.accent_primary
        )
        self._trials_label.pack(side="left", padx=(6, 16))
        
        # Overall accuracy
        ttk.Label(stats_row, text="Accuracy:", style="Subheading.TLabel").pack(side="left")
        self._accuracy_label = ttk.Label(
            stats_row, text="--", 
            font=Theme.font_mono(size=12, weight="bold"),
            foreground=palette.info
        )
        self._accuracy_label.pack(side="left", padx=(6, 16))
        
        # Rolling accuracy with selectable window
        ttk.Label(stats_row, text="Last", style="Subheading.TLabel").pack(side="left")
        self._rolling_n_var = tk.StringVar(value="20")
        self._rolling_n_combo = ttk.Combobox(
            stats_row, 
            textvariable=self._rolling_n_var,
            values=["5", "10", "20", "50", "100"],
            width=4,
            state="readonly"
        )
        self._rolling_n_combo.pack(side="left", padx=(4, 2))
        ttk.Label(stats_row, text=":", style="Subheading.TLabel").pack(side="left")
        self._rolling_label = ttk.Label(
            stats_row, text="--", 
            font=Theme.font_mono(size=12),
            foreground=palette.accent_secondary
        )
        self._rolling_label.pack(side="left", padx=(6, 0))
        
        # Breakdown row
        breakdown_row = ttk.Frame(perf_frame)
        breakdown_row.pack(fill="x", pady=3)
        
        ttk.Label(breakdown_row, text="Correct:").pack(side="left")
        self._correct_label = ttk.Label(
            breakdown_row, text="0", 
            font=Theme.font_mono(size=10),
            foreground=palette.success
        )
        self._correct_label.pack(side="left", padx=(4, 14))
        
        ttk.Label(breakdown_row, text="Incorrect:").pack(side="left")
        self._incorrect_label = ttk.Label(
            breakdown_row, text="0", 
            font=Theme.font_mono(size=10),
            foreground=palette.error
        )
        self._incorrect_label.pack(side="left", padx=(4, 14))
        
        ttk.Label(breakdown_row, text="Timeouts:").pack(side="left")
        self._timeout_label = ttk.Label(
            breakdown_row, text="0", 
            font=Theme.font_mono(size=10),
            foreground=palette.warning
        )
        self._timeout_label.pack(side="left", padx=(4, 0))
        
        # Stop button (packed first so it's always visible at the bottom)
        button_frame = ttk.Frame(self)
        button_frame.pack(side="bottom", fill="x", padx=10, pady=8)
        
        self._stop_button = ttk.Button(
            button_frame, text="Stop Session",
            command=self._on_stop_clicked,
            style="Danger.TButton"
        )
        self._stop_button.pack(side="right", padx=3)
        
        # Timer and status row
        timer_frame = ttk.Frame(self)
        timer_frame.pack(side="bottom", fill="x", padx=10, pady=6)
        
        ttk.Label(timer_frame, text="Elapsed:", style="Subheading.TLabel").pack(side="left")
        self._timer_label = ttk.Label(
            timer_frame, text="00:00:00",
            font=Theme.font_mono(size=22, weight="bold"), 
            foreground=palette.success
        )
        self._timer_label.pack(side="left", padx=10)
        
        self._status_label = ttk.Label(
            timer_frame, text="RUNNING",
            font=Theme.font(size=12, weight="bold"), 
            foreground=palette.success
        )
        self._status_label.pack(side="right", padx=10)
        
        # =====================================================================
        # Resizable paned area: Trial Log | Scales Plot | Session Log
        # =====================================================================
        self._paned = ttk.PanedWindow(self, orient="vertical")
        self._paned.pack(fill="both", expand=True, padx=10, pady=5)
        
        # --- Pane 1: Trial Log ---
        trial_pane = ttk.LabelFrame(self._paned, text="Trial Log", padding=(8, 4))
        self._trial_log = scrolledtext.ScrolledText(
            trial_pane, height=8, state="disabled"
        )
        style_scrolled_text(self._trial_log, log_style=True)
        self._trial_log.pack(fill="both", expand=True)
        
        # Configure tags for trial log coloring
        self._trial_log.tag_config("success", foreground=palette.success)
        self._trial_log.tag_config("failure", foreground=palette.error)
        self._trial_log.tag_config("timeout", foreground=palette.warning)
        self._trial_log.tag_config("stimulus", foreground=palette.info)
        
        self._paned.add(trial_pane, weight=3)
        
        # --- Pane 2: Live Scales Plot ---
        scales_pane = ttk.LabelFrame(self._paned, text="Scales", padding=(8, 4))
        self._scales_plot = ScalesPlotWidget(scales_pane)
        self._scales_plot.pack(fill="both", expand=True)
        
        self._paned.add(scales_pane, weight=2)
        
        # --- Pane 3: Session Log ---
        log_pane = ttk.LabelFrame(self._paned, text="Session Log", padding=(8, 4))
        self._log_text = scrolledtext.ScrolledText(
            log_pane, height=3, state="disabled"
        )
        style_scrolled_text(self._log_text, log_style=True)
        self._log_text.pack(fill="both", expand=True)
        
        self._paned.add(log_pane, weight=1)
    
    def set_scales_client(self, client) -> None:
        """
        Provide a scales client for live weight plotting.
        
        Args:
            client: Object with get_weight() -> Optional[float]
        """
        self._scales_plot.set_scales_client(client)
    
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
        
        # Start the live scales plot
        self._scales_plot.start()
    
    def _reset_performance_display(self) -> None:
        """Reset all performance stats to initial state."""
        self._trials_label.config(text="0")
        self._accuracy_label.config(text="--")
        self._rolling_label.config(text="--")
        self._correct_label.config(text="0")
        self._incorrect_label.config(text="0")
        self._timeout_label.config(text="0")
        self._last_logged_trial = 0
        
        # Clear trial log
        self._trial_log.config(state="normal")
        self._trial_log.delete("1.0", tk.END)
        self._trial_log.config(state="disabled")
    
    def log_stimulus(self, target_port: int) -> None:
        """
        Log a stimulus presentation to the trial log.

        Must be called on the main thread (marshalling is done by RigWindow).

        Args:
            target_port: The port that is the correct response.
        """
        trial_num = self._last_logged_trial + 1
        line = f"Trial {trial_num}: → Stimulus ON - Target port {target_port}\n"
        
        self._trial_log.config(state="normal")
        self._trial_log.insert(tk.END, line, "stimulus")
        self._trial_log.see(tk.END)
        self._trial_log.config(state="disabled")
    
    def update_performance(self, tracker: "PerformanceTracker") -> None:
        """
        Update the performance display from a tracker.

        Must be called on the main thread (marshalling is done by RigWindow).

        Args:
            tracker: The PerformanceTracker instance with current stats.
        """
        palette = Theme.palette
        
        self._trials_label.config(text=str(tracker.total_trials))
        self._correct_label.config(text=str(tracker.successes))
        self._incorrect_label.config(text=str(tracker.failures))
        self._timeout_label.config(text=str(tracker.timeouts))
        
        # Overall accuracy
        if tracker.responses > 0:
            acc = tracker.accuracy
            self._accuracy_label.config(text=f"{acc:.0f}%")
            # Color based on performance using theme
            self._accuracy_label.config(foreground=get_accuracy_color(acc))
        else:
            self._accuracy_label.config(text="--", foreground=palette.info)
        
        # Rolling accuracy (last N trials, user-selectable)
        if tracker.total_trials > 0:
            try:
                n = int(self._rolling_n_var.get())
            except ValueError:
                n = 20
            rolling = tracker.rolling_accuracy(n)
            self._rolling_label.config(text=f"{rolling:.0f}%")
        else:
            self._rolling_label.config(text="--")
        
        # Log new trials to the trial log (only fetch new ones)
        new_trials = tracker.get_trials_since(self._last_logged_trial)
        for trial in new_trials:
            self._log_trial(trial)
            self._last_logged_trial += 1
    
    def _log_trial(self, trial) -> None:
        """Log a single trial to the trial log with colored output."""
        from core.performance_tracker import TrialOutcome
        
        # Build trial description
        trial_num = trial.trial_number
        outcome = trial.outcome
        correct_port = trial.correct_port
        chosen_port = trial.chosen_port
        duration = trial.trial_duration
        
        # Format the log line based on outcome
        if outcome == TrialOutcome.SUCCESS:
            line = f"Trial {trial_num}: ✓ CORRECT - Port {correct_port} ({duration:.2f}s)\n"
            tag = "success"
        elif outcome == TrialOutcome.FAILURE:
            line = f"Trial {trial_num}: ✗ WRONG - Chose port {chosen_port}, correct was {correct_port} ({duration:.2f}s)\n"
            tag = "failure"
        else:  # TIMEOUT
            line = f"Trial {trial_num}: ⏱ TIMEOUT - Correct was port {correct_port} ({duration:.2f}s)\n"
            tag = "timeout"
        
        # Add to trial log
        self._trial_log.config(state="normal")
        self._trial_log.insert(tk.END, line, tag)
        self._trial_log.see(tk.END)
        self._trial_log.config(state="disabled")
    
    def deactivate(self) -> dict:
        """
        Called when leaving this mode.
        
        Returns:
            Context dict with elapsed_time and final log
        """
        self.stop_timer()
        self._scales_plot.stop()
        
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
    
    def start_timer(self) -> None:
        """Start the elapsed time timer (public interface)."""
        self._start_time = datetime.now()
        self._update_timer()

    def stop_timer(self) -> None:
        """Stop the elapsed time timer."""
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
    
    def stop_scales_plot(self) -> None:
        """Stop the scales poll loop (public interface)."""
        self._scales_plot.stop()
    
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
    
    def set_status(self, status: ProtocolStatus) -> None:
        """Update the status display."""
        palette = Theme.palette
        
        status_config = {
            ProtocolStatus.IDLE: ("IDLE", palette.text_secondary),
            ProtocolStatus.RUNNING: ("RUNNING", palette.success),
            ProtocolStatus.COMPLETED: ("COMPLETED", "#1e8449"),  # Darker green
            ProtocolStatus.ABORTED: ("STOPPED", palette.warning),
            ProtocolStatus.ERROR: ("ERROR", palette.error),
        }
        text, color = status_config.get(status, ("UNKNOWN", palette.text_primary))
        self._status_label.config(text=text, foreground=color)
        self._timer_label.config(foreground=color)
    
    def set_stopping(self) -> None:
        """Update UI to show stopping state."""
        palette = Theme.palette
        self._stop_button.config(state="disabled", text="Stopping...")
        self._status_label.config(text="STOPPING", foreground=palette.warning)
    
    def _clear_log(self) -> None:
        """Clear the log."""
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state="disabled")
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self._on_stop:
            self._on_stop()
