"""
Dynamic Parameter Form Builder.

This module provides functionality to automatically generate GUI input
widgets from protocol parameter definitions. It handles:
    - Creating appropriate widgets for each parameter type
    - Organising parameters into groups
    - Validation and error display
    - Extracting values from the form

The ParameterFormBuilder class is the main entry point. Given a list of
Parameter objects, it creates a tkinter frame containing all necessary
input widgets.

Example Usage:
    parameters = MyProtocol.get_parameters()
    builder = ParameterFormBuilder(parent_frame, parameters)
    builder.build()

    # Later, to get values:
    values = builder.get_values()
    is_valid, errors = builder.validate()
"""

import tkinter as tk
from tkinter import ttk
from typing import Any

from core.parameter_types import (
    BoolParameter,
    ChoiceParameter,
    FloatParameter,
    IntParameter,
    Parameter,
)
from gui.theme import Theme


class ParameterWidget:
    """
    Base class for parameter input widgets.

    Each parameter type has a corresponding widget class that handles
    creating the appropriate tkinter widget and getting/setting values.

    Attributes:
        parameter: The parameter definition this widget represents.
        frame: The frame containing the widget.
        variable: The tkinter variable holding the widget's value.
    """

    def __init__(self, parent: tk.Widget, parameter: Parameter):
        """
        Initialise the parameter widget.

        Args:
            parent: Parent tkinter widget.
            parameter: The parameter definition.
        """
        self.parameter = parameter
        self.frame = ttk.Frame(parent)
        self.variable: tk.Variable = None
        self.error_label: ttk.Label = None

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create the widget components. Override in subclasses."""
        raise NotImplementedError

    def get_value(self) -> Any:
        """Get the current value from the widget."""
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        """Set the widget's value."""
        raise NotImplementedError

    def show_error(self, message: str) -> None:
        """Display an error message below the widget."""
        if self.error_label is not None:
            palette = Theme.palette
            self.error_label.config(text=message, foreground=palette.error)

    def clear_error(self) -> None:
        """Clear any error message."""
        if self.error_label is not None:
            self.error_label.config(text="")

    def pack(self, **kwargs) -> None:
        """Pack the widget frame."""
        self.frame.pack(**kwargs)

    def grid(self, **kwargs) -> None:
        """Grid the widget frame."""
        self.frame.grid(**kwargs)


class IntParameterWidget(ParameterWidget):
    """Widget for integer parameters using a spinbox."""

    def __init__(self, parent: tk.Widget, parameter: IntParameter):
        """Initialise the integer parameter widget."""
        super().__init__(parent, parameter)

    def _create_widgets(self) -> None:
        """Create label, spinbox, and error label."""
        param: IntParameter = self.parameter
        palette = Theme.palette

        # Label
        label = ttk.Label(self.frame, text=param.display_name + ":")
        label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Spinbox
        self.variable = tk.IntVar(value=param.default)

        from_val = param.min_value if param.min_value is not None else -999999
        to_val = param.max_value if param.max_value is not None else 999999

        self.spinbox = ttk.Spinbox(
            self.frame,
            from_=from_val,
            to=to_val,
            increment=param.step,
            textvariable=self.variable,
            width=16,
        )
        self.spinbox.grid(row=0, column=1, sticky="w")

        # Tooltip (description)
        if param.description:
            tooltip_label = ttk.Label(
                self.frame,
                text=f"({param.description})",
                style="Muted.TLabel",
            )
            tooltip_label.grid(row=1, column=0, columnspan=2, sticky="w")

        # Error label
        self.error_label = ttk.Label(
            self.frame, text="", 
            foreground=palette.error,
            font=Theme.font_small()
        )
        self.error_label.grid(row=2, column=0, columnspan=2, sticky="w")

    def get_value(self) -> int:
        """Get the current integer value."""
        try:
            return self.variable.get()
        except tk.TclError:
            # Handle case where spinbox contains invalid text
            return self.parameter.default

    def set_value(self, value: int) -> None:
        """Set the spinbox value."""
        self.variable.set(value)


