"""
Post-Processing Window for Behaviour Rig System (DearPyGui).

Provides a GUI for batch processing cohort data including:
- Recovering crashed sessions
- Processing videos (binary/BMP to AVI)
- Running behavioral analysis

Uses a mode-based UI that switches between Configuration and Progress views.
"""

import logging
import sys
import threading
import multiprocessing as mp
from enum import Enum, auto
from pathlib import Path
from typing import Optional

import dearpygui.dearpygui as dpg

from .dpg_app import call_on_main_thread
from .dpg_dialogs import show_warning, show_info, ask_yes_no
from .theme import Theme, hex_to_rgba

logger = logging.getLogger(__name__)


class WindowMode(Enum):
    CONFIG = auto()
    PROGRESS = auto()


class PostProcessingWindow:
    """Window for post-processing cohort data."""

    def __init__(self, cohort_folders: tuple = ()):
        self._cohort_folders_typed = cohort_folders
        self.cohort_folders = self._load_cohort_folders()

        self.is_processing = False
        self.cancel_requested = False
        self.processing_thread: Optional[threading.Thread] = None

        self.cohort_vars: dict[str, bool] = {}
        self.cohort_checkboxes: dict[str, int] = {}
        self.recover_sessions = True
        self.process_videos = True
        self.run_analysis = True
        self.refresh_analysis = False

        # DPG IDs
        self._window_id: int | None = None
        self._config_group: int | None = None
        self._progress_group: int | None = None
        self._progress_label: int | None = None
        self._progress_bar: int | None = None
        self._log_container: int | None = None
        self._cancel_btn: int | None = None
        self._back_btn: int | None = None

        self._build()
        self._show_mode(WindowMode.CONFIG)

    def _load_cohort_folders(self) -> list[dict]:
        return [
            {"name": c.name, "directory": c.directory, "description": c.description}
            for c in self._cohort_folders_typed
        ]

    def _build(self) -> None:
        palette = Theme.palette

        self._window_id = dpg.add_window(
            label="Post-Processing", width=800, height=650,
            on_close=self._on_close,
        )

        # --- Config mode ---
        self._config_group = dpg.add_group(parent=self._window_id, show=True)

        dpg.add_text("Post-Processing", parent=self._config_group,
                     color=hex_to_rgba(palette.text_primary))
        if Theme.font_heading():
            dpg.bind_item_font(dpg.last_item(), Theme.font_heading())

        dpg.add_text("Select Cohorts to Process:",
                     parent=self._config_group,
                     color=hex_to_rgba(palette.text_secondary))

        cohort_scroll = dpg.add_child_window(
            height=160, parent=self._config_group,
        )

        if not self.cohort_folders:
            dpg.add_text("No cohort folders configured in rigs.yaml",
                         parent=cohort_scroll, color=hex_to_rgba(palette.error))
        else:
            for cohort in self.cohort_folders:
                name = cohort.get("name", "Unknown")
                directory = cohort.get("directory", "")
                self.cohort_vars[name] = True
                cb = dpg.add_checkbox(
                    label=f"{name} ({directory})",
                    default_value=True, parent=cohort_scroll,
                )
                self.cohort_checkboxes[name] = cb

        dpg.add_separator(parent=self._config_group)
        dpg.add_text("Processing Steps:", parent=self._config_group,
                     color=hex_to_rgba(palette.text_secondary))

        self._recover_cb = dpg.add_checkbox(
            label="Recover crashed sessions", default_value=True,
            parent=self._config_group,
        )
        self._video_cb = dpg.add_checkbox(
            label="Process videos (BMP/binary to AVI)", default_value=True,
            parent=self._config_group,
        )
        self._analysis_cb = dpg.add_checkbox(
            label="Run behavioral analysis", default_value=True,
            parent=self._config_group,
        )
        self._refresh_cb = dpg.add_checkbox(
            label="Refresh (reprocess already completed sessions)", default_value=False,
            parent=self._config_group,
        )

        with dpg.group(horizontal=True, parent=self._config_group):
            start_btn = dpg.add_button(
                label="Start Processing",
                callback=lambda: self._on_start_click(),
            )
            if Theme.primary_button_theme:
                dpg.bind_item_theme(start_btn, Theme.primary_button_theme)

            close_btn = dpg.add_button(
                label="Close",
                callback=lambda: self._on_close(),
            )
            if Theme.secondary_button_theme:
                dpg.bind_item_theme(close_btn, Theme.secondary_button_theme)

        # --- Progress mode ---
        self._progress_group = dpg.add_group(parent=self._window_id, show=False)

        dpg.add_text("Processing in Progress", parent=self._progress_group,
                     color=hex_to_rgba(palette.text_primary))
        if Theme.font_heading():
            dpg.bind_item_font(dpg.last_item(), Theme.font_heading())

        self._progress_label = dpg.add_text(
            "Ready to start processing", parent=self._progress_group,
            color=hex_to_rgba(palette.accent_primary),
        )
        self._progress_bar = dpg.add_progress_bar(
            default_value=0.0, width=-1, parent=self._progress_group,
        )

        dpg.add_text("Processing Log:", parent=self._progress_group,
                     color=hex_to_rgba(palette.text_secondary))
        self._log_container = dpg.add_child_window(
            height=350, parent=self._progress_group,
        )

        with dpg.group(horizontal=True, parent=self._progress_group):
            self._cancel_btn = dpg.add_button(
                label="Cancel",
                callback=lambda: self._on_cancel_click(),
            )
            if Theme.danger_button_theme:
                dpg.bind_item_theme(self._cancel_btn, Theme.danger_button_theme)

            self._back_btn = dpg.add_button(
                label="Back to Configuration",
                callback=lambda: self._show_mode(WindowMode.CONFIG),
                enabled=False,
            )
            if Theme.secondary_button_theme:
                dpg.bind_item_theme(self._back_btn, Theme.secondary_button_theme)

    def _show_mode(self, mode: WindowMode) -> None:
        if self._config_group and dpg.does_item_exist(self._config_group):
            dpg.configure_item(self._config_group, show=(mode == WindowMode.CONFIG))
        if self._progress_group and dpg.does_item_exist(self._progress_group):
            dpg.configure_item(self._progress_group, show=(mode == WindowMode.PROGRESS))

    def _on_start_click(self) -> None:
        # Read checkbox values
        selected = []
        for name, cb_id in self.cohort_checkboxes.items():
            if dpg.does_item_exist(cb_id) and dpg.get_value(cb_id):
                selected.append(name)

        if not selected:
            show_warning("No Cohorts Selected", "Please select at least one cohort.")
            return

        self.recover_sessions = dpg.get_value(self._recover_cb)
        self.process_videos = dpg.get_value(self._video_cb)
        self.run_analysis = dpg.get_value(self._analysis_cb)
        self.refresh_analysis = dpg.get_value(self._refresh_cb)

        if not (self.recover_sessions or self.process_videos or self.run_analysis):
            show_warning("No Steps Selected", "Please select at least one processing step.")
            return

        self._start_processing(selected)

    def _start_processing(self, selected_cohorts: list[str]) -> None:
        self.is_processing = True
        self.cancel_requested = False
        if self._cancel_btn and dpg.does_item_exist(self._cancel_btn):
            dpg.configure_item(self._cancel_btn, enabled=True)
        if self._back_btn and dpg.does_item_exist(self._back_btn):
            dpg.configure_item(self._back_btn, enabled=False)

        self._show_mode(WindowMode.PROGRESS)

        # Clear log
        if self._log_container and dpg.does_item_exist(self._log_container):
            for child in dpg.get_item_children(self._log_container, 1) or []:
                dpg.delete_item(child)

        self.processing_thread = threading.Thread(
            target=self._process_cohorts, args=(selected_cohorts,), daemon=True,
        )
        self.processing_thread.start()

    def _log(self, text: str, color: str | None = None) -> None:
        palette = Theme.palette
        c = hex_to_rgba(color or palette.text_primary)
        call_on_main_thread(self._append_log, text=text, color=c)

    def _append_log(self, text: str, color: list[int]) -> None:
        if self._log_container and dpg.does_item_exist(self._log_container):
            dpg.add_text(text, parent=self._log_container, color=color)
            dpg.set_y_scroll(self._log_container,
                             dpg.get_y_scroll_max(self._log_container))

    def _update_progress(self, message: str) -> None:
        call_on_main_thread(self._set_progress_label, message=message)

    def _set_progress_label(self, message: str) -> None:
        if self._progress_label and dpg.does_item_exist(self._progress_label):
            dpg.set_value(self._progress_label, message)

    def _process_cohorts(self, selected_cohorts: list[str]) -> None:
        palette = Theme.palette
        try:
            from behaviour_rig_system.post_processing.post_processing_pipeline import (
                recover_crashed_sessions, process_cohort_directory, run_analysis_on_local
            )

            cohort_dirs = {
                c.get("name"): {"directory": Path(c.get("directory"))}
                for c in self.cohort_folders
                if c.get("name") in selected_cohorts
            }

            total = len(cohort_dirs)
            for idx, (name, info) in enumerate(cohort_dirs.items(), 1):
                if self.cancel_requested:
                    self._log("Processing cancelled by user.", palette.warning)
                    break

                directory = info["directory"]
                self._update_progress(f"Processing cohort {idx}/{total}: {name}")
                self._log(f"\n{'=' * 60}", palette.accent_primary)
                self._log(f"COHORT: {name}", palette.accent_primary)
                self._log(f"DIRECTORY: {directory}", palette.success)

                if self.recover_sessions and not self.cancel_requested:
                    self._log("\n----- STEP 1: RECOVERING CRASHED SESSIONS -----", palette.info)
                    try:
                        recover_crashed_sessions(directory, verbose=True, force=False)
                    except Exception as e:
                        self._log(f"Error: {e}", palette.error)

                if self.process_videos and not self.cancel_requested:
                    self._log("\n----- STEP 2: PROCESSING VIDEOS -----", palette.info)
                    try:
                        process_cohort_directory(directory, num_processes=mp.cpu_count())
                    except Exception as e:
                        self._log(f"Error: {e}", palette.error)

                if self.run_analysis and not self.cancel_requested:
                    self._log("\n----- STEP 3: RUNNING ANALYSIS -----", palette.info)
                    try:
                        run_analysis_on_local(directory, refresh=self.refresh_analysis)
                    except Exception as e:
                        self._log(f"Error: {e}", palette.error)

            if not self.cancel_requested:
                self._log(f"\n{'=' * 60}", palette.success)
                self._log("ALL PROCESSING COMPLETE", palette.success)
                self._update_progress("Processing complete!")

        except Exception as e:
            self._log(f"\nFATAL ERROR: {e}", palette.error)
            self._update_progress("Processing failed")
        finally:
            call_on_main_thread(self._processing_complete)

    def _processing_complete(self) -> None:
        self.is_processing = False
        if self._cancel_btn and dpg.does_item_exist(self._cancel_btn):
            dpg.configure_item(self._cancel_btn, enabled=False)
        if self._back_btn and dpg.does_item_exist(self._back_btn):
            dpg.configure_item(self._back_btn, enabled=True)
        if not self.cancel_requested:
            show_info("Processing Complete",
                      "All selected cohorts have been processed.\nSee the log for details.")

    def _on_cancel_click(self) -> None:
        def do_cancel():
            self.cancel_requested = True
            if self._cancel_btn and dpg.does_item_exist(self._cancel_btn):
                dpg.configure_item(self._cancel_btn, enabled=False)
            self._update_progress("Cancelling...")

        ask_yes_no("Cancel Processing",
                   "Are you sure you want to cancel?\nThe current operation will finish first.",
                   on_yes=do_cancel)

    def _on_close(self) -> None:
        if self.is_processing:
            show_warning("Processing In Progress",
                         "Cannot close while processing. Cancel first.")
            return
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.delete_item(self._window_id)


def open_post_processing_window(cohort_folders: tuple = ()) -> None:
    """Open the post-processing window."""
    PostProcessingWindow(cohort_folders)
