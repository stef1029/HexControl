"""
Tracker Report Widget - Self-contained post-session display.

Takes raw trial data from one or more trackers and handles all
interpretation (stats computation) and display (stats grid + plots).

Plotters are pluggable: define a class with `name` and `plot()`,
add it to PLOTTERS, and it automatically gets a tab.
"""

import tkinter as tk
from abc import ABC, abstractmethod
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from hexcontrol.gui.theme import Theme, get_accuracy_color


# =============================================================================
# Plotter interface and built-in plotters
# =============================================================================

class BasePlotter(ABC):
    """Base class for post-session plot types."""

    name: str  # Tab label

    @abstractmethod
    def plot(self, parent: ttk.Frame, trials: list[dict], palette) -> None:
        """Create a matplotlib figure and embed it in parent.

        Args:
            parent: Frame to pack the plot into.
            trials: List of trial dicts with keys:
                time_since_start, outcome, correct_port, chosen_port, trial_duration
            palette: Theme palette for styling.
        """
        ...


def _create_styled_figure(palette, height: float = 2.5):
    """Create a themed matplotlib Figure + Axes pair."""
    fig = Figure(figsize=(6, height), dpi=100, facecolor=palette.bg_secondary)
    ax = fig.add_subplot(111)
    ax.set_facecolor(palette.bg_secondary)
    ax.grid(True, alpha=0.3, color=palette.border_medium)
    ax.tick_params(colors=palette.text_secondary)
    for spine in ax.spines.values():
        spine.set_color(palette.border_light)
    return fig, ax


def _embed_figure(parent: ttk.Frame, fig: Figure) -> None:
    """Embed a matplotlib Figure into a tkinter frame."""
    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def _bin_trials(trials: list[dict], bin_size_seconds: float = 120.0):
    """Group trials into time bins.

    Yields (bin_centre_minutes, bin_trials) for each non-empty bin.
    """
    if not trials:
        return
    max_time = max(t["time_since_start"] for t in trials)
    bin_start = 0.0
    while bin_start < max_time:
        bin_end = bin_start + bin_size_seconds
        bin_trials = [t for t in trials if bin_start <= t["time_since_start"] < bin_end]
        if bin_trials:
            bin_centre = (bin_start + bin_size_seconds / 2) / 60.0
            yield bin_centre, bin_trials
        bin_start = bin_end


class AccuracyOverTimePlotter(BasePlotter):
    """Accuracy (%) over session time in 2-minute bins."""

    name = "Accuracy"

    def plot(self, parent: ttk.Frame, trials: list[dict], palette) -> None:
        fig, ax = _create_styled_figure(palette)

        time_bins = []
        accuracy_bins = []
        for bin_centre, bin_trials in _bin_trials(trials):
            successes = sum(1 for t in bin_trials if t["outcome"] == "success")
            responses = sum(1 for t in bin_trials if t["outcome"] in ("success", "failure"))
            if responses > 0:
                time_bins.append(bin_centre)
                accuracy_bins.append(successes / responses * 100)

        if time_bins:
            ax.plot(
                time_bins, accuracy_bins,
                color=palette.accent_primary, linewidth=2,
                marker="o", markersize=5,
                label="Accuracy (2-min bins)",
            )
            ax.legend(loc="lower right", fontsize=9)

        ax.set_xlabel("Time (minutes)", fontsize=10, color=palette.text_secondary)
        ax.set_ylabel("Accuracy (%)", fontsize=10, color=palette.text_secondary)
        ax.set_title("Accuracy Over Session", fontsize=11, fontweight="bold", color=palette.text_primary)
        ax.set_ylim(0, 100)
        if time_bins:
            ax.set_xlim(0, time_bins[-1] + 1)

        _embed_figure(parent, fig)