class FloatParameterWidget(ParameterWidget):
    """Widget for floating-point parameters using a spinbox."""

    def __init__(self, parent: tk.Widget, parameter: FloatParameter):
        """Initialise the float parameter widget."""
        super().__init__(parent, parameter)

    def _create_widgets(self) -> None:
        """Create label, spinbox, and error label."""
        param: FloatParameter = self.parameter
        palette = Theme.palette

        # Label
        label = ttk.Label(self.frame, text=param.display_name + ":")
        label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Spinbox
        self.variable = tk.DoubleVar(value=param.default)

        from_val = param.min_value if param.min_value is not None else -999999.0
        to_val = param.max_value if param.max_value is not None else 999999.0

        self.spinbox = ttk.Spinbox(
            self.frame,
            from_=from_val,
            to=to_val,
            increment=param.step,
            textvariable=self.variable,
            width=16,
            format=f"%.{param.precision}f",
        )
        self.spinbox.grid(row=0, column=1, sticky="w")

        # Tooltip (description)
        if param.description:
            tooltip_label = ttk.Label(
                self.frame,
                text=f"({param.description})",
                style="Muted.TLabel",
            )
            tooltip_label.grid(row=1, column=0, columnspan=2, sticky="w")

        # Error label
        self.error_label = ttk.Label(
            self.frame, text="", 
            foreground=palette.error,
            font=Theme.font_small()
        )
        self.error_label.grid(row=2, column=0, columnspan=2, sticky="w")

    def get_value(self) -> float:
        """Get the current float value."""
        try:
            return self.variable.get()
        except tk.TclError:
            return self.parameter.default

    def set_value(self, value: float) -> None:
        """Set the spinbox value."""
        self.variable.set(value)


class BoolParameterWidget(ParameterWidget):
    """Widget for boolean parameters using a checkbox."""

    def __init__(self, parent: tk.Widget, parameter: BoolParameter):
        """Initialise the boolean parameter widget."""
        super().__init__(parent, parameter)

    def _create_widgets(self) -> None:
        """Create checkbox and error label."""
        param: BoolParameter = self.parameter
        palette = Theme.palette

        # Checkbox
        self.variable = tk.BooleanVar(value=param.default)

        self.checkbox = ttk.Checkbutton(
            self.frame,
            text=param.display_name,
            variable=self.variable,
        )
        self.checkbox.grid(row=0, column=0, sticky="w")

        # Tooltip (description)
        if param.description:
            tooltip_label = ttk.Label(
                self.frame,
                text=f"({param.description})",
                style="Muted.TLabel",
            )
            tooltip_label.grid(row=1, column=0, sticky="w")

        # Error label (rarely used for booleans, but included for consistency)
        self.error_label = ttk.Label(
            self.frame, text="", 
            foreground=palette.error,
            font=Theme.font_small()
        )
        self.error_label.grid(row=2, column=0, sticky="w")

    def get_value(self) -> bool:
        """Get the current boolean value."""
        return self.variable.get()

    def set_value(self, value: bool) -> None:
        """Set the checkbox state."""
        self.variable.set(value)


class ChoiceParameterWidget(ParameterWidget):
    """Widget for choice parameters using a dropdown combobox."""

    def __init__(self, parent: tk.Widget, parameter: ChoiceParameter):
        """Initialise the choice parameter widget."""
        super().__init__(parent, parameter)

    def _create_widgets(self) -> None:
        """Create label, combobox, and error label."""
        param: ChoiceParameter = self.parameter
        palette = Theme.palette

        # Label
        label = ttk.Label(self.frame, text=param.display_name + ":")
        label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Combobox
        self.variable = tk.StringVar(value=param.default)

        self.combobox = ttk.Combobox(
            self.frame,
            textvariable=self.variable,
            values=param.choices,
            state="readonly",
            width=22,
        )
        self.combobox.grid(row=0, column=1, sticky="w")

        # Tooltip (description)
        if param.description:
            tooltip_label = ttk.Label(
                self.frame,
                text=f"({param.description})",
                style="Muted.TLabel",
            )
            tooltip_label.grid(row=1, column=0, columnspan=2, sticky="w")

        # Error label
        self.error_label = ttk.Label(
            self.frame, text="", 
            foreground=palette.error,
            font=Theme.font_small()
        )
        self.error_label.grid(row=2, column=0, columnspan=2, sticky="w")

    def get_value(self) -> str:
        """Get the currently selected value."""
        return self.variable.get()

    def set_value(self, value: str) -> None:
        """Set the selected value."""
        self.variable.set(value)


