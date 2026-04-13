"""
Running Mode - Monitor an active session (DearPyGui).

Shows:
    - Session summary (protocol, mouse, save path)
    - Performance stats (accuracy, rolling accuracy)
    - Elapsed timer
    - Status indicator
    - Trial log (colored)
    - Live scales plot
    - Session event log
    - Stop button
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import dearpygui.dearpygui as dpg

from hexcontrol.core.protocol_base import ProtocolStatus
from hexcontrol.gui.dpg_app import frame_poller
from hexcontrol.gui.theme import Theme, hex_to_rgba, get_accuracy_color
from hexcontrol.gui.scales_plot_widget import ScalesPlotWidget


_MAX_LOG_LINES = 2000


class RunningMode:
    """Running mode — shows session progress, logging, and stop button."""

    def __init__(self, parent: int | str, on_stop: Callable[[], None]):
        self._parent = parent
        self._on_stop = on_stop
        self._start_time: datetime | None = None
        self._tracker_widgets: dict[str, dict] = {}
        self._tracker_definitions: list = []
        self._tracker_tab_indices: dict[str, int] = {}
        self._last_logged_trials: dict[str, int] = {}
        self._perf_tab_bar: int | None = None
        self._lock_tracker_view: bool = False
        self._daq_view_proc: subprocess.Popen | None = None
        self._rig_number: int = 0
        self._log_line_count: int = 0
        self._trial_log_line_count: int = 0

        # DPG IDs
        self._window_id: int | None = None
        self._timer_text: int | None = None
        self._status_text: int | None = None
        self._stop_btn: int | None = None
        self._daq_btn: int | None = None
        self._summary_labels: dict[str, int] = {}
        self._perf_container: int | None = None
        self._trial_log: int | None = None
        self._session_log: int | None = None
        self._scales_plot: ScalesPlotWidget | None = None
        self._lock_checkbox: int | None = None

        self._build()

    def _build(self) -> None:
        palette = Theme.palette
        self._window_id = dpg.add_group(parent=self._parent, show=False)
        root = self._window_id

        # --- Session Summary ---
        with dpg.collapsing_header(label="Session", default_open=True, parent=root):
            for key, label_text in [("protocol", "Protocol:"), ("mouse", "Mouse:"), ("save_path", "Saving to:")]:
                with dpg.group(horizontal=True):
                    dpg.add_text(label_text, color=hex_to_rgba(palette.text_secondary))
                    self._summary_labels[key] = dpg.add_text("")

        # --- Performance ---
        with dpg.collapsing_header(label="Performance", default_open=True, parent=root):
            self._perf_container = dpg.add_group()

        # --- Trial Log ---
        with dpg.collapsing_header(label="Trial Log", default_open=True, parent=root):
            self._trial_log = dpg.add_child_window(height=200)

        # --- Scales Plot ---
        with dpg.collapsing_header(label="Scales", default_open=True, parent=root):
            scales_container = dpg.add_child_window(height=180)
            self._scales_plot = ScalesPlotWidget(scales_container)

        # --- Session Log ---
        with dpg.collapsing_header(label="Session Log", default_open=True, parent=root):
            self._session_log = dpg.add_child_window(height=120)

        # --- Timer + Status ---
        dpg.add_separator(parent=root)
        with dpg.group(horizontal=True, parent=root):
            dpg.add_text("Elapsed:", color=hex_to_rgba(palette.text_secondary))
            self._timer_text = dpg.add_text("00:00:00",
                                            color=hex_to_rgba(palette.success))
            dpg.add_spacer(width=40)
            self._status_text = dpg.add_text("RUNNING",
                                             color=hex_to_rgba(palette.success))

        # --- Buttons ---
        with dpg.group(horizontal=True, parent=root):
            self._daq_btn = dpg.add_button(
                label="DAQ View", callback=lambda: self._toggle_daq_view(),
            )
            self._stop_btn = dpg.add_button(
                label="Stop Session", callback=lambda: self._on_stop_clicked(),
            )
            if Theme.danger_button_theme:
                dpg.bind_item_theme(self._stop_btn, Theme.danger_button_theme)

    # ----- Scales -----

    def set_scales_client(self, client) -> None:
        if self._scales_plot:
            self._scales_plot.set_scales_client(client)

    def set_scales_threshold(self, value) -> None:
        if self._scales_plot:
            self._scales_plot.set_threshold(value)

    def set_battery_detection(self, enabled: bool) -> None:
        if self._scales_plot:
            self._scales_plot.set_battery_detection(enabled)

    # ----- Activation -----

    def activate(self, session_config: dict, tracker_definitions=None, rig_number: int = 0) -> None:
        self._rig_number = rig_number
        self._clear_log()
        self._log_line_count = 0
        self._trial_log_line_count = 0

        if self._stop_btn and dpg.does_item_exist(self._stop_btn):
            dpg.configure_item(self._stop_btn, enabled=True, label="Stop Session")

        for key, text_id in self._summary_labels.items():
            if dpg.does_item_exist(text_id):
                dpg.set_value(text_id, session_config.get(key.replace("save_path", "save_path"), ""))
        # Set specific keys
        if dpg.does_item_exist(self._summary_labels.get("protocol", 0)):
            dpg.set_value(self._summary_labels["protocol"], session_config.get("protocol_name", ""))
        if dpg.does_item_exist(self._summary_labels.get("mouse", 0)):
            dpg.set_value(self._summary_labels["mouse"], session_config.get("mouse_id", ""))
        if dpg.does_item_exist(self._summary_labels.get("save_path", 0)):
            dpg.set_value(self._summary_labels["save_path"], session_config.get("save_path", ""))

        self._tracker_definitions = tracker_definitions or []
        self._build_performance_tabs()

        self._start_time = None
        if self._timer_text and dpg.does_item_exist(self._timer_text):
            dpg.set_value(self._timer_text, "00:00:00")

        if self._scales_plot:
            self._scales_plot.start()

    def _build_performance_tabs(self) -> None:
        palette = Theme.palette
        if self._perf_container and dpg.does_item_exist(self._perf_container):
            for child in dpg.get_item_children(self._perf_container, 1) or []:
                dpg.delete_item(child)
        self._tracker_widgets.clear()
        self._tracker_tab_indices.clear()
        self._last_logged_trials.clear()
        self._perf_tab_bar = None
        self._lock_tracker_view = False

        # Clear trial log
        if self._trial_log and dpg.does_item_exist(self._trial_log):
            for child in dpg.get_item_children(self._trial_log, 1) or []:
                dpg.delete_item(child)
            self._trial_log_line_count = 0

        if not self._tracker_definitions:
            dpg.add_text("No performance trackers defined",
                         parent=self._perf_container,
                         color=hex_to_rgba(palette.text_secondary))
            return

        # Lock checkbox
        self._lock_checkbox = dpg.add_checkbox(
            label="Lock view", default_value=False,
            parent=self._perf_container,
            callback=lambda s, a: setattr(self, '_lock_tracker_view', a),
        )

        self._perf_tab_bar = dpg.add_tab_bar(parent=self._perf_container)

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
                outer_tab = dpg.add_tab(label=tdef.display_name, parent=self._perf_tab_bar)
                self._tracker_tab_indices[tdef.name] = idx

                inner_nb = dpg.add_tab_bar(parent=outer_tab)
                overall_tab = dpg.add_tab(label="Overall", parent=inner_nb)
                overall_widgets = self._create_tracker_tab(overall_tab, "Overall")

                sub_widgets = {}
                for sub_name in sub_trackers:
                    sub_tab = dpg.add_tab(label=sub_name.capitalize(), parent=inner_nb)
                    sub_widgets[sub_name] = self._create_tracker_tab(sub_tab, sub_name.capitalize())

                self._tracker_widgets[tdef.name] = {
                    "_overall": overall_widgets,
                    "_sub": sub_widgets,
                    "_inner_nb": inner_nb,
                }
                self._last_logged_trials[tdef.name] = 0
            else:
                tab = dpg.add_tab(label=tdef.display_name, parent=self._perf_tab_bar)
                widgets = self._create_tracker_tab(tab, tdef.display_name)
                self._tracker_widgets[tdef.name] = widgets
                self._tracker_tab_indices[tdef.name] = idx
                self._last_logged_trials[tdef.name] = 0

    def _create_tracker_tab(self, parent: int | str, display_name: str = "") -> dict:
        palette = Theme.palette

        name_label = dpg.add_text(display_name, parent=parent,
                                  color=hex_to_rgba(palette.accent_primary))

        with dpg.group(horizontal=True, parent=parent):
            dpg.add_text("Trials:", color=hex_to_rgba(palette.text_secondary))
            trials_label = dpg.add_text("0", color=hex_to_rgba(palette.accent_primary))
            dpg.add_spacer(width=16)
            dpg.add_text("Accuracy:", color=hex_to_rgba(palette.text_secondary))
            accuracy_label = dpg.add_text("--", color=hex_to_rgba(palette.info))
            dpg.add_spacer(width=16)
            dpg.add_text("Last", color=hex_to_rgba(palette.text_secondary))
            rolling_n_combo = dpg.add_combo(
                items=["5", "10", "20", "50", "100"],
                default_value="20", width=60,
            )
            dpg.add_text(":", color=hex_to_rgba(palette.text_secondary))
            rolling_label = dpg.add_text("--", color=hex_to_rgba(palette.accent_secondary))

        with dpg.group(horizontal=True, parent=parent):
            dpg.add_text("Correct:", color=hex_to_rgba(palette.text_secondary))
            correct_label = dpg.add_text("0", color=hex_to_rgba(palette.success))
            dpg.add_spacer(width=14)
            dpg.add_text("Incorrect:", color=hex_to_rgba(palette.text_secondary))
            incorrect_label = dpg.add_text("0", color=hex_to_rgba(palette.error))
            dpg.add_spacer(width=14)
            dpg.add_text("Timeouts:", color=hex_to_rgba(palette.text_secondary))
            timeout_label = dpg.add_text("0", color=hex_to_rgba(palette.warning))

        return {
            "trials": trials_label,
            "accuracy": accuracy_label,
            "rolling_n_combo": rolling_n_combo,
            "rolling": rolling_label,
            "correct": correct_label,
            "incorrect": incorrect_label,
            "timeout": timeout_label,
        }

    # ----- Stimulus / Performance / Log -----

    def log_stimulus(self, target_port: int) -> None:
        palette = Theme.palette
        line = f"-> Stimulus ON - Target port {target_port}"
        self._append_trial_log(line, palette.info)

    def update_performance(self, trackers=None, updated: str = "") -> None:
        if trackers is None or updated not in self._tracker_widgets or updated not in trackers:
            return

        tracker = trackers[updated]
        w = self._tracker_widgets[updated]
        palette = Theme.palette

        if "_overall" in w:
            self._update_tracker_widgets(w["_overall"], tracker, palette)
            for sub_name, sub_widgets in w["_sub"].items():
                sub = tracker.get_sub_tracker(sub_name)
                if sub is not None:
                    self._update_tracker_widgets(sub_widgets, sub, palette)
        else:
            self._update_tracker_widgets(w, tracker, palette)

        # Log new trials
        last = self._last_logged_trials.get(updated, 0)
        all_trials = tracker.get_all_trials()
        new_trials = all_trials[last:]
        multi = len(self._tracker_widgets) > 1
        display_name = tracker.display_name
        for trial in new_trials:
            self._log_trial(trial, prefix=f"[{display_name}] " if multi else "")
            self._last_logged_trials[updated] = last + 1
            last += 1

        # Auto-switch tab
        if (
            not self._lock_tracker_view
            and self._perf_tab_bar is not None
            and dpg.does_item_exist(self._perf_tab_bar)
            and updated in self._tracker_tab_indices
        ):
            tabs = dpg.get_item_children(self._perf_tab_bar, 1)
            if tabs:
                idx = self._tracker_tab_indices[updated]
                if idx < len(tabs):
                    dpg.set_value(self._perf_tab_bar, tabs[idx])

    def _update_tracker_widgets(self, w: dict, tracker, palette) -> None:
        _set_text(w["trials"], str(tracker.total_trials))
        _set_text(w["correct"], str(tracker.successes))
        _set_text(w["incorrect"], str(tracker.failures))
        _set_text(w["timeout"], str(tracker.timeouts))

        if tracker.responses > 0:
            acc = tracker.accuracy
            _set_text(w["accuracy"], f"{acc:.0f}%")
            if dpg.does_item_exist(w["accuracy"]):
                dpg.configure_item(w["accuracy"], color=hex_to_rgba(get_accuracy_color(acc)))
        else:
            _set_text(w["accuracy"], "--")

        if tracker.total_trials > 0:
            try:
                n = int(dpg.get_value(w["rolling_n_combo"]))
            except (ValueError, TypeError):
                n = 20
            rolling = tracker.rolling_accuracy(n)
            _set_text(w["rolling"], f"{rolling:.0f}%")
        else:
            _set_text(w["rolling"], "--")

    def _log_trial(self, trial, prefix: str = "") -> None:
        from core.tracker import TrialOutcome
        palette = Theme.palette

        trial_num = trial.trial_number
        outcome = trial.outcome
        correct_port = trial.correct_port
        chosen_port = trial.chosen_port
        duration = trial.trial_duration

        if outcome == TrialOutcome.SUCCESS:
            line = f"{prefix}Trial {trial_num}: CORRECT - Port {correct_port} ({duration:.2f}s)"
            color = palette.success
        elif outcome == TrialOutcome.FAILURE:
            line = f"{prefix}Trial {trial_num}: WRONG - Chose port {chosen_port}, correct was {correct_port} ({duration:.2f}s)"
            color = palette.error
        else:
            line = f"{prefix}Trial {trial_num}: TIMEOUT - Correct was port {correct_port} ({duration:.2f}s)"
            color = palette.warning

        self._append_trial_log(line, color)

    def _append_trial_log(self, text: str, color_hex: str) -> None:
        if self._trial_log and dpg.does_item_exist(self._trial_log):
            dpg.add_text(text, parent=self._trial_log, color=hex_to_rgba(color_hex))
            self._trial_log_line_count += 1
            if self._trial_log_line_count > _MAX_LOG_LINES:
                children = dpg.get_item_children(self._trial_log, 1)
                if children:
                    dpg.delete_item(children[0])
                    self._trial_log_line_count -= 1
            dpg.set_y_scroll(self._trial_log, dpg.get_y_scroll_max(self._trial_log))

    def log_message(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        palette = Theme.palette
        if self._session_log and dpg.does_item_exist(self._session_log):
            dpg.add_text(log_line, parent=self._session_log,
                         color=hex_to_rgba(palette.text_primary))
            self._log_line_count += 1
            if self._log_line_count > _MAX_LOG_LINES:
                children = dpg.get_item_children(self._session_log, 1)
                if children:
                    dpg.delete_item(children[0])
                    self._log_line_count -= 1
            dpg.set_y_scroll(self._session_log, dpg.get_y_scroll_max(self._session_log))

    # ----- Timer -----

    def _update_timer(self) -> None:
        if self._start_time:
            elapsed = datetime.now() - self._start_time
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if self._timer_text and dpg.does_item_exist(self._timer_text):
                dpg.set_value(self._timer_text, f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def start_timer(self) -> None:
        self._start_time = datetime.now()
        frame_poller.register(1000, self._update_timer)

    def stop_timer(self) -> None:
        frame_poller.unregister(self._update_timer)

    def stop_scales_plot(self) -> None:
        if self._scales_plot:
            self._scales_plot.stop()

    def get_elapsed_time(self) -> float:
        if self._start_time:
            return (datetime.now() - self._start_time).total_seconds()
        return 0.0

    # ----- Status -----

    def set_status(self, status: ProtocolStatus) -> None:
        palette = Theme.palette
        status_config = {
            ProtocolStatus.IDLE: ("IDLE", palette.text_secondary),
            ProtocolStatus.RUNNING: ("RUNNING", palette.success),
            ProtocolStatus.COMPLETED: ("COMPLETED", "#1e8449"),
            ProtocolStatus.STOPPED: ("STOPPED", palette.warning),
            ProtocolStatus.ERROR: ("ERROR", palette.error),
        }
        text, color = status_config.get(status, ("UNKNOWN", palette.text_primary))
        _set_text(self._status_text, text)
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.configure_item(self._status_text, color=hex_to_rgba(color))
        if self._timer_text and dpg.does_item_exist(self._timer_text):
            dpg.configure_item(self._timer_text, color=hex_to_rgba(color))

    def set_stopping(self) -> None:
        palette = Theme.palette
        if self._stop_btn and dpg.does_item_exist(self._stop_btn):
            dpg.configure_item(self._stop_btn, enabled=False, label="Stopping...")
        _set_text(self._status_text, "STOPPING")
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.configure_item(self._status_text, color=hex_to_rgba(palette.warning))

    # ----- Deactivate -----

    def deactivate(self) -> dict:
        self.stop_timer()
        if self._scales_plot:
            self._scales_plot.stop()
        self._close_daq_view()
        return {"elapsed_time": self.get_elapsed_time()}

    def _clear_log(self) -> None:
        if self._session_log and dpg.does_item_exist(self._session_log):
            for child in dpg.get_item_children(self._session_log, 1) or []:
                dpg.delete_item(child)

    # ----- DAQ View -----

    def _toggle_daq_view(self) -> None:
        if self._daq_view_proc is not None and self._daq_view_proc.poll() is None:
            return
        script = Path(__file__).resolve().parents[1] / "daq_view_subprocess.py"
        self._daq_view_proc = subprocess.Popen(
            [sys.executable, str(script), str(self._rig_number)],
        )

    def _close_daq_view(self) -> None:
        if self._daq_view_proc is not None:
            if self._daq_view_proc.poll() is None:
                self._daq_view_proc.terminate()
            self._daq_view_proc = None

    def _on_stop_clicked(self) -> None:
        if self._on_stop:
            self._on_stop()

    # ----- Show / hide -----

    def show(self) -> None:
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=True)

    def hide(self) -> None:
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=False)


# =========================================================================
# Helpers
# =========================================================================

def _set_text(item_id: int | None, text: str) -> None:
    if item_id is not None and dpg.does_item_exist(item_id):
        dpg.set_value(item_id, text)
