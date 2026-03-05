"""
Parameter Type Definitions for Behaviour Protocols.

Simplified parameter system - each parameter is a dataclass with:
    - name: Internal identifier
    - display_name: Shown in GUI
    - description: Tooltip text
    - default: Default value
    - Constraints (min/max for numbers, choices for dropdowns)
    - group: For organizing in GUI

Example:
    IntParameter(
        name="trial_count",
        display_name="Number of Trials",
        default=10,
        min_value=1,
        max_value=100,
    )
"""

from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# Parameter Types - Simple Dataclasses
# =============================================================================

@dataclass
class IntParameter:
    """Integer parameter (displayed as spinbox)."""
    name: str
    display_name: str
    default: int = 0
    description: str = ""
    min_value: int | None = None
    max_value: int | None = None
    step: int = 1
    group: str = "General"
    order: int = 0

    def validate(self, value: Any) -> tuple[bool, str]:
        """Check if value is valid."""
        try:
            v = int(value)
        except (ValueError, TypeError):
            return False, f"'{value}' is not a valid integer"
        if self.min_value is not None and v < self.min_value:
            return False, f"Must be at least {self.min_value}"
        if self.max_value is not None and v > self.max_value:
            return False, f"Must be at most {self.max_value}"
        return True, ""

    def convert(self, value: Any) -> int:
        """Convert to int."""
        return int(value)


@dataclass
class FloatParameter:
    """Float parameter (displayed as spinbox)."""
    name: str
    display_name: str
    default: float = 0.0
    description: str = ""
    min_value: float | None = None
    max_value: float | None = None
    step: float = 0.1
    precision: int = 2
    group: str = "General"
    order: int = 0

    def validate(self, value: Any) -> tuple[bool, str]:
        """Check if value is valid."""
        try:
            v = float(value)
        except (ValueError, TypeError):
            return False, f"'{value}' is not a valid number"
        if self.min_value is not None and v < self.min_value:
            return False, f"Must be at least {self.min_value}"
        if self.max_value is not None and v > self.max_value:
            return False, f"Must be at most {self.max_value}"
        return True, ""

    def convert(self, value: Any) -> float:
        """Convert to float."""
        return float(value)


@dataclass
class BoolParameter:
    """Boolean parameter (displayed as checkbox)."""
    name: str
    display_name: str
    default: bool = False
    description: str = ""
    group: str = "General"
    order: int = 0

    def validate(self, value: Any) -> tuple[bool, str]:
        """Booleans are always valid."""
        return True, ""

    def convert(self, value: Any) -> bool:
        """Convert to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)


@dataclass
class ChoiceParameter:
    """Choice parameter (displayed as dropdown)."""
    name: str
    display_name: str
    choices: list[str] = field(default_factory=list)
    default: str = ""
    description: str = ""
    group: str = "General"
    order: int = 0

    def __post_init__(self):
        """Set default to first choice if not specified."""
        if self.choices and not self.default:
            self.default = self.choices[0]

    def validate(self, value: Any) -> tuple[bool, str]:
        """Check if value is in choices."""
        if str(value) not in self.choices:
            return False, f"Must be one of: {self.choices}"
        return True, ""

    def convert(self, value: Any) -> str:
        """Convert to string."""
        return str(value)


@dataclass
class StringParameter:
    """String parameter (displayed as text entry)."""
    name: str
    display_name: str
    default: str = ""
    description: str = ""
    group: str = "General"
    order: int = 0

    def validate(self, value: Any) -> tuple[bool, str]:
        """Strings are always valid."""
        return True, ""

    def convert(self, value: Any) -> str:
        """Convert to string."""
        return str(value)


# Type alias for any parameter
Parameter = IntParameter | FloatParameter | BoolParameter | ChoiceParameter | StringParameter


# =============================================================================
# Helper Functions
# =============================================================================

def validate_parameters(
    parameters: list[Parameter], values: dict[str, Any]
) -> tuple[bool, dict[str, str]]:
    """
    Validate all parameter values.
    
    Returns (all_valid, {param_name: error_message}).
    """
    errors = {}
    for param in parameters:
        if param.name not in values:
            errors[param.name] = "Missing value"
            continue
        is_valid, msg = param.validate(values[param.name])
        if not is_valid:
            errors[param.name] = msg
    return len(errors) == 0, errors


def convert_parameters(
    parameters: list[Parameter], values: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert all values to their correct types.
    
    Uses defaults for missing values.
    """
    result = {}
    for param in parameters:
        if param.name in values:
            result[param.name] = param.convert(values[param.name])
        else:
            result[param.name] = param.default
    return result
