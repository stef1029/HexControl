# Parameter Types

Parameters define the configurable settings for your protocol. The GUI automatically generates appropriate input widgets for each parameter type.

All parameter types are defined in `core/parameter_types.py`.

## Common fields

Every parameter type shares these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Internal key -- used to access the value via `self.parameters["name"]` |
| `display_name` | `str` | required | Label shown in the GUI |
| `default` | varies | type-specific | Default value |
| `description` | `str` | `""` | Tooltip text shown on hover |
| `group` | `str` | `"General"` | Group heading for organizing parameters in the form |
| `order` | `int` | `0` | Sort order within the group (lower numbers appear first) |

---

## IntParameter

Integer values displayed as a spinbox.

```python
IntParameter(
    name="num_trials",
    display_name="Number of Trials",
    default=100,
    min_value=1,
    max_value=10000,
    step=10,
    description="Total number of trials to run",
    group="Session",
    order=0,
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_value` | `int \| None` | `None` | Minimum allowed value (no limit if `None`) |
| `max_value` | `int \| None` | `None` | Maximum allowed value (no limit if `None`) |
| `step` | `int` | `1` | Increment/decrement step for the spinbox arrows |

---

## FloatParameter

Floating-point values displayed as a spinbox with configurable precision.

```python
FloatParameter(
    name="response_timeout",
    display_name="Response Timeout (s)",
    default=10.0,
    min_value=1.0,
    max_value=60.0,
    step=0.5,
    precision=1,
    description="Seconds to wait for a response before timeout",
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_value` | `float \| None` | `None` | Minimum allowed value |
| `max_value` | `float \| None` | `None` | Maximum allowed value |
| `step` | `float` | `0.1` | Increment/decrement step |
| `precision` | `int` | `2` | Number of decimal places displayed |

---

## BoolParameter

Boolean toggle displayed as a checkbox.

```python
BoolParameter(
    name="audio_enabled",
    display_name="Enable Audio Cues",
    default=False,
    description="Play audio cue alongside visual LED cue",
)
```

No additional fields beyond the common ones. Validation always succeeds.

---

## ChoiceParameter

Selection from a fixed list, displayed as a dropdown.

```python
ChoiceParameter(
    name="trial_mode",
    display_name="Trial Mode",
    choices=["random", "sequential", "blocked"],
    default="random",
    description="How to select the target port each trial",
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `choices` | `list[str]` | `[]` | List of allowed values |

If `default` is empty, it defaults to the first choice in the list. Validation rejects values not in `choices`.

---

## StringParameter

Free-text input displayed as a text entry field.

```python
StringParameter(
    name="notes",
    display_name="Session Notes",
    default="",
    description="Optional notes for this session",
)
```

No additional fields. Validation always succeeds.

---

## Validation and conversion

Parameters are validated and type-converted before the protocol runs.

### Validation

Each parameter has a `validate(value)` method returning `(is_valid, error_message)`:

- **Int/Float**: Checks that the value is numeric and within `min_value`/`max_value` bounds
- **Bool**: Always valid
- **Choice**: Checks that the value is in the `choices` list
- **String**: Always valid

If validation fails, the GUI shows the error message next to the parameter and prevents the session from starting.

### Conversion

Each parameter has a `convert(value)` method that casts the raw GUI string to the correct Python type:

- `IntParameter.convert("42")` returns `42` (int)
- `FloatParameter.convert("3.14")` returns `3.14` (float)
- `BoolParameter.convert("true")` returns `True` (bool)
- `ChoiceParameter.convert(x)` returns `str(x)`
- `StringParameter.convert(x)` returns `str(x)`

### Helper functions

Two utility functions are available for bulk operations:

```python
from core.parameter_types import validate_parameters, convert_parameters

# Validate all parameters at once
all_valid, errors = validate_parameters(param_list, values_dict)
# errors is a dict: {param_name: error_message}

# Convert all values to correct types (uses defaults for missing values)
converted = convert_parameters(param_list, values_dict)
```

## Grouping and ordering

Parameters can be organized using `group` and `order`:

```python
[
    IntParameter(name="num_trials", display_name="Trials", default=100,
                 group="Session", order=0),
    FloatParameter(name="timeout", display_name="Timeout (s)", default=10.0,
                   group="Session", order=1),
    FloatParameter(name="iti", display_name="ITI (s)", default=1.0,
                   group="Timing", order=0),
    FloatParameter(name="wait", display_name="Wait (s)", default=0.0,
                   group="Timing", order=1),
    BoolParameter(name="audio", display_name="Audio", default=False,
                  group="Cues", order=0),
]
```

The GUI renders parameters sorted by group name, then by `order` within each group, with a heading for each group.
