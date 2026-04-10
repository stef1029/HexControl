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

import subprocess
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, ttk
from typing import Callable

from hexcontrol.core.protocol_base import ProtocolStatus
from hexcontrol.gui.theme import Theme, style_scrolled_text, get_accuracy_color
from hexcontrol.gui.scales_plot_widget import ScalesPlotWidget



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
        self._tracker_widgets: dict[str, dict] = {}  # Per-tracker widget refs
        self._tracker_definitions: list = []
        self._tracker_tab_indices: dict[str, int] = {}  # tracker name -> tab index
        self._last_logged_trials: dict[str, int] = {}  # Per-tracker log index
        self._perf_notebook: ttk.Notebook | None = None
        self._lock_tracker_view = tk.BooleanVar(value=False)
        self._daq_view_proc: subprocess.Popen | None = None
        self._rig_number: int = 0

        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the running UI widgets."""
        palette = Theme.palette

        # Stop button (packed first so it's always visible at the bottom)
        button_frame = ttk.Frame(self)
        button_frame.pack(side="bottom", fill="x", padx=10, pady=8)

        self._stop_button = ttk.Button(
            button_frame, text="Stop Session",
            command=self._on_stop_clicked,
            style="Danger.TButton"
        )
        self._stop_button.pack(side="right", padx=3)

        self._daq_view_btn = ttk.Button(
            button_frame, text="DAQ View",
            command=self._toggle_daq_view,
        )
        self._daq_view_btn.pack(side="right", padx=3)

        # Timer and status row (pinned above buttons)
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
        # Resizable paned area: Session+Performance | Trial Log | Scales | Log
        # =====================================================================
        self._paned = ttk.PanedWindow(self, orient="vertical")
        self._paned.pack(fill="both", expand=True, padx=10, pady=5)

        # --- Pane 1: Session Summary + Performance ---
        info_pane = ttk.Frame(self._paned)

        summary_frame = ttk.LabelFrame(info_pane, text="Session", padding=(10, 6))
        summary_frame.pack(fill="x", pady=(0, 3))

        self._summary_labels = {}
        for key, label_text in [("protocol", "Protocol:"), ("mouse", "Mouse:"), ("save_path", "Saving to:")]:
            row = ttk.Frame(summary_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label_text, style="Subheading.TLabel").pack(side="left")
            value_label = ttk.Label(row, text="", foreground=palette.text_secondary)
            value_label.pack(side="left", padx=6)
            self._summary_labels[key] = value_label

        self._perf_frame = ttk.LabelFrame(info_pane, text="Performance", padding=(10, 6))
        self._perf_frame.pack(fill="both", expand=True)

        self._paned.add(info_pane, weight=0)

        # --- Pane 2: Trial Log ---
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

        # --- Pane 3: Live Scales Plot ---
        scales_pane = ttk.LabelFrame(self._paned, text="Scales", padding=(8, 4))
        self._scales_plot = ScalesPlotWidget(scales_pane)
        self._scales_plot.pack(fill="both", expand=True)

        self._paned.add(scales_pane, weight=1)

        # --- Pane 4: Session Log ---
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

    def set_scales_threshold(self, value) -> None:
        """Set the activation threshold line on the scales plot."""
        self._scales_plot.set_threshold(value)

    def set_battery_detection(self, enabled: bool) -> None:
        """Enable or disable the stuck-battery detection warning on the scales plot."""
        self._scales_plot.set_battery_detection(enabled)
    
    def activate(self, session_config: dict, tracker_definitions: list | None = None,
                 rig_number: int = 0) -> None:
        """
        Called when this mode becomes active.

        Args:
            session_config: Dict with protocol_name, mouse_id, save_path
            tracker_definitions: List of TrackerDefinition from the protocol
            rig_number: Rig number (1-indexed) for DAQ UDP listener
        """
        self._rig_number = rig_number

        # Reset UI state
        self._clear_log()
        self._stop_button.config(state="normal", text="Stop Session")

        # Set session info
        self._summary_labels["protocol"].config(text=session_config.get("protocol_name", ""))
        self._summary_labels["mouse"].config(text=session_config.get("mouse_id", ""))
        self._summary_labels["save_path"].config(text=session_config.get("save_path", ""))

        # Build performance tabs from tracker definitions
        self._tracker_definitions = tracker_definitions or []
        self._build_performance_tabs()

        # Reset timer state
        self._start_time = None
        self._timer_label.config(text="00:00:00")

        # Start the live scales plot
        self._scales_plot.start()
    
    def _build_performance_tabs(self) -> None:
        """Build (or rebuild) the performance display from tracker definitions."""
        palette = Theme.palette

        # Clear existing content
        for child in self._perf_frame.winfo_children():
            child.destroy()
        self._tracker_widgets.clear()
        self._tracker_tab_indices.clear()
        self._last_logged_trials.clear()
        self._perf_notebook = None
        self._lock_tracker_view.set(False)

        # Clear trial log
        self._trial_log.config(state="normal")
        self._trial_log.delete("1.0", tk.END)
        self._trial_log.config(state="disabled")

        if not self._tracker_definitions:
            ttk.Label(
                self._perf_frame,
                text="No performance trackers defined",
                foreground=palette.text_secondary,
            ).pack(pady=10)
            return

        # Lock view checkbox
        controls_row = ttk.Frame(self._perf_frame)
        controls_row.pack(fill="x")
        ttk.Checkbutton(
            controls_row, text="Lock view",
            variable=self._lock_tracker_view,
        ).pack(side="right")

        # Notebook with one tab per tracker group
        self._perf_notebook = ttk.Notebook(self._perf_frame)
        self._perf_notebook.pack(fill="x", expand=True)

        # Extract unique tracker definitions (multiple stage keys may share one).
        if isinstance(self._tracker_definitions, dict):
            seen_ids: set[int] = set()
            unique_defs: list = []
            for tdef in self._tracker_definitions.values():
                if id(tdef) not in seen_ids:
                    seen_ids.add(id(tdef))
                    unique_defs.append(tdef)
        else:
            unique_defs = list(self._tracker_definitions)

        for idx, tdef in enumerate(unique_defs):
            sub_trackers = getattr(tdef, "sub_trackers", None)
            has_subs = sub_trackers is not None and len(sub_trackers) > 0

            if has_subs:
                # Multi-sub-tracker group: create inner notebook with sub-tabs
                outer_tab = ttk.Frame(self._perf_notebook, padding=(2, 2))
                self._perf_notebook.add(outer_tab, text=tdef.display_name)
                self._tracker_tab_indices[tdef.name] = idx

                inner_nb = ttk.Notebook(outer_tab)
                inner_nb.pack(fill="x", expand=True)

                # "Overall" sub-tab (aggregated)
                overall_tab = ttk.Frame(inner_nb, padding=(6, 4))
                inner_nb.add(overall_tab, text="Overall")
                overall_widgets = self._create_tracker_tab(overall_tab, display_name="Overall")

                # Per-sub-tracker tabs
                sub_widgets = {}
                for sub_name in sub_trackers:
                    sub_tab = ttk.Frame(inner_nb, padding=(6, 4))
                    inner_nb.add(sub_tab, text=sub_name.capitalize())
                    sub_widgets[sub_name] = self._create_tracker_tab(
                        sub_tab, display_name=sub_name.capitalize()
                    )

                self._tracker_widgets[tdef.name] = {
                    "_overall": overall_widgets,
                    "_sub": sub_widgets,
                    "_inner_nb": inner_nb,
                }
                self._last_logged_trials[tdef.name] = 0
            else:
                # Simple group: single tab as before
                tab = ttk.Frame(self._perf_notebook, padding=(6, 4))
                self._perf_notebook.add(tab, text=tdef.display_name)
                widgets = self._create_tracker_tab(tab, display_name=tdef.display_name)
                self._tracker_widgets[tdef.name] = widgets
                self._tracker_tab_indices[tdef.name] = idx
                self._last_logged_trials[tdef.name] = 0

    def _create_tracker_tab(self, parent: ttk.Frame, display_name: str = "") -> dict:
        """Create the standard stats widgets inside a tracker tab. Returns widget refs."""
        palette = Theme.palette

        # Tracker name header
        name_label = ttk.Label(
            parent, text=display_name,
            font=Theme.font_mono(size=13, weight="bold"),
            foreground=palette.accent_primary,
        )
        name_label.pack(fill="x", pady=(2, 4))

        # Stats row
        stats_row = ttk.Frame(parent)
        stats_row.pack(fill="x", pady=3)

        ttk.Label(stats_row, text="Trials:", style="Subheading.TLabel").pack(side="left")
        trials_label = ttk.Label(
            stats_row, text="0",
            font=Theme.font_mono(size=12),
            foreground=palette.accent_primary,
        )
        trials_label.pack(side="left", padx=(6, 16))

        ttk.Label(stats_row, text="Accuracy:", style="Subheading.TLabel").pack(side="left")
        accuracy_label = ttk.Label(
            stats_row, text="--",
            font=Theme.font_mono(size=12, weight="bold"),
            foreground=palette.info,
        )
        accuracy_label.pack(side="left", padx=(6, 16))

        ttk.Label(stats_row, text="Last", style="Subheading.TLabel").pack(side="left")
        rolling_n_var = tk.StringVar(value="20")
        rolling_n_combo = ttk.Combobox(
            stats_row,
            textvariable=rolling_n_var,
            values=["5", "10", "20", "50", "100"],
            width=4,
            state="readonly",
        )
        rolling_n_combo.pack(side="left", padx=(4, 2))
        ttk.Label(stats_row, text=":", style="Subheading.TLabel").pack(side="left")
        rolling_label = ttk.Label(
            stats_row, text="--",
            font=Theme.font_mono(size=12),
            foreground=palette.accent_secondary,
        )
        rolling_label.pack(side="left", padx=(6, 0))

        # Breakdown row
        breakdown_row = ttk.Frame(parent)
        breakdown_row.pack(fill="x", pady=3)

        ttk.Label(breakdown_row, text="Correct:").pack(side="left")
        correct_label = ttk.Label(
            breakdown_row, text="0",
            font=Theme.font_mono(size=10),
            foreground=palette.success,
        )
        correct_label.pack(side="left", padx=(4, 14))

        ttk.Label(breakdown_row, text="Incorrect:").pack(side="left")
        incorrect_label = ttk.Label(
            breakdown_row, text="0",
            font=Theme.font_mono(size=10),
            foreground=palette.error,
        )
        incorrect_label.pack(side="left", padx=(4, 14))

        ttk.Label(breakdown_row, text="Timeouts:").pack(side="left")
        timeout_label = ttk.Label(
            breakdown_row, text="0",
            font=Theme.font_mono(size=10),
            foreground=palette.warning,
        )
        timeout_label.pack(side="left", padx=(4, 0))

        return {
            "trials": trials_label,
            "accuracy": accuracy_label,
            "rolling_n_var": rolling_n_var,
            "rolling": rolling_label,
            "correct": correct_label,
            "incorrect": incorrect_label,
            "timeout": timeout_label,
        }
    
    def log_stimulus(self, target_port: int) -> None:
        """
        Log a stimulus presentation to the trial log.

        Must be called on the main thread (marshalling is done by RigWindow).

        Args:
            target_port: The port that is the correct response.
        """
        line = f"→ Stimulus ON - Target port {target_port}\n"

        self._trial_log.config(state="normal")
        self._trial_log.insert(tk.END, line, "stimulus")
        self._trial_log.see(tk.END)
        self._trial_log.config(state="disabled")

    def update_performance(self, trackers: dict = None, updated: str = "") -> None:
        """
        Update the performance display for the tracker that changed.

        Must be called on the main thread (marshalling is done by RigWindow).

        Args:
            trackers: Dict of tracker_name -> Tracker.
            updated:  Name of the tracker that just changed.
        """
        if trackers is None or updated not in self._tracker_widgets or updated not in trackers:
            return

        tracker = trackers[updated]
        w = self._tracker_widgets[updated]
        palette = Theme.palette

        if "_overall" in w:
            # Multi-sub-tracker: update overall + sub-tracker tabs
            self._update_tracker_widgets(w["_overall"], tracker, palette)
            for sub_name, sub_widgets in w["_sub"].items():
                sub = tracker.get_sub_tracker(sub_name)
                if sub is not None:
                    self._update_tracker_widgets(sub_widgets, sub, palette)
        else:
            # Simple tracker: update single tab
            self._update_tracker_widgets(w, tracker, palette)

        # Log new trials to the shared trial log
        last = self._last_logged_trials.get(updated, 0)
        all_trials = tracker.get_all_trials()
        new_trials = all_trials[last:]
        multi = len(self._tracker_widgets) > 1
        display_name = tracker.display_name
        for trial in new_trials:
            self._log_trial(trial, prefix=f"[{display_name}] " if multi else "")
            self._last_logged_trials[updated] = last + 1
            last += 1

        # Auto-switch to the updated tracker's tab (unless locked)
        if (
            not self._lock_tracker_view.get()
            and self._perf_notebook is not None
            and updated in self._tracker_tab_indices
        ):
            self._perf_notebook.select(self._tracker_tab_indices[updated])

    def _update_tracker_widgets(self, w: dict, tracker, palette) -> None:
        """Update a set of stat widgets from a tracker or tracker group."""
        w["trials"].config(text=str(tracker.total_trials))
        w["correct"].config(text=str(tracker.successes))
        w["incorrect"].config(text=str(tracker.failures))
        w["timeout"].config(text=str(tracker.timeouts))

        if tracker.responses > 0:
            acc = tracker.accuracy
            w["accuracy"].config(text=f"{acc:.0f}%", foreground=get_accuracy_color(acc))
        else:
            w["accuracy"].config(text="--", foreground=palette.info)

        if tracker.total_trials > 0:
            try:
                n = int(w["rolling_n_var"].get())
            except ValueError:
                n = 20
            rolling = tracker.rolling_accuracy(n)
            w["rolling"].config(text=f"{rolling:.0f}%")
        else:
            w["rolling"].config(text="--")

    def _log_trial(self, trial, prefix: str = "") -> None:
        """Log a single trial to the trial log with colored output."""
        from core.tracker import TrialOutcome

        trial_num = trial.trial_number
        outcome = trial.outcome
        correct_port = trial.correct_port
        chosen_port = trial.chosen_port
        duration = trial.trial_duration

        if outcome == TrialOutcome.SUCCESS:
            line = f"{prefix}Trial {trial_num}: ✓ CORRECT - Port {correct_port} ({duration:.2f}s)\n"
            tag = "success"
        elif outcome == TrialOutcome.FAILURE:
            line = f"{prefix}Trial {trial_num}: ✗ WRONG - Chose port {chosen_port}, correct was {correct_port} ({duration:.2f}s)\n"
            tag = "failure"
        else:  # TIMEOUT
            line = f"{prefix}Trial {trial_num}: ⏱ TIMEOUT - Correct was port {correct_port} ({duration:.2f}s)\n"
            tag = "timeout"

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
        self._close_daq_view()
        
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
            ProtocolStatus.STOPPED: ("STOPPED", palette.warning),
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
    
    def _toggle_daq_view(self) -> None:
        """Open the DAQ live-view in a separate process."""
        # If process is still running, do nothing (user can close it themselves)
        if self._daq_view_proc is not None and self._daq_view_proc.poll() is None:
            return

        script = Path(__file__).resolve().parents[1] / "daq_view_subprocess.py"
        self._daq_view_proc = subprocess.Popen(
            [sys.executable, str(script), str(self._rig_number)],
        )

    def _close_daq_view(self) -> None:
        """Terminate the DAQ view subprocess if still running."""
        if self._daq_view_proc is not None:
            if self._daq_view_proc.poll() is None:
                self._daq_view_proc.terminate()
            self._daq_view_proc = None

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self._on_stop:
            self._on_stop()
