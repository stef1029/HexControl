"""
Tracker Report Widget - Post-session display using DearPyGui native plots.

Takes raw trial data from one or more trackers and handles all
interpretation (stats computation) and display (stats grid + plots).

Replaces the matplotlib-based implementation with DPG native plotting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import dearpygui.dearpygui as dpg

from hexcontrol.gui.theme import Theme, hex_to_rgba, get_accuracy_color


# =============================================================================
# Plotter interface and built-in plotters
# =============================================================================

class BasePlotter(ABC):
    """Base class for post-session plot types."""

    name: str

    @abstractmethod
    def plot(self, parent: int | str, trials: list[dict], palette) -> None:
        """Create a DPG plot inside *parent*."""
        ...


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

    def plot(self, parent: int | str, trials: list[dict], palette) -> None:
        time_bins = []
        accuracy_bins = []
        for bin_centre, bin_trials in _bin_trials(trials):
            successes = sum(1 for t in bin_trials if t["outcome"] == "success")
            responses = sum(1 for t in bin_trials if t["outcome"] in ("success", "failure"))
            if responses > 0:
                time_bins.append(bin_centre)
                accuracy_bins.append(successes / responses * 100)

        with dpg.plot(label="Accuracy Over Session", height=200, width=-1, parent=parent):
            x_ax = dpg.add_plot_axis(dpg.mvXAxis, label="Time (minutes)")
            y_ax = dpg.add_plot_axis(dpg.mvYAxis, label="Accuracy (%)")
            dpg.set_axis_limits(y_ax, 0, 100)
            if time_bins:
                dpg.set_axis_limits(x_ax, 0, time_bins[-1] + 1)
                dpg.add_line_series(
                    time_bins, accuracy_bins, parent=y_ax,
                    label="Accuracy (2-min bins)",
                )
            dpg.add_plot_legend()


class TrialDurationPlotter(BasePlotter):
    """Mean trial duration (seconds) over session time in 2-minute bins."""

    name = "Trial Duration"

    def plot(self, parent: int | str, trials: list[dict], palette) -> None:
        response_trials = [t for t in trials if t["outcome"] in ("success", "failure")]

        time_bins = []
        duration_bins = []
        for bin_centre, bin_trials in _bin_trials(response_trials):
            durations = [t["trial_duration"] for t in bin_trials if t["trial_duration"] > 0]
            if durations:
                time_bins.append(bin_centre)
                duration_bins.append(sum(durations) / len(durations))

        with dpg.plot(label="Trial Duration Over Session", height=200, width=-1, parent=parent):
            x_ax = dpg.add_plot_axis(dpg.mvXAxis, label="Time (minutes)")
            y_ax = dpg.add_plot_axis(dpg.mvYAxis, label="Duration (s)")
            if duration_bins:
                dpg.set_axis_limits(y_ax, 0, max(duration_bins) * 1.2)
                dpg.set_axis_limits(x_ax, 0, time_bins[-1] + 1)
                dpg.add_line_series(
                    time_bins, duration_bins, parent=y_ax,
                    label="Mean duration (2-min bins)",
                )
            dpg.add_plot_legend()


PLOTTERS: list[BasePlotter] = [
    AccuracyOverTimePlotter(),
    TrialDurationPlotter(),
]


# =============================================================================
# TrackerReportWidget
# =============================================================================

class TrackerReportWidget:
    """
    Self-contained post-session display for one or more trackers.
    """

    def __init__(self, parent: int | str, reports: dict[str, dict]):
        self._parent = parent
        self._reports = reports
        self._build_ui()

    def _build_ui(self) -> None:
        if not self._reports:
            dpg.add_text("No performance data recorded.",
                         parent=self._parent,
                         color=hex_to_rgba(Theme.palette.text_secondary))
            return

        with dpg.tab_bar(parent=self._parent):
            for name, report in self._reports.items():
                sub_trackers = report.get("sub_trackers")
                is_simple = report.get("is_simple", True)

                if not is_simple and sub_trackers and len(sub_trackers) > 1:
                    with dpg.tab(label=name):
                        with dpg.tab_bar():
                            with dpg.tab(label="Overall"):
                                self._build_tracker_tab(name="Overall", report=report)
                            all_trials = report.get("trials", [])
                            session_duration = report.get("session_duration", 0.0)
                            for sub_name in sub_trackers:
                                sub_trials = [t for t in all_trials if t.get("trial_type") == sub_name]
                                sub_report = {"trials": sub_trials, "session_duration": session_duration}
                                with dpg.tab(label=sub_name.capitalize()):
                                    self._build_tracker_tab(name=sub_name.capitalize(), report=sub_report)
                else:
                    with dpg.tab(label=name):
                        self._build_tracker_tab(name=name, report=report)

    def _build_tracker_tab(self, name: str, report: dict) -> None:
        trials = report.get("trials", [])
        session_duration = report.get("session_duration", 0.0)

        stats = self._compute_stats(trials, session_duration)
        self._build_stats_section(name, stats)

        if trials:
            palette = Theme.palette
            with dpg.tab_bar():
                for plotter in PLOTTERS:
                    with dpg.tab(label=plotter.name) as tab:
                        plotter.plot(tab, trials, palette)

    @staticmethod
    def _compute_stats(trials: list[dict], session_duration: float) -> dict:
        successes = sum(1 for t in trials if t["outcome"] == "success")
        failures = sum(1 for t in trials if t["outcome"] == "failure")
        timeouts = sum(1 for t in trials if t["outcome"] == "timeout")
        total = len(trials)
        responses = successes + failures

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

    def _build_stats_section(self, name: str, stats: dict) -> None:
        palette = Theme.palette

        dpg.add_text(name, color=hex_to_rgba(palette.accent_primary))

        if stats["total_trials"] == 0:
            dpg.add_text("No trials recorded.", color=hex_to_rgba(palette.text_secondary))
            return

        with dpg.table(header_row=False, borders_innerH=False, borders_innerV=False):
            dpg.add_table_column()
            dpg.add_table_column()
            dpg.add_table_column(init_width_or_weight=20)
            dpg.add_table_column()
            dpg.add_table_column()

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
                ("", "", None),
            ]

            for (ll, lv, lc), (rl, rv, rc) in zip(left_items, right_items):
                with dpg.table_row():
                    dpg.add_text(ll, color=hex_to_rgba(palette.text_secondary))
                    t = dpg.add_text(lv)
                    if lc:
                        dpg.configure_item(t, color=hex_to_rgba(lc))
                    dpg.add_text("")  # spacer
                    dpg.add_text(rl, color=hex_to_rgba(palette.text_secondary))
                    t2 = dpg.add_text(rv)
                    if rc:
                        dpg.configure_item(t2, color=hex_to_rgba(rc))

        # Extra stats row
        dpg.add_separator()
        with dpg.group(horizontal=True):
            tpm = stats["trials_per_minute"]
            dpg.add_text("Trial Rate:", color=hex_to_rgba(palette.text_secondary))
            dpg.add_text(f"{tpm:.1f} trials/min" if tpm > 0 else "-")
            dpg.add_spacer(width=30)
            r20 = stats["rolling_accuracy_20"]
            dpg.add_text("Last 20 Accuracy:", color=hex_to_rgba(palette.text_secondary))
            dpg.add_text(f"{r20:.1f}%", color=hex_to_rgba(get_accuracy_color(r20)))
