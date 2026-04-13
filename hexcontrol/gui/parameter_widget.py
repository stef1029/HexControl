"""
Dynamic Parameter Form Builder (DearPyGui).

Automatically generates DPG input widgets from protocol parameter
definitions.  Handles creating appropriate widgets for each parameter
type, organising parameters into groups, validation, and value extraction.

Usage:
    parameters = MyProtocol.get_parameters()
    builder = ParameterFormBuilder(parent_id, parameters)
    builder.build()
    values = builder.get_values()
"""

from __future__ import annotations

from typing import Any

import dearpygui.dearpygui as dpg

from hexcontrol.core.parameter_types import (
    BoolParameter,
    ChoiceParameter,
    FloatParameter,
    IntParameter,
    Parameter,
    StringParameter,
)
from hexcontrol.gui.theme import Theme, hex_to_rgba


# =========================================================================
# Individual parameter widgets
# =========================================================================

class ParameterWidget:
    """Base class wrapping a DPG item for one parameter."""

    def __init__(self, parent: int | str, parameter: Parameter):
        self.parameter = parameter
        self.parent = parent
        self.item_id: int | None = None
        self.error_id: int | None = None
        self._group_id: int | None = None
        self._create_widgets()

    def _create_widgets(self) -> None:
        raise NotImplementedError

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError

    def show_error(self, message: str) -> None:
        if self.error_id is not None and dpg.does_item_exist(self.error_id):
            dpg.set_value(self.error_id, message)
            dpg.configure_item(self.error_id, color=hex_to_rgba(Theme.palette.error))

    def clear_error(self) -> None:
        if self.error_id is not None and dpg.does_item_exist(self.error_id):
            dpg.set_value(self.error_id, "")


class IntParameterWidget(ParameterWidget):

    def _create_widgets(self) -> None:
        param: IntParameter = self.parameter
        with dpg.group(parent=self.parent) as self._group_id:
            dpg.add_text(param.display_name,
                         color=hex_to_rgba(Theme.palette.text_secondary))
            from_val = param.min_value if param.min_value is not None else -999999
            to_val = param.max_value if param.max_value is not None else 999999
            self.item_id = dpg.add_input_int(
                label="", default_value=param.default,
                min_value=from_val, max_value=to_val,
                min_clamped=True, max_clamped=True,
                step=param.step, width=-1,
            )
            if param.description:
                dpg.add_text(f"({param.description})", wrap=0,
                             color=hex_to_rgba(Theme.palette.text_disabled))
            self.error_id = dpg.add_text("", color=hex_to_rgba(Theme.palette.error))

    def get_value(self) -> int:
        return dpg.get_value(self.item_id)

    def set_value(self, value: int) -> None:
        dpg.set_value(self.item_id, value)


class FloatParameterWidget(ParameterWidget):

    def _create_widgets(self) -> None:
        param: FloatParameter = self.parameter
        with dpg.group(parent=self.parent) as self._group_id:
            dpg.add_text(param.display_name,
                         color=hex_to_rgba(Theme.palette.text_secondary))
            from_val = param.min_value if param.min_value is not None else -999999.0
            to_val = param.max_value if param.max_value is not None else 999999.0
            fmt = f"%.{param.precision}f"
            self.item_id = dpg.add_input_float(
                label="", default_value=param.default,
                min_value=from_val, max_value=to_val,
                min_clamped=True, max_clamped=True,
                step=param.step, format=fmt, width=-1,
            )
            if param.description:
                dpg.add_text(f"({param.description})", wrap=0,
                             color=hex_to_rgba(Theme.palette.text_disabled))
            self.error_id = dpg.add_text("", color=hex_to_rgba(Theme.palette.error))

    def get_value(self) -> float:
        return dpg.get_value(self.item_id)

    def set_value(self, value: float) -> None:
        dpg.set_value(self.item_id, value)


class BoolParameterWidget(ParameterWidget):

    def _create_widgets(self) -> None:
        param: BoolParameter = self.parameter
        with dpg.group(parent=self.parent) as self._group_id:
            self.item_id = dpg.add_checkbox(
                label=param.display_name,
                default_value=param.default,
            )
            if param.description:
                dpg.add_text(f"({param.description})", wrap=0,
                             color=hex_to_rgba(Theme.palette.text_disabled))
            self.error_id = dpg.add_text("", color=hex_to_rgba(Theme.palette.error))

    def get_value(self) -> bool:
        return dpg.get_value(self.item_id)

    def set_value(self, value: bool) -> None:
        dpg.set_value(self.item_id, value)