class ParameterFormBuilder:
    """
    Builds a complete parameter input form from parameter definitions.

    This class handles:
        - Creating appropriate widgets for each parameter type
        - Organising parameters into labelled groups
        - Sorting parameters by their 'order' attribute
        - Providing methods to get/validate all values

    Attributes:
        parent: The parent tkinter widget.
        parameters: List of parameter definitions.
        widgets: Dictionary mapping parameter names to their widgets.
    """

    def __init__(self, parent: tk.Widget, parameters: list[Parameter]):
        """
        Initialise the form builder.

        Args:
            parent: Parent tkinter widget to build the form in.
            parameters: List of parameter definitions.
        """
        self.parent = parent
        self.parameters = parameters
        self.widgets: dict[str, ParameterWidget] = {}

        # Main frame for the form
        self.frame = ttk.Frame(parent)

    def build(self) -> ttk.Frame:
        """
        Build the parameter form.

        Creates widgets for all parameters, organised into groups.

        Returns:
            The frame containing the complete form.
        """
        # Clear any existing widgets
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.widgets.clear()

        # Group parameters
        groups: dict[str, list[Parameter]] = {}
        for param in self.parameters:
            group = param.group or "General"
            if group not in groups:
                groups[group] = []
            groups[group].append(param)

        # Sort parameters within each group by order
        for group in groups.values():
            group.sort(key=lambda p: p.order)

        # Create widgets for each group
        row = 0
        for group_name, group_params in groups.items():
            # Group label frame
            group_frame = ttk.LabelFrame(
                self.frame, text=group_name, padding=(10, 6)
            )
            group_frame.grid(
                row=row, column=0, sticky="ew", padx=6, pady=5
            )
            self.frame.columnconfigure(0, weight=1)
            row += 1

            # Create widgets for each parameter in the group
            for param_idx, param in enumerate(group_params):
                widget = self._create_widget(group_frame, param)
                widget.grid(
                    row=param_idx, column=0, sticky="w", padx=6, pady=3
                )
                self.widgets[param.name] = widget

        return self.frame

    def _create_widget(
        self, parent: tk.Widget, parameter: Parameter
    ) -> ParameterWidget:
        """
        Create the appropriate widget for a parameter type.

        Args:
            parent: Parent widget.
            parameter: The parameter definition.

        Returns:
            The created ParameterWidget.
        """
        if isinstance(parameter, IntParameter):
            return IntParameterWidget(parent, parameter)
        elif isinstance(parameter, FloatParameter):
            return FloatParameterWidget(parent, parameter)
        elif isinstance(parameter, BoolParameter):
            return BoolParameterWidget(parent, parameter)
        elif isinstance(parameter, ChoiceParameter):
            return ChoiceParameterWidget(parent, parameter)
        else:
            raise ValueError(
                f"Unknown parameter type: {type(parameter).__name__}"
            )

    def get_values(self) -> dict[str, Any]:
        """
        Get all parameter values from the form.

        Returns:
            Dictionary mapping parameter names to their current values.
        """
        values = {}
        for name, widget in self.widgets.items():
            values[name] = widget.get_value()
        return values

    def set_values(self, values: dict[str, Any]) -> None:
        """
        Set parameter values in the form.

        Args:
            values: Dictionary mapping parameter names to values.
        """
        for name, value in values.items():
            if name in self.widgets:
                self.widgets[name].set_value(value)

    def validate(self) -> tuple[bool, dict[str, str]]:
        """
        Validate all parameter values.

        Returns:
            Tuple of (all_valid, errors) where errors is a dictionary
            mapping parameter names to error messages.
        """
        errors = {}
        values = self.get_values()

        # Clear all previous errors
        for widget in self.widgets.values():
            widget.clear_error()

        # Validate each parameter
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
        """
        Get all parameter values, converted to their appropriate types.

        Returns:
            Dictionary mapping parameter names to converted values.

        Raises:
            ValueError: If validation fails.
        """
        is_valid, errors = self.validate()
        if not is_valid:
            raise ValueError(
                f"Parameter validation failed: {errors}"
            )

        values = self.get_values()
        converted = {}

        for param in self.parameters:
            if param.name in values:
                converted[param.name] = param.convert(values[param.name])
            else:
                converted[param.name] = param.default

        return converted

    def reset_to_defaults(self) -> None:
        """Reset all parameters to their default values."""
        for param in self.parameters:
            if param.name in self.widgets:
                self.widgets[param.name].set_value(param.default)
                self.widgets[param.name].clear_error()

    def pack(self, **kwargs) -> None:
        """Pack the form frame."""
        self.frame.pack(**kwargs)

    def grid(self, **kwargs) -> None:
        """Grid the form frame."""
        self.frame.grid(**kwargs)
