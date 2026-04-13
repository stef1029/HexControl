"""
Setup Mode - Configure and start a new session (DearPyGui).

Shows:
    - Save location selection
    - Mouse ID selection
    - Protocol selection and parameter configuration
    - Start button
"""

import logging
from pathlib import Path
from typing import Callable

import dearpygui.dearpygui as dpg

from hexcontrol.core.protocol_base import BaseProtocol
from hexcontrol.protocols import get_available_protocols
from hexcontrol.gui.parameter_widget import ParameterFormBuilder
from hexcontrol.gui.theme import Theme, hex_to_rgba
from hexcontrol.gui.dpg_dialogs import show_error
from hexcontrol.simulation.mouse_parameters import MOUSE_PARAMETERS

logger = logging.getLogger(__name__)


# =========================================================================
# Protocol Tab
# =========================================================================

class ProtocolTab:
    """Content for a single protocol tab with description and parameters."""

    def __init__(self, parent: int | str, protocol_class: type[BaseProtocol]):
        self.protocol_class = protocol_class
        self.form_builder: ParameterFormBuilder | None = None
        self._build(parent)

    def _build(self, parent: int | str) -> None:
        palette = Theme.palette

        description = self.protocol_class.get_description()
        dpg.add_text(description, wrap=520, parent=parent,
                     color=hex_to_rgba(palette.text_secondary))
        dpg.add_separator(parent=parent)

        # Scrollable parameter area
        scroll = dpg.add_child_window(parent=parent, height=-40)
        parameters = self.protocol_class.get_parameters()
        self.form_builder = ParameterFormBuilder(scroll, parameters)
        self.form_builder.build()

        # Reset button
        btn = dpg.add_button(
            label="Reset to Defaults", parent=parent,
            callback=lambda: self._reset_to_defaults(),
        )
        if Theme.secondary_button_theme:
            dpg.bind_item_theme(btn, Theme.secondary_button_theme)

    def _reset_to_defaults(self) -> None:
        if self.form_builder:
            self.form_builder.reset_to_defaults()

    def get_parameters(self) -> dict:
        if self.form_builder is None:
            return {}
        return self.form_builder.get_converted_values()

    def validate(self) -> tuple[bool, dict[str, str]]:
        if self.form_builder is None:
            return True, {}
        return self.form_builder.validate()


# =========================================================================
# SetupMode
# =========================================================================