class TrialDurationPlotter(BasePlotter):
    """Mean trial duration (seconds) over session time in 2-minute bins."""

    name = "Trial Duration"

    def plot(self, parent: ttk.Frame, trials: list[dict], palette) -> None:
        fig, ax = _create_styled_figure(palette)

        # Exclude timeouts (they have artificial fixed durations)
        response_trials = [t for t in trials if t["outcome"] in ("success", "failure")]

        time_bins = []
        duration_bins = []
        for bin_centre, bin_trials in _bin_trials(response_trials):
            durations = [t["trial_duration"] for t in bin_trials if t["trial_duration"] > 0]
            if durations:
                time_bins.append(bin_centre)
                duration_bins.append(sum(durations) / len(durations))

        if time_bins:
            ax.plot(
                time_bins, duration_bins,
                color=palette.accent_secondary, linewidth=2,
                marker="s", markersize=5,
                label="Mean duration (2-min bins)",
            )
            ax.legend(loc="upper right", fontsize=9)

        ax.set_xlabel("Time (minutes)", fontsize=10, color=palette.text_secondary)
        ax.set_ylabel("Duration (s)", fontsize=10, color=palette.text_secondary)
        ax.set_title("Trial Duration Over Session", fontsize=11, fontweight="bold", color=palette.text_primary)
        if duration_bins:
            ax.set_ylim(0, max(duration_bins) * 1.2)
            ax.set_xlim(0, time_bins[-1] + 1)

        _embed_figure(parent, fig)


# Registry — add new plotters here
PLOTTERS: list[BasePlotter] = [
    AccuracyOverTimePlotter(),
    TrialDurationPlotter(),
]


# =============================================================================
# TrackerReportWidget
# =============================================================================

