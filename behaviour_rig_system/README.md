# Behaviour Rig System

A modular framework for running behaviour experiments on custom hardware rigs.

## Overview

This system provides a graphical interface for configuring and running behaviour protocols on behaviour rig hardware. The architecture is designed to make it easy to add new behaviour protocols whilst keeping the core infrastructure stable.

### Key Features

- **Tabbed GUI** for selecting and configuring different behaviour protocols
- **Dynamic parameter forms** automatically generated from protocol definitions
- **Real-time event logging** during protocol execution
- **Simulation mode** for testing without connected hardware
- **Modular protocol system** - add new protocols by creating a single Python file

## Project Structure

```
behaviour_rig_system/
├── main.py                 # Application entry point
├── core/                   # Core system components
│   ├── __init__.py
│   ├── parameter_types.py  # Parameter definitions for GUI generation
│   ├── protocol_base.py    # Base class for all protocols
│   └── hardware.py         # Hardware abstraction layer
├── protocols/              # Behaviour protocol implementations
│   ├── __init__.py
│   └── hardware_test.py    # Example: Hardware test protocol
├── gui/                    # GUI components
│   ├── __init__.py
│   ├── main_window.py      # Main application window
│   └── parameter_widget.py # Dynamic parameter form builder
└── config/
    └── rigs.yaml           # Rig configuration
```

## Installation

### Requirements

- Python 3.10 or later
- tkinter (usually included with Python)
- pyserial (for hardware communication)

### Setup

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install pyserial
   ```
3. Ensure your BehavLink library is available in your Python path

## Usage

### Running the GUI

```bash
python main.py
```

The GUI will open with tabs for each available protocol. Select a protocol, configure its parameters, and click "Start Protocol" to begin.

### Simulation Mode

Enable "Simulation Mode" in the GUI to test protocols without connected hardware. All hardware commands will be logged instead of being sent to the rig.

### Configuration

Edit `main.py` to change default settings:

```python
SERIAL_PORT = "COM7"      # Your serial port
BAUD_RATE = 115200        # Communication speed
SIMULATION_MODE = True    # Start in simulation mode
```

## Creating New Protocols

To add a new behaviour protocol:

1. Create a new Python file in the `protocols/` directory
2. Define a class that inherits from `BaseProtocol`
3. Implement the required methods:
   - `get_name()`: Return the protocol's display name
   - `get_description()`: Return a description for the GUI
   - `get_parameters()`: Return a list of configurable parameters
   - `_run_protocol()`: Implement the main behaviour loop
4. Add the new protocol to `protocols/__init__.py`

### Example Protocol Template

```python
from core.parameter_types import IntParameter, FloatParameter, BoolParameter
from core.protocol_base import BaseProtocol, ProtocolEvent


class MyProtocol(BaseProtocol):
    """My custom behaviour protocol."""

    @classmethod
    def get_name(cls) -> str:
        return "My Protocol"

    @classmethod
    def get_description(cls) -> str:
        return "Description of what this protocol does."

    @classmethod
    def get_parameters(cls) -> list:
        return [
            IntParameter(
                name="trial_count",
                display_name="Number of Trials",
                description="How many trials to run",
                default=100,
                min_value=1,
                max_value=1000,
            ),
            FloatParameter(
                name="delay",
                display_name="Inter-trial Delay (s)",
                description="Delay between trials",
                default=2.0,
                min_value=0.5,
                max_value=10.0,
            ),
        ]

    def _run_protocol(self) -> None:
        """Main behaviour loop."""
        for trial in range(self.parameters["trial_count"]):
            if self._check_abort():
                return

            # Emit event for logging
            self._emit_event(ProtocolEvent(
                "trial_start",
                data={"trial": trial + 1}
            ))

            # Your behaviour logic here
            # self.hardware.led_set(0, 255)
            # time.sleep(self.parameters["delay"])
            # self.hardware.led_set(0, 0)

            self._emit_event(ProtocolEvent(
                "trial_end",
                data={"trial": trial + 1}
            ))
```

## Parameter Types

The system supports the following parameter types:

| Type | GUI Widget | Example |
|------|------------|---------|
| `IntParameter` | Spinbox | Trial counts, port numbers |
| `FloatParameter` | Spinbox | Delays, durations, thresholds |
| `BoolParameter` | Checkbox | Enable/disable options |
| `ChoiceParameter` | Dropdown | Selection from fixed options |

### Parameter Attributes

All parameters support:
- `name`: Internal identifier (used in code)
- `display_name`: Human-readable label for GUI
- `description`: Tooltip text
- `default`: Default value
- `group`: Group name for organising in GUI
- `order`: Sorting order within group

Numeric parameters additionally support:
- `min_value`, `max_value`: Validation constraints
- `step`: Increment for spinbox

## Hardware Interface

The `HardwareInterface` class provides methods for controlling the rig:

```python
# LEDs (ports 0-5)
hardware.led_set(port, brightness)  # brightness: 0-255
hardware.led_off(port)
hardware.led_all_off()

# Spotlights (ports 0-5, or 255 for all)
hardware.spotlight_set(port, brightness)

# IR Illuminator
hardware.ir_set(brightness)

# Buzzers (ports 0-5, or 255 for all)
hardware.buzzer_set(port, on)  # on: True/False

# Speaker
hardware.speaker_set(frequency, duration)

# Valves (ports 0-5)
hardware.valve_pulse(port, duration_ms)

# GPIO (pins 0-5)
hardware.gpio_configure(pin, mode)
hardware.gpio_set(pin, high)

# Sensors
event = hardware.wait_for_sensor_event(timeout)
```

## Event System

Protocols emit events for logging and monitoring:

```python
self._emit_event(ProtocolEvent(
    "event_type",
    data={"key": "value"}
))
```

Events are displayed in the GUI event log with timestamps.

## Future Development

Planned features:
- Multi-rig support with individual windows
- Live performance monitoring graphs
- Data logging to files
- DAQ and camera integration
- Parameter presets (save/load)

## License

[Your license here]

## Author

[Your name/organisation]
