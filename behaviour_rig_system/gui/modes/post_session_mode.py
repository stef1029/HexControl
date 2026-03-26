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
        self._perf_frame.pack(fill="x", padx=18, pady=8)
        
        # New session button (packed first so it's always visible at the bottom)
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
        
        # Performance Plot Section
        self._create_performance_plot()
    
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

        # Update performance report(s)
        self._update_performance_reports(session_result.get("performance_reports"))

        # Update performance plot from trials.csv
        save_path = session_result.get("save_path", "")
        if save_path:
            self._update_performance_plot(Path(save_path))

    def _update_performance_reports(self, reports: dict[str, dict] | None) -> None:
        """Build the performance report section from per-tracker reports."""
        # Clear existing content
        for child in self._perf_frame.winfo_children():
            child.destroy()

        if not reports:
            ttk.Label(
                self._perf_frame,
                text="No performance data recorded.",
                style="Muted.TLabel",
            ).pack(pady=10)
            return

        # Always use tabs (even for a single tracker)
        notebook = ttk.Notebook(self._perf_frame)
        notebook.pack(fill="x", expand=True)

        for name, report in reports.items():
            tab = ttk.Frame(notebook, padding=(10, 6))
            notebook.add(tab, text=name)
            self._fill_report_tab(tab, report, display_name=name)

    def _fill_report_tab(self, parent: ttk.Frame, report: dict, display_name: str = "") -> None:
        """Populate a single report tab with stats from a tracker report."""
        palette = Theme.palette

        # Tracker name header
        if display_name:
            ttk.Label(
                parent, text=display_name,
                font=Theme.font_mono(size=13, weight="bold"),
                foreground=palette.accent_primary,
            ).pack(fill="x", pady=(2, 4))

        if report.get("total_trials", 0) == 0:
            ttk.Label(parent, text="No trials recorded.", style="Muted.TLabel").pack(pady=10)
            return

        container = ttk.Frame(parent)
        container.pack(fill="x")
        container.columnconfigure(1, weight=1)
        container.columnconfigure(4, weight=1)

        left_items = [
            ("Total Trials:", str(report.get("total_trials", 0)), None),
            ("Successes:", str(report.get("successes", 0)), palette.success),
            ("Failures:", str(report.get("failures", 0)), palette.error),
            ("Timeouts:", str(report.get("timeouts", 0)), palette.warning),
        ]
        right_items = [
            ("Success (excl. TO):", f"{report.get('accuracy', 0):.1f}%", None),
            ("Success (incl. TO):", f"{report.get('accuracy_with_timeouts', 0):.1f}%", None),
            ("Timeout Rate:", f"{report.get('timeout_rate', 0):.1f}%",
             palette.warning if report.get("timeout_rate", 0) > 20 else None),
        ]

        max_rows = max(len(left_items), len(right_items))
        for row_idx in range(max_rows):
            if row_idx < len(left_items):
                label_text, value, fg = left_items[row_idx]
                ttk.Label(container, text=label_text, style="Subheading.TLabel", anchor="e").grid(
                    row=row_idx, column=0, sticky="e", pady=2)
                lbl = ttk.Label(container, text=value, font=Theme.font_body())
                if fg:
                    lbl.config(foreground=fg)
                lbl.grid(row=row_idx, column=1, sticky="w", padx=(6, 0), pady=2)

            if row_idx < len(right_items):
                label_text, value, fg = right_items[row_idx]
                ttk.Label(container, text=label_text, style="Subheading.TLabel", anchor="e").grid(
                    row=row_idx, column=3, sticky="e", pady=2)
                lbl = ttk.Label(container, text=value, font=Theme.font_body())
                if fg:
                    lbl.config(foreground=fg)
                lbl.grid(row=row_idx, column=4, sticky="w", padx=(6, 0), pady=2)

        # Extra row
        extra = ttk.Frame(parent)
        extra.pack(fill="x", pady=(8, 0))
        extra.columnconfigure(1, weight=1)
        extra.columnconfigure(4, weight=1)

        tpm = report.get("trials_per_minute", 0)
        ttk.Label(extra, text="Trial Rate:", style="Subheading.TLabel", anchor="e").grid(
            row=0, column=0, sticky="e")
        ttk.Label(extra, text=f"{tpm:.1f} trials/min" if tpm > 0 else "-",
                  font=Theme.font_body()).grid(row=0, column=1, sticky="w", padx=(8, 0))

        r20 = report.get("rolling_accuracy_20", 0)
        ttk.Label(extra, text="Last 20 Accuracy:", style="Subheading.TLabel", anchor="e").grid(
            row=0, column=3, sticky="e", padx=(18, 0))
        ttk.Label(extra, text=f"{r20:.1f}%", font=Theme.font_body(),
                  foreground=get_accuracy_color(r20)).grid(row=0, column=4, sticky="w", padx=(6, 0))
    
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
        Update the performance plot with data from the trials CSV.

        Reads the merged CSV (with ``tracker`` column) and plots each tracker
        as a separate line. Falls back to a single line if no tracker column.
        """
        # Find the trials.csv file
        trials_files = list(save_path.glob("*-trials.csv"))
        if not trials_files:
            trials_file = save_path / "trials.csv"
            if not trials_file.exists():
                return
        else:
            trials_file = trials_files[0]

        # Load trial data grouped by tracker
        tracker_trials: dict[str, list[dict]] = {}
        try:
            with open(trials_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tracker_name = row.get("tracker", "all")
                    tracker_trials.setdefault(tracker_name, []).append({
                        "time": float(row["time_since_start_s"]),
                        "outcome": row["outcome"],
                    })
        except (FileNotFoundError, KeyError, ValueError) as e:
            print(f"Error loading trials data: {e}")
            return

        if not tracker_trials:
            return

        palette = Theme.palette
        self._ax.clear()

        # Color cycle for multiple trackers
        colors = [palette.accent_primary, palette.accent_secondary,
                  palette.success, palette.warning, palette.error, palette.info]

        max_time_all = 0
        for idx, (name, trials) in enumerate(tracker_trials.items()):
            if not trials:
                continue

            bin_size_seconds = 120
            max_time = max(t["time"] for t in trials)
            max_time_all = max(max_time_all, max_time)

            time_bins = []
            accuracy_bins = []
            bin_start = 0
            while bin_start < max_time:
                bin_end = bin_start + bin_size_seconds
                bin_trials = [t for t in trials if bin_start <= t["time"] < bin_end]
                if bin_trials:
                    successes = sum(1 for t in bin_trials if t["outcome"] == "success")
                    responses = sum(1 for t in bin_trials if t["outcome"] in ("success", "failure"))
                    if responses > 0:
                        accuracy = (successes / responses) * 100
                        bin_center_minutes = (bin_start + bin_size_seconds / 2) / 60
                        time_bins.append(bin_center_minutes)
                        accuracy_bins.append(accuracy)
                bin_start = bin_end

            if time_bins:
                color = colors[idx % len(colors)]
                self._ax.plot(
                    time_bins, accuracy_bins, color=color,
                    linewidth=2, marker="o", markersize=5,
                    label=f"{name} (2-min bins)",
                )

        # Style axes
        self._ax.set_xlabel("Time (minutes)", fontsize=10, color=palette.text_secondary)
        self._ax.set_ylabel("Accuracy (%)", fontsize=10, color=palette.text_secondary)
        self._ax.set_title("Performance Over Session", fontsize=11, fontweight="bold", color=palette.text_primary)
        self._ax.set_ylim(0, 100)
        if max_time_all > 0:
            self._ax.set_xlim(0, (max_time_all / 60) + 1)
        self._ax.grid(True, alpha=0.3, color=palette.border_medium)
        self._ax.tick_params(colors=palette.text_secondary)
        for spine in self._ax.spines.values():
            spine.set_color(palette.border_light)
        self._ax.legend(loc="lower right", fontsize=9)

        self._figure.tight_layout()
        self._canvas.draw()
    
    def _on_button_click(self, event: tk.Event) -> None:
        """Handle button click: Ctrl+click = new session, normal click = close window."""
        if event.state & 0x4:  # Ctrl key held
            if self._on_new_session:
                self._on_new_session()
        else:
            if self._on_close_window:
                self._on_close_window()
