"""
Post-Session Mode - Review completed session.

Shows:
    - Session summary (status, protocol, mouse, duration, save path)
    - Performance plot over time
    - New Session button to return to setup
"""

import csv
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from gui.theme import Theme, get_accuracy_color


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
        
        # Performance Report Section
        self._perf_frame = ttk.LabelFrame(self, text="Performance Report", padding=(14, 10))
        self._perf_frame.pack(fill="x", padx=18, pady=8)
        
        # Create two-column grid layout for performance stats
        perf_container = ttk.Frame(self._perf_frame)
        perf_container.pack(fill="x")
        
        # Configure grid columns to expand properly
        perf_container.columnconfigure(0, weight=0)  # Left label
        perf_container.columnconfigure(1, weight=1)  # Left value
        perf_container.columnconfigure(2, weight=0, minsize=25)  # Spacer
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
                    style="Subheading.TLabel", anchor="e"
                ).grid(row=row_idx, column=0, sticky="e", pady=2)
                value_label = ttk.Label(
                    perf_container, text="-", 
                    font=Theme.font_body()
                )
                value_label.grid(row=row_idx, column=1, sticky="w", padx=(6, 0), pady=2)
                self._perf_labels[key] = value_label
            
            # Right side
            if row_idx < len(right_items):
                key, label_text = right_items[row_idx]
                ttk.Label(
                    perf_container, text=label_text,
                    style="Subheading.TLabel", anchor="e"
                ).grid(row=row_idx, column=3, sticky="e", pady=2)
                value_label = ttk.Label(
                    perf_container, text="-", 
                    font=Theme.font_body()
                )
                value_label.grid(row=row_idx, column=4, sticky="w", padx=(6, 0), pady=2)
                self._perf_labels[key] = value_label
        
        # Additional stats row
        extra_row = ttk.Frame(self._perf_frame)
        extra_row.pack(fill="x", pady=(8, 0))
        extra_row.columnconfigure(1, weight=1)
        extra_row.columnconfigure(4, weight=1)
        
        ttk.Label(
            extra_row, text="Trial Rate:",
            style="Subheading.TLabel", anchor="e"
        ).grid(row=0, column=0, sticky="e")
        self._perf_labels["trial_rate"] = ttk.Label(
            extra_row, text="-", 
            font=Theme.font_body()
        )
        self._perf_labels["trial_rate"].grid(row=0, column=1, sticky="w", padx=(8, 0))
        
        ttk.Label(
            extra_row, text="Last 20 Accuracy:",
            style="Subheading.TLabel", anchor="e"
        ).grid(row=0, column=3, sticky="e", padx=(18, 0))
        self._perf_labels["rolling_20"] = ttk.Label(
            extra_row, text="-", 
            font=Theme.font_body()
        )
        self._perf_labels["rolling_20"].grid(row=0, column=4, sticky="w", padx=(6, 0))
        
        # No trials message (hidden by default)
        self._no_trials_label = ttk.Label(
            self._perf_frame, 
            text="No trials were recorded during this session.",
            style="Muted.TLabel"
        )
        
        # Performance Plot Section
        self._create_performance_plot()
        
        # Spacer
        ttk.Frame(self).pack(fill="both", expand=True)
        
        # New session button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=18, pady=14)
        
        self._new_session_button = ttk.Button(
            button_frame, text="New Session",
            command=self._on_new_session_clicked,
            style="Primary.TButton"
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
        palette = Theme.palette
        status_colors = {
            "Completed": palette.success,
            "Stopped": palette.warning,
            "Error": palette.error,
        }
        color = status_colors.get(status, "black")
        self._summary_labels["status"].config(foreground=color)
        
        # Update performance report
        self._update_performance_report(session_result.get("performance_report"))
        
        # Update performance plot from trials.csv
        save_path = session_result.get("save_path", "")
        if save_path:
            self._update_performance_plot(Path(save_path))
    
    def _update_performance_report(self, report: dict | None) -> None:
        """
        Update the performance report section with session statistics.
        
        Args:
            report: Performance report dict from PerformanceTracker.get_report(),
                   or None if no trials were recorded
        """
        palette = Theme.palette
        
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
            foreground=palette.success
        )
        self._perf_labels["failures"].config(
            text=str(report.get("failures", 0)),
            foreground=palette.error
        )
        self._perf_labels["timeouts"].config(
            text=str(report.get("timeouts", 0)),
            foreground=palette.warning
        )
        
        # Update accuracy stats
        accuracy = report.get("accuracy", 0)
        self._perf_labels["accuracy"].config(
            text=f"{accuracy:.1f}%",
            foreground=palette.text_primary
        )
        
        accuracy_with_to = report.get("accuracy_with_timeouts", 0)
        self._perf_labels["accuracy_with_to"].config(
            text=f"{accuracy_with_to:.1f}%",
            foreground=palette.text_primary
        )
        
        timeout_rate = report.get("timeout_rate", 0)
        self._perf_labels["timeout_rate"].config(
            text=f"{timeout_rate:.1f}%",
            foreground=palette.warning if timeout_rate > 20 else palette.text_primary
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
            foreground=get_accuracy_color(rolling_20)
        )
    
    def _get_accuracy_color(self, accuracy: float) -> str:
        """Get color for accuracy value (green=good, orange=ok, red=poor)."""
        return get_accuracy_color(accuracy)
    
    def _create_performance_plot(self) -> None:
        """Create the performance plot section (initially empty)."""
        palette = Theme.palette
        
        # Plot frame
        self._plot_frame = ttk.LabelFrame(self, text="Performance Over Time", padding=(20, 15))
        self._plot_frame.pack(fill="both", expand=True, padx=25, pady=12)
        
        # Create matplotlib figure with themed colors
        self._figure = Figure(figsize=(6, 3), dpi=100, facecolor=palette.bg_secondary)
        self._ax = self._figure.add_subplot(111)
        self._ax.set_facecolor(palette.bg_secondary)
        
        # Initial empty plot setup
        self._ax.set_xlabel('Time (minutes)', fontsize=10, color=palette.text_secondary)
        self._ax.set_ylabel('Accuracy (%)', fontsize=10, color=palette.text_secondary)
        self._ax.set_title('Performance Over Session', fontsize=11, fontweight='bold', color=palette.text_primary)
        self._ax.set_ylim(0, 100)
        self._ax.grid(True, alpha=0.3, color=palette.border_medium)
        self._ax.tick_params(colors=palette.text_secondary)
        for spine in self._ax.spines.values():
            spine.set_color(palette.border_light)
        self._ax.text(0.5, 0.5, 'No data available', 
                     transform=self._ax.transAxes, ha='center', va='center',
                     fontsize=12, color=palette.text_disabled)
        
        self._figure.tight_layout()
        
        # Create canvas and embed in tkinter
        self._canvas = FigureCanvasTkAgg(self._figure, master=self._plot_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def _update_performance_plot(self, save_path: Path) -> None:
        """
        Update the performance plot with data from the trials.csv file.
        
        Calculates average accuracy in 2-minute time bins across the session.
        
        Args:
            save_path: Path to the session data folder containing trials.csv
        """
        # Find the trials.csv file
        trials_files = list(save_path.glob("*-trials.csv"))
        if not trials_files:
            # Try without prefix
            trials_file = save_path / "trials.csv"
            if not trials_file.exists():
                return
        else:
            trials_file = trials_files[0]
        
        # Load trial data
        trials = []
        try:
            with open(trials_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trials.append({
                        'time': float(row['time_since_start_s']),
                        'outcome': row['outcome']
                    })
        except (FileNotFoundError, KeyError, ValueError) as e:
            print(f"Error loading trials data: {e}")
            return
        
        if not trials:
            return
        
        # Calculate accuracy in 2-minute (120 second) bins
        bin_size_seconds = 120
        max_time = max(t['time'] for t in trials)
        
        time_bins = []  # Center of each bin in minutes
        accuracy_bins = []  # Accuracy for each bin
        
        bin_start = 0
        while bin_start < max_time:
            bin_end = bin_start + bin_size_seconds
            
            # Get trials in this bin
            bin_trials = [t for t in trials if bin_start <= t['time'] < bin_end]
            
            if bin_trials:
                # Count successes and responses (exclude timeouts for accuracy calc)
                successes = sum(1 for t in bin_trials if t['outcome'] == 'success')
                responses = sum(1 for t in bin_trials if t['outcome'] in ('success', 'failure'))
                
                if responses > 0:
                    accuracy = (successes / responses) * 100
                    # Use center of bin for x-axis (convert to minutes)
                    bin_center_minutes = (bin_start + bin_size_seconds / 2) / 60
                    time_bins.append(bin_center_minutes)
                    accuracy_bins.append(accuracy)
            
            bin_start = bin_end
        
        if not time_bins:
            return
        
        # Clear and update plot
        palette = Theme.palette
        self._ax.clear()
        
        # Plot the data with themed colors
        self._ax.plot(time_bins, accuracy_bins, color=palette.accent_primary, 
                     linewidth=2, marker='o', markersize=6,
                     label='Accuracy (2-min bins)')
        
        # Configure axes with themed styling
        self._ax.set_xlabel('Time (minutes)', fontsize=10, color=palette.text_secondary)
        self._ax.set_ylabel('Accuracy (%)', fontsize=10, color=palette.text_secondary)
        self._ax.set_title('Performance Over Session', fontsize=11, fontweight='bold', color=palette.text_primary)
        self._ax.set_ylim(0, 100)
        self._ax.set_xlim(0, max(time_bins) + 1)
        self._ax.grid(True, alpha=0.3, color=palette.border_medium)
        self._ax.tick_params(colors=palette.text_secondary)
        for spine in self._ax.spines.values():
            spine.set_color(palette.border_light)
        self._ax.legend(loc='lower right', fontsize=9)
        
        self._figure.tight_layout()
        self._canvas.draw()
    
    def _on_new_session_clicked(self) -> None:
        """Handle new session button click."""
        if self._on_new_session:
            self._on_new_session()
