# Protocol Template Walkthrough

The file `protocols/_protocol_template.py` is a ready-to-copy starting point for new protocols. This page walks through each section.

## Creating a new protocol

1. Copy `_protocol_template.py` to a new file (e.g. `my_protocol.py`) -- remove the leading underscore
2. Rename the class
3. Implement the required methods
4. The system auto-discovers it on next launch

## The template, annotated

### Imports

```python
from core.parameter_types import BoolParameter, FloatParameter, IntParameter, StringParameter
from core.protocol_base import BaseProtocol
```

Import `BaseProtocol` (required) and whichever parameter types you need.

### Class definition

```python
class ProtocolTemplate(BaseProtocol):
    """Template protocol: copy, rename, then simplify as needed."""
```

Your class must inherit from `BaseProtocol`.

### `get_name()` -- display name

```python
@classmethod
def get_name(cls) -> str:
    return "Template Protocol"
```

This string appears as the tab label in the GUI. Keep it short.

### `get_description()` -- protocol summary

```python
@classmethod
def get_description(cls) -> str:
    return "Template description. Replace with your protocol summary."
```

Shown at the top of the protocol tab in Setup Mode.

### `get_parameters()` -- configurable settings

```python
@classmethod
def get_parameters(cls) -> list:
    return [
        IntParameter(
            name="example_int",
            display_name="Example Integer",
            default=10,
            min_value=1,
            max_value=1000,
        ),
        FloatParameter(
            name="example_float",
            display_name="Example Float",
            default=1.0,
            min_value=0.0,
            max_value=60.0,
        ),
        BoolParameter(
            name="example_flag",
            display_name="Example Flag",
            default=True,
        ),
        StringParameter(
            name="example_text",
            display_name="Example Text",
            default="",
        ),
    ]
```

Each parameter automatically generates a GUI widget. The `name` field is the key used to access the value in `self.parameters`. See [Parameter Types](parameter-types.md) for all options.

### `_run_protocol()` -- main experiment loop

```python
def _run_protocol(self) -> None:
    scales = self.scales
    perf_tracker = self.perf_trackers.get("trials")

    if perf_tracker is not None:
        perf_tracker.reset()

    self.log("Template protocol started")
    self.log(f"Parameters: {self.parameters}")

    # Read the current weight from the scales
    if scales is not None:
        weight = scales.get_weight()
        if weight is not None:
            self.log(f"Current weight: {weight:.2f} g")

    # Main trial loop
    for trial in range(self.parameters["example_int"]):
        if self.check_stop():
            self.log("Stopped by user")
            return

        self.sleep(0.1)

    self.log("Template protocol complete")
```

Key patterns shown here:

1. **Get resources** -- `self.scales`, `self.perf_trackers` are set by the system before your protocol runs
2. **Reset tracker** -- Call `perf_tracker.reset()` at the start to initialise timing
3. **Log messages** -- `self.log()` sends text to the GUI session log
4. **Check for stop** -- Call `self.check_stop()` in every loop iteration. Return early if `True`
5. **Use `self.sleep()`** -- Not `time.sleep()`. This respects the virtual clock in simulation mode
6. **Access parameters** -- Via `self.parameters["name"]`, already validated and type-converted

## Minimal protocol

The absolute minimum protocol with no parameters:

```python
from core.protocol_base import BaseProtocol

class MinimalProtocol(BaseProtocol):
    @classmethod
    def get_name(cls) -> str:
        return "Minimal"

    @classmethod
    def get_description(cls) -> str:
        return "Does nothing."

    @classmethod
    def get_parameters(cls) -> list:
        return []

    def _run_protocol(self) -> None:
        self.log("Hello!")
        if self.check_stop():
            return
```
