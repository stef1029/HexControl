"""
Parameter Type Definitions for Behaviour Protocols.

This module defines the parameter types that protocols use to declare their
configurable settings. The GUI uses these definitions to automatically
generate appropriate input widgets.

Each parameter type includes metadata for:
    - Display name and description (for tooltips)
    - Default values
    - Validation constraints (min, max, allowed values)
    - GUI widget hints

Example Usage:
    class MyProtocol(BaseProtocol):
        @classmethod
        def get_parameters(cls) -> list[Parameter]:
            return [
                IntParameter(
                    name="trial_count",
                    display_name="Number of Trials",
                    description="Total trials to run in session",
                    default=100,
                    min_value=1,
                    max_value=1000,
                ),
                FloatParameter(
                    name="reward_volume",
                    display_name="Reward Volume (µL)",
                    description="Volume of reward per delivery",
                    default=5.0,
                    min_value=0.1,
                    max_value=50.0,
                ),
            ]
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class Parameter(ABC, Generic[T]):
    """
    Abstract base class for all parameter types.

    Attributes:
        name: Internal identifier used in code (snake_case recommended).
        display_name: Human-readable name shown in GUI.
        description: Tooltip text explaining the parameter.
        default: Default value for the parameter.
        group: Optional group name for organising parameters in the GUI.
        order: Optional ordering hint (lower numbers appear first).
    """

    name: str
    display_name: str
    description: str = ""
    default: T = None
    group: str = "General"
    order: int = 0

    @abstractmethod
    def validate(self, value: Any) -> tuple[bool, str]:
        """
        Validate a value against this parameter's constraints.

        Args:
            value: The value to validate.

        Returns:
            A tuple of (is_valid, error_message). If valid, error_message
            is an empty string.
        """
        pass

    @abstractmethod
    def convert(self, value: Any) -> T:
        """
        Convert a raw input value to the appropriate type.

        Args:
            value: The raw value (often a string from GUI input).

        Returns:
            The converted value of the appropriate type.

        Raises:
            ValueError: If the value cannot be converted.
        """
        pass

    @property
    @abstractmethod
    def widget_type(self) -> str:
        """
        Return a hint for what GUI widget to use.

        Returns:
            A string identifier for the widget type (e.g., 'spinbox',
            'entry', 'checkbox', 'dropdown').
        """
        pass


@dataclass
class IntParameter(Parameter[int]):
    """
    Integer parameter with optional min/max constraints.

    Attributes:
        min_value: Minimum allowed value (inclusive). None for no limit.
        max_value: Maximum allowed value (inclusive). None for no limit.
        step: Step size for spinbox increment/decrement.
    """

    default: int = 0
    min_value: int | None = None
    max_value: int | None = None
    step: int = 1

    def validate(self, value: Any) -> tuple[bool, str]:
        """Validate that value is an integer within constraints."""
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            return False, f"'{value}' is not a valid integer"

        if self.min_value is not None and int_value < self.min_value:
            return False, f"Value must be at least {self.min_value}"

        if self.max_value is not None and int_value > self.max_value:
            return False, f"Value must be at most {self.max_value}"

        return True, ""

    def convert(self, value: Any) -> int:
        """Convert value to integer."""
        return int(value)

    @property
    def widget_type(self) -> str:
        """Integer parameters use spinbox widgets."""
        return "spinbox"


@dataclass
class FloatParameter(Parameter[float]):
    """
    Floating-point parameter with optional min/max constraints.

    Attributes:
        min_value: Minimum allowed value (inclusive). None for no limit.
        max_value: Maximum allowed value (inclusive). None for no limit.
        step: Step size for spinbox increment/decrement.
        precision: Number of decimal places to display.
    """

    default: float = 0.0
    min_value: float | None = None
    max_value: float | None = None
    step: float = 0.1
    precision: int = 2

    def validate(self, value: Any) -> tuple[bool, str]:
        """Validate that value is a float within constraints."""
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            return False, f"'{value}' is not a valid number"

        if self.min_value is not None and float_value < self.min_value:
            return False, f"Value must be at least {self.min_value}"

        if self.max_value is not None and float_value > self.max_value:
            return False, f"Value must be at most {self.max_value}"

        return True, ""

    def convert(self, value: Any) -> float:
        """Convert value to float."""
        return float(value)

    @property
    def widget_type(self) -> str:
        """Float parameters use spinbox widgets."""
        return "spinbox"


@dataclass
class BoolParameter(Parameter[bool]):
    """
    Boolean parameter displayed as a checkbox.

    Attributes:
        default: Default checked state.
    """

    default: bool = False

    def validate(self, value: Any) -> tuple[bool, str]:
        """Boolean values are always valid after conversion."""
        return True, ""

    def convert(self, value: Any) -> bool:
        """Convert value to boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    @property
    def widget_type(self) -> str:
        """Boolean parameters use checkbox widgets."""
        return "checkbox"


@dataclass
class ChoiceParameter(Parameter[str]):
    """
    Parameter with a fixed set of allowed values, displayed as a dropdown.

    Attributes:
        choices: List of allowed values.
        default: Default selected value (must be in choices).
    """

    choices: list[str] = field(default_factory=list)
    default: str = ""

    def __post_init__(self):
        """Ensure default is valid if choices are provided."""
        if self.choices and not self.default:
            self.default = self.choices[0]
        if self.default and self.choices and self.default not in self.choices:
            raise ValueError(
                f"Default value '{self.default}' not in choices: {self.choices}"
            )

    def validate(self, value: Any) -> tuple[bool, str]:
        """Validate that value is one of the allowed choices."""
        str_value = str(value)
        if str_value not in self.choices:
            return False, f"'{str_value}' is not a valid choice. Options: {self.choices}"
        return True, ""

    def convert(self, value: Any) -> str:
        """Convert value to string."""
        return str(value)

    @property
    def widget_type(self) -> str:
        """Choice parameters use dropdown widgets."""
        return "dropdown"


def validate_parameters(
    parameters: list[Parameter], values: dict[str, Any]
) -> tuple[bool, dict[str, str]]:
    """
    Validate a dictionary of parameter values against their definitions.

    Args:
        parameters: List of parameter definitions.
        values: Dictionary mapping parameter names to values.

    Returns:
        A tuple of (all_valid, errors) where errors is a dictionary mapping
        parameter names to error messages for any invalid parameters.
    """
    errors = {}

    for param in parameters:
        if param.name not in values:
            errors[param.name] = "Missing required parameter"
            continue

        is_valid, error_msg = param.validate(values[param.name])
        if not is_valid:
            errors[param.name] = error_msg

    return len(errors) == 0, errors


def convert_parameters(
    parameters: list[Parameter], values: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert a dictionary of raw values to their appropriate types.

    Args:
        parameters: List of parameter definitions.
        values: Dictionary mapping parameter names to raw values.

    Returns:
        Dictionary mapping parameter names to converted values.

    Raises:
        ValueError: If any value cannot be converted.
    """
    converted = {}

    for param in parameters:
        if param.name in values:
            converted[param.name] = param.convert(values[param.name])
        else:
            converted[param.name] = param.default

    return converted