class SetupMode:
    """Setup mode — configure session parameters and start."""

    def __init__(
        self,
        parent: int | str,
        rig_config,
        on_start: Callable[[dict], None],
        claim_mouse_fn=None,
        get_claimed_mice_fn=None,
        cohort_folders: tuple = (),
        mice: tuple = (),
    ):
        self._parent = parent
        self._rig_config = rig_config
        self._on_start = on_start
        self._claim_mouse_fn = claim_mouse_fn
        self._get_claimed_mice_fn = get_claimed_mice_fn
        self._simulate = rig_config.simulate if rig_config else False
        self._cohort_folders_typed = cohort_folders
        self._mice_typed = mice
        self._cohort_folders: list[dict] = []
        self._mice: list[dict] = []
        self._mouse_form: ParameterFormBuilder | None = None
        self._mouse_buttons: dict[str, int] = {}
        self._cohort_buttons: dict[str, int] = {}
        self._mouse_default_cohorts: dict[str, str] = {}

        # State
        self._selected_cohort: str = ""
        self._selected_mouse: str = ""

        # DPG IDs
        self._window_id: int | None = None
        self._save_path_text: int | None = None
        self._mouse_weight_input: int | None = None
        self._num_trials_input: int | None = None
        self._max_duration_input: int | None = None
        self._tab_bar_id: int | None = None
        self.protocol_tabs: dict[str, ProtocolTab] = {}

        self._load_session_options()
        self._build()

    def _load_session_options(self) -> None:
        if self._cohort_folders_typed:
            self._cohort_folders = [
                {"name": c.name, "directory": c.directory, "description": c.description}
                for c in self._cohort_folders_typed
            ]
        else:
            self._cohort_folders = [{"name": "default", "directory": "D:\\behaviour_data\\default"}]

        if self._mice_typed:
            self._mice = [
                {"id": m.id, "description": m.description, "default_cohort": m.default_cohort}
                for m in self._mice_typed
            ]
        else:
            self._mice = [{"id": "test", "description": "Test mouse"}]

        self._mouse_default_cohorts = {
            m["id"]: m["default_cohort"]
            for m in self._mice
            if m.get("default_cohort")
        }

        if self._cohort_folders:
            self._selected_cohort = self._cohort_folders[0].get("name", "")
        if self._mice:
            self._selected_mouse = self._mice[0].get("id", "test")

    def _build(self) -> None:
        palette = Theme.palette

        self._window_id = dpg.add_group(parent=self._parent, show=False)

        # --- Session Info section ---
        with dpg.collapsing_header(label="Session Info", default_open=True,
                                   parent=self._window_id):

            # Save Location
            with dpg.collapsing_header(label="Save Location", default_open=True):
                for cohort in self._cohort_folders:
                    name = cohort.get("name", "Unknown")
                    directory = cohort.get("directory", "")
                    label = f"{name}  --  {directory}" if directory else name
                    btn = dpg.add_button(
                        label=label, width=-1,
                        callback=lambda s, a, u: self._select_cohort(u),
                        user_data=name,
                    )
                    self._cohort_buttons[name] = btn
                self._style_cohort_buttons()

            # Mouse ID
            with dpg.collapsing_header(label="Mouse ID", default_open=True):
                # 3-column grid
                with dpg.table(header_row=False):
                    dpg.add_table_column()
                    dpg.add_table_column()
                    dpg.add_table_column()

                    for i in range(0, len(self._mice), 3):
                        with dpg.table_row():
                            for j in range(3):
                                idx = i + j
                                if idx < len(self._mice):
                                    mouse = self._mice[idx]
                                    mouse_id = mouse.get("id", "Unknown")
                                    desc = mouse.get("description", "")
                                    label = f"{mouse_id}\n({desc})" if desc else mouse_id
                                    btn = dpg.add_button(
                                        label=label, width=-1,
                                        callback=lambda s, a, u: self._select_mouse(u),
                                        user_data=mouse_id,
                                    )
                                    self._mouse_buttons[mouse_id] = btn
                self._style_mouse_buttons()

            # Session Parameters
            with dpg.collapsing_header(label="Session Parameters", default_open=True):
                self._mouse_weight_input = dpg.add_input_float(
                    label="Mouse Weight (g)", default_value=18.0,
                    min_value=0.1, step=0.1, width=160,
                )
                self._num_trials_input = dpg.add_input_int(
                    label="Number of Trials", default_value=1000,
                    min_value=1, step=1, width=160,
                )
                self._max_duration_input = dpg.add_input_float(
                    label="Max Duration (min, 0=no limit)", default_value=0.0,
                    min_value=0.0, step=1.0, width=160,
                )

            # Save path preview
            with dpg.group(horizontal=True):
                dpg.add_text("Save to:", color=hex_to_rgba(palette.text_secondary))
                self._save_path_text = dpg.add_text(
                    "", color=hex_to_rgba(palette.accent_primary),
                )
            self._update_save_path_preview()

            # Simulated mouse settings
            if self._simulate:
                with dpg.collapsing_header(label="Simulated Mouse", default_open=True):
                    mouse_scroll = dpg.add_child_window(height=200)
                    self._mouse_form = ParameterFormBuilder(mouse_scroll, MOUSE_PARAMETERS)
                    self._mouse_form.build()

        # --- Protocol Tabs ---
        dpg.add_separator(parent=self._window_id)
        self._tab_bar_id = dpg.add_tab_bar(parent=self._window_id)

        for protocol_class in get_available_protocols():
            protocol_name = protocol_class.get_name()
            tab = dpg.add_tab(label=protocol_name, parent=self._tab_bar_id)
            protocol_tab = ProtocolTab(tab, protocol_class)
            self.protocol_tabs[protocol_name] = protocol_tab

        # --- Start button ---
        dpg.add_spacer(height=8, parent=self._window_id)
        start_btn = dpg.add_button(
            label="Start Session", parent=self._window_id,
            callback=lambda: self._on_start_clicked(),
            width=140,
        )
        if Theme.success_button_theme:
            dpg.bind_item_theme(start_btn, Theme.success_button_theme)

    # ----- Selection handlers -----

    def _select_cohort(self, name: str) -> None:
        self._selected_cohort = name
        self._style_cohort_buttons()
        self._update_save_path_preview()

    def _select_mouse(self, mouse_id: str) -> None:
        self._selected_mouse = mouse_id
        default_cohort = self._mouse_default_cohorts.get(mouse_id)
        if default_cohort and default_cohort in self._cohort_buttons:
            self._select_cohort(default_cohort)
        self._style_mouse_buttons()
        self._update_save_path_preview()

    def _style_cohort_buttons(self) -> None:
        palette = Theme.palette
        for name, btn_id in self._cohort_buttons.items():
            if not dpg.does_item_exist(btn_id):
                continue
            if name == self._selected_cohort:
                _apply_button_colors(btn_id, palette.accent_primary, palette.text_inverse)
            else:
                _apply_button_colors(btn_id, palette.bg_tertiary, palette.text_primary)

    def _style_mouse_buttons(self) -> None:
        palette = Theme.palette
        for mouse_id, btn_id in self._mouse_buttons.items():
            if not dpg.does_item_exist(btn_id):
                continue
            if mouse_id == self._selected_mouse:
                _apply_button_colors(btn_id, palette.accent_primary, palette.text_inverse)
            else:
                _apply_button_colors(btn_id, palette.bg_tertiary, palette.text_primary)

    def _update_save_path_preview(self) -> None:
        directory = self._get_selected_cohort_directory()
        mouse_id = self._selected_mouse
        if directory and mouse_id:
            preview = f"{directory}\\<datetime>\\<datetime>_{mouse_id}"
        else:
            preview = "<select save location>"
        if self._save_path_text and dpg.does_item_exist(self._save_path_text):
            dpg.set_value(self._save_path_text, preview)

    def _get_selected_cohort_directory(self) -> str:
        for cf in self._cohort_folders:
            if cf.get("name") == self._selected_cohort:
                return cf.get("directory", "")
        return ""

    # ----- Start -----

    def _on_start_clicked(self) -> None:
        tab = self.get_current_tab()

        # Validate session params
        try:
            mouse_weight = dpg.get_value(self._mouse_weight_input)
            if mouse_weight <= 0:
                raise ValueError("Mouse weight must be positive")
        except (ValueError, TypeError) as e:
            show_error("Validation Error", f"Invalid mouse weight: {e}")
            return

        try:
            num_trials = dpg.get_value(self._num_trials_input)
            if num_trials <= 0:
                raise ValueError("Number of trials must be positive")
        except (ValueError, TypeError) as e:
            show_error("Validation Error", f"Invalid number of trials: {e}")
            return

        try:
            max_duration = dpg.get_value(self._max_duration_input)
            if max_duration < 0:
                raise ValueError("Max duration cannot be negative")
        except (ValueError, TypeError) as e:
            show_error("Validation Error", f"Invalid max duration: {e}")
            return

        mouse_id = self._selected_mouse
        if self._claim_mouse_fn:
            rig_name = self._rig_config.name if self._rig_config else "Unknown"
            if not self._claim_mouse_fn(mouse_id, rig_name):
                claimed = self._get_claimed_mice_fn() if self._get_claimed_mice_fn else {}
                other_rig = claimed.get(mouse_id, "another rig")
                show_error("Mouse Already Selected",
                           f"Mouse '{mouse_id}' is already in use by {other_rig}.")
                return

        is_valid, errors = tab.validate()
        if not is_valid:
            error_msg = "\n".join(f"- {k}: {v}" for k, v in errors.items())
            show_error("Validation Error",
                       f"Please correct the following errors:\n{error_msg}")
            return

        protocol_params = tab.get_parameters()
        protocol_params["mouse_weight"] = mouse_weight
        protocol_params["num_trials"] = num_trials
        protocol_params["max_duration_minutes"] = max_duration
        protocol_params["mouse_id"] = mouse_id
        protocol_params["save_directory"] = self._get_selected_cohort_directory()

        mouse_params = None
        if self._mouse_form is not None:
            mouse_params = self._mouse_form.get_values()

        session_config = {
            "mouse_id": mouse_id,
            "save_directory": self._get_selected_cohort_directory(),
            "protocol_name": tab.protocol_class.get_name(),
            "protocol_class": tab.protocol_class,
            "parameters": protocol_params,
            "mouse_params": mouse_params,
        }
        self._on_start(session_config)

    def get_current_tab(self) -> ProtocolTab:
        """Get the currently selected protocol tab."""
        if self._tab_bar_id and dpg.does_item_exist(self._tab_bar_id):
            active_tab = dpg.get_value(self._tab_bar_id)
            if active_tab is not None:
                tab_label = dpg.get_item_label(active_tab)
                if tab_label in self.protocol_tabs:
                    return self.protocol_tabs[tab_label]
        # Fallback to first tab
        return next(iter(self.protocol_tabs.values()))

    # ----- Show / hide -----

    def show(self) -> None:
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=True)

    def hide(self) -> None:
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=False)


# =========================================================================
# Helper: per-widget button color themes
# =========================================================================

_button_theme_cache: dict[tuple, int] = {}


def _apply_button_colors(button_id: int, bg_hex: str, fg_hex: str) -> None:
    """Apply custom button colors via a cached per-color theme."""
    key = (bg_hex, fg_hex)
    if key not in _button_theme_cache:
        with dpg.theme() as t:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, hex_to_rgba(bg_hex))
                dpg.add_theme_color(dpg.mvThemeCol_Text, hex_to_rgba(fg_hex))
        _button_theme_cache[key] = t
    dpg.bind_item_theme(button_id, _button_theme_cache[key])