class ChoiceParameterWidget(ParameterWidget):

    def _create_widgets(self) -> None:
        param: ChoiceParameter = self.parameter
        with dpg.group(parent=self.parent) as self._group_id:
            dpg.add_text(param.display_name,
                         color=hex_to_rgba(Theme.palette.text_secondary))
            self.item_id = dpg.add_combo(
                label="",
                items=list(param.choices),
                default_value=param.default,
                width=-1,
            )
            if param.description:
                dpg.add_text(f"({param.description})", wrap=0,
                             color=hex_to_rgba(Theme.palette.text_disabled))
            self.error_id = dpg.add_text("", color=hex_to_rgba(Theme.palette.error))

    def get_value(self) -> str:
        return dpg.get_value(self.item_id)

    def set_value(self, value: str) -> None:
        dpg.set_value(self.item_id, value)


class StringParameterWidget(ParameterWidget):

    def _create_widgets(self) -> None:
        param: StringParameter = self.parameter
        with dpg.group(parent=self.parent) as self._group_id:
            dpg.add_text(param.display_name,
                         color=hex_to_rgba(Theme.palette.text_secondary))
            self.item_id = dpg.add_input_text(
                label="",
                default_value=param.default,
                width=-1,
            )
            if param.description:
                dpg.add_text(f"({param.description})", wrap=0,
                             color=hex_to_rgba(Theme.palette.text_disabled))
            self.error_id = dpg.add_text("", color=hex_to_rgba(Theme.palette.error))

    def get_value(self) -> str:
        return dpg.get_value(self.item_id)

    def set_value(self, value: str) -> None:
        dpg.set_value(self.item_id, value)


# =========================================================================
# Form builder
# =========================================================================

class ParameterFormBuilder:
    """Builds a complete parameter input form inside a DPG parent container."""

    def __init__(self, parent: int | str, parameters: list[Parameter]):
        self.parent = parent
        self.parameters = parameters
        self.widgets: dict[str, ParameterWidget] = {}
        self._group_id: int | None = None

    def build(self) -> int:
        """Build the form inside *self.parent* and return the group ID."""
        # Clear existing
        if self._group_id is not None and dpg.does_item_exist(self._group_id):
            dpg.delete_item(self._group_id)
        self.widgets.clear()

        self._group_id = dpg.add_group(parent=self.parent)

        # Group parameters
        groups: dict[str, list[Parameter]] = {}
        for param in self.parameters:
            group = param.group or "General"
            groups.setdefault(group, []).append(param)

        for group in groups.values():
            group.sort(key=lambda p: p.order)

        # Build widgets
        for group_name, group_params in groups.items():
            header = dpg.add_collapsing_header(
                label=group_name, default_open=True, closable=False,
                parent=self._group_id,
            )
            for param in group_params:
                widget = self._create_widget(header, param)
                self.widgets[param.name] = widget

        return self._group_id

    def _create_widget(self, parent: int | str, parameter: Parameter) -> ParameterWidget:
        if isinstance(parameter, IntParameter):
            return IntParameterWidget(parent, parameter)
        elif isinstance(parameter, FloatParameter):
            return FloatParameterWidget(parent, parameter)
        elif isinstance(parameter, BoolParameter):
            return BoolParameterWidget(parent, parameter)
        elif isinstance(parameter, ChoiceParameter):
            return ChoiceParameterWidget(parent, parameter)
        elif isinstance(parameter, StringParameter):
            return StringParameterWidget(parent, parameter)
        else:
            raise ValueError(f"Unknown parameter type: {type(parameter).__name__}")

    def get_values(self) -> dict[str, Any]:
        return {name: w.get_value() for name, w in self.widgets.items()}

    def set_values(self, values: dict[str, Any]) -> None:
        for name, value in values.items():
            if name in self.widgets:
                self.widgets[name].set_value(value)

    def validate(self) -> tuple[bool, dict[str, str]]:
        errors = {}
        values = self.get_values()
        for widget in self.widgets.values():
            widget.clear_error()
        for param in self.parameters:
            if param.name not in values:
                errors[param.name] = "Missing value"
                continue
            is_valid, error_msg = param.validate(values[param.name])
            if not is_valid:
                errors[param.name] = error_msg
                self.widgets[param.name].show_error(error_msg)
        return len(errors) == 0, errors

    def get_converted_values(self) -> dict[str, Any]:
        is_valid, errors = self.validate()
        if not is_valid:
            raise ValueError(f"Parameter validation failed: {errors}")
        values = self.get_values()
        converted = {}
        for param in self.parameters:
            if param.name in values:
                converted[param.name] = param.convert(values[param.name])
            else:
                converted[param.name] = param.default
        return converted

    def reset_to_defaults(self) -> None:
        for param in self.parameters:
            if param.name in self.widgets:
                self.widgets[param.name].set_value(param.default)
                self.widgets[param.name].clear_error()