class TrackerReportWidget(ttk.Frame):
    """
    Self-contained post-session display for one or more trackers.

    Outer notebook: one tab per tracker.
    Each tab: stats section + inner notebook of plot tabs.
    """

    def __init__(self, parent: tk.Widget, reports: dict[str, dict]):
        """
        Args:
            parent: Parent widget.
            reports: {tracker_name: {"trials": [...], "session_duration": float}}
                     Each trial dict has: time_since_start, outcome,
                     correct_port, chosen_port, trial_duration.
        """
        super().__init__(parent)
        self._reports = reports
        self._build_ui()

    def _build_ui(self) -> None:
        if not self._reports:
            ttk.Label(
                self, text="No performance data recorded.",
                style="Muted.TLabel",
            ).pack(pady=10)
            return

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        for name, report in self._reports.items():
            sub_trackers = report.get("sub_trackers")
            is_simple = report.get("is_simple", True)

            if not is_simple and sub_trackers and len(sub_trackers) > 1:
                # Grouped tracker: outer tab with inner sub-tabs
                outer_tab = ttk.Frame(notebook, padding=(4, 4))
                notebook.add(outer_tab, text=name)

                inner_nb = ttk.Notebook(outer_tab)
                inner_nb.pack(fill="both", expand=True)

                # Overall tab with all trials
                overall_tab = ttk.Frame(inner_nb, padding=(10, 6))
                inner_nb.add(overall_tab, text="Overall")
                self._build_tracker_tab(overall_tab, "Overall", report)

                # Per-sub-tracker tabs
                all_trials = report.get("trials", [])
                session_duration = report.get("session_duration", 0.0)
                for sub_name in sub_trackers:
                    sub_trials = [t for t in all_trials if t.get("trial_type") == sub_name]
                    sub_report = {"trials": sub_trials, "session_duration": session_duration}
                    sub_tab = ttk.Frame(inner_nb, padding=(10, 6))
                    inner_nb.add(sub_tab, text=sub_name.capitalize())
                    self._build_tracker_tab(sub_tab, sub_name.capitalize(), sub_report)
            else:
                # Simple tracker
                tab = ttk.Frame(notebook, padding=(10, 6))
                notebook.add(tab, text=name)
                self._build_tracker_tab(tab, name, report)

    def _build_tracker_tab(
        self, parent: ttk.Frame, name: str, report: dict
    ) -> None:
        trials = report.get("trials", [])
        session_duration = report.get("session_duration", 0.0)

        # Stats section
        stats = self._compute_stats(trials, session_duration)
        self._build_stats_section(parent, name, stats)

        # Plot tabs
        if trials:
            plot_notebook = ttk.Notebook(parent)
            plot_notebook.pack(fill="both", expand=True, pady=(8, 0))

            palette = Theme.palette
            for plotter in PLOTTERS:
                plot_frame = ttk.Frame(plot_notebook)
                plot_notebook.add(plot_frame, text=plotter.name)
                plotter.plot(plot_frame, trials, palette)

    # =========================================================================
    # Stats computation
    # =========================================================================

    @staticmethod
    def _compute_stats(trials: list[dict], session_duration: float) -> dict:
        """Compute display statistics from raw trial data."""
        successes = sum(1 for t in trials if t["outcome"] == "success")
        failures = sum(1 for t in trials if t["outcome"] == "failure")
        timeouts = sum(1 for t in trials if t["outcome"] == "timeout")
        total = len(trials)
        responses = successes + failures

        # Rolling accuracy (last 20 non-timeout trials)
        recent = [t for t in trials if t["outcome"] != "timeout"][-20:]
        rolling_20 = (
            (sum(1 for t in recent if t["outcome"] == "success") / len(recent) * 100)
            if recent else 0.0
        )

        return {
            "total_trials": total,
            "successes": successes,
            "failures": failures,
            "timeouts": timeouts,
            "responses": responses,
            "accuracy": (successes / responses * 100) if responses > 0 else 0.0,
            "accuracy_with_timeouts": (successes / total * 100) if total > 0 else 0.0,
            "timeout_rate": (timeouts / total * 100) if total > 0 else 0.0,
            "rolling_accuracy_20": rolling_20,
            "trials_per_minute": (total / (session_duration / 60)) if session_duration > 0 else 0.0,
        }

    # =========================================================================
    # Stats display
    # =========================================================================

    @staticmethod
    def _build_stats_section(parent: ttk.Frame, name: str, stats: dict) -> None:
        """Render the summary statistics grid."""
        palette = Theme.palette

        # Tracker name header
        ttk.Label(
            parent, text=name,
            font=Theme.font_mono(size=13, weight="bold"),
            foreground=palette.accent_primary,
        ).pack(fill="x", pady=(2, 4))

        if stats["total_trials"] == 0:
            ttk.Label(parent, text="No trials recorded.", style="Muted.TLabel").pack(pady=10)
            return

        container = ttk.Frame(parent)
        container.pack(fill="x")
        container.columnconfigure(1, weight=1)
        container.columnconfigure(4, weight=1)

        left_items = [
            ("Total Trials:", str(stats["total_trials"]), None),
            ("Successes:", str(stats["successes"]), palette.success),
            ("Failures:", str(stats["failures"]), palette.error),
            ("Timeouts:", str(stats["timeouts"]), palette.warning),
        ]
        right_items = [
            ("Success (excl. TO):", f"{stats['accuracy']:.1f}%", None),
            ("Success (incl. TO):", f"{stats['accuracy_with_timeouts']:.1f}%", None),
            ("Timeout Rate:", f"{stats['timeout_rate']:.1f}%",
             palette.warning if stats["timeout_rate"] > 20 else None),
        ]

        max_rows = max(len(left_items), len(right_items))
        for row_idx in range(max_rows):
            if row_idx < len(left_items):
                label_text, value, fg = left_items[row_idx]
                ttk.Label(
                    container, text=label_text,
                    style="Subheading.TLabel", anchor="e",
                ).grid(row=row_idx, column=0, sticky="e", pady=2)
                lbl = ttk.Label(container, text=value, font=Theme.font_body())
                if fg:
                    lbl.config(foreground=fg)
                lbl.grid(row=row_idx, column=1, sticky="w", padx=(6, 0), pady=2)

            if row_idx < len(right_items):
                label_text, value, fg = right_items[row_idx]
                ttk.Label(
                    container, text=label_text,
                    style="Subheading.TLabel", anchor="e",
                ).grid(row=row_idx, column=3, sticky="e", pady=2)
                lbl = ttk.Label(container, text=value, font=Theme.font_body())
                if fg:
                    lbl.config(foreground=fg)
                lbl.grid(row=row_idx, column=4, sticky="w", padx=(6, 0), pady=2)

        # Extra row: trial rate + rolling accuracy
        extra = ttk.Frame(parent)
        extra.pack(fill="x", pady=(8, 0))
        extra.columnconfigure(1, weight=1)
        extra.columnconfigure(4, weight=1)

        tpm = stats["trials_per_minute"]
        ttk.Label(
            extra, text="Trial Rate:",
            style="Subheading.TLabel", anchor="e",
        ).grid(row=0, column=0, sticky="e")
        ttk.Label(
            extra,
            text=f"{tpm:.1f} trials/min" if tpm > 0 else "-",
            font=Theme.font_body(),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        r20 = stats["rolling_accuracy_20"]
        ttk.Label(
            extra, text="Last 20 Accuracy:",
            style="Subheading.TLabel", anchor="e",
        ).grid(row=0, column=3, sticky="e", padx=(18, 0))
        ttk.Label(
            extra, text=f"{r20:.1f}%",
            font=Theme.font_body(),
            foreground=get_accuracy_color(r20),
        ).grid(row=0, column=4, sticky="w", padx=(6, 0))
