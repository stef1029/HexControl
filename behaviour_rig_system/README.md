# Behaviour Rig System

A modular framework for running behaviour experiments on custom hardware rigs.

## Overview

This system provides a graphical interface for configuring and running behaviour protocols on behaviour rig hardware. It manages:

- **Session configuration** - Select mouse, save location, and protocol parameters
- **Peripheral orchestration** - Automatically starts/stops DAQ and camera subprocesses
- **Protocol execution** - Run behaviour protocols with real-time event logging
- **Hardware communication** - Serial communication with Arduino-based behaviour rigs via BehavLink

### Key Features

- **Multi-rig launcher** - Launch separate windows for each rig
- **Mode-based UI** - Setup → Running → Post-Session flow
- **Dynamic parameter forms** - Automatically generated from protocol definitions
- **Real-time event logging** - Live updates during protocol execution
- **Peripheral management** - DAQ and camera processes with signal-file coordination
- **Modular protocol system** - Add new protocols by creating a single Python file

## Project Structure

```
behaviour_rig_system/
├── main.py                     # Application entry point
├── core/                       # Core system components
│   ├── parameter_types.py      # Parameter definitions for GUI generation
│   ├── protocol_base.py        # Base class for all protocols
│   ├── protocol_loader.py      # Creates protocol classes from simple definitions
│   ├── peripheral_manager.py   # Manages DAQ and camera subprocesses
│   └── session.py              # Session configuration
├── protocols/                  # Behaviour protocol implementations
│   ├── __init__.py             # Protocol registry
│   └── hardware_test.py        # Example: Hardware test protocol
├── gui/                        # GUI components
│   ├── launcher.py             # Multi-rig launcher window
│   ├── rig_window.py           # Main rig window (orchestrator)
│   ├── parameter_widget.py     # Dynamic parameter form builder
│   └── modes/                  # UI modes
│       ├── setup_mode.py       # Session configuration UI
│       ├── running_mode.py     # Active session monitoring UI
│       └── post_session_mode.py # Session summary UI
└── config/
    └── rigs.yaml               # Rig and experiment configuration
```

## Installation

### Requirements

- Python 3.10 or later
- tkinter (usually included with Python)
- pyserial (for hardware communication)
- PyYAML (for configuration files)
- BehavLink (for Arduino communication)

### Setup

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install pyserial pyyaml
   ```
3. Ensure your BehavLink library is available in your Python path

## Usage

### Running the GUI

```bash
python main.py
```

The launcher window will open showing available rigs. Click a rig button to test the connection and open its control window.

### Configuration

Edit `config/rigs.yaml` to configure:

```yaml
global:
  baud_rate: 115200

rigs:
  - name: "Rig 1"
    serial_port: "COM7"
    enabled: true

cohort_folders:
  - name: "My Experiment"
    directory: "D:\\behaviour_data\\my_experiment"

mice:
  - id: "mouse_001"
    description: "Control group"
```

---

## Code Flow Walkthrough

This section explains how the application flows from startup to session completion.

### 1. Application Launch

```
main.py
   └── launcher.launch(CONFIG_PATH)
```

- `main.py` defines the config path and calls `launcher.launch()`
- `launcher.py` creates a window showing available rigs (loaded from `rigs.yaml`)
- User clicks a rig button to connect

### 2. Rig Window Opens

```
launcher.py
   └── RigWindow(serial_port, baud_rate, parent, rig_name, rig_config)
```

`RigWindow.__init__()` runs:
1. `_setup_window()` - Creates the Tk window
2. `_create_modes()` - Creates the three mode frames (Setup, Running, PostSession)
3. `_create_startup_overlay()` - Creates the overlay shown during startup
4. `_show_mode(SETUP)` - Shows the setup mode

**User sees:** Setup screen with cohort/mouse selection, protocol tabs, and Start button

### 3. User Clicks "Start Session"

```
SetupMode (Start button clicked)
   └── on_start callback
       └── RigWindow._start_session(session_config)
```

1. `SetupMode` validates the config and calls `_start_session()` with:
   - `protocol_class` - The protocol to run
   - `parameters` - Protocol parameters from the UI
   - `mouse_id` - Selected mouse
   - `save_directory` - Selected cohort folder path

2. `_start_session()`:
   - Stores session info for later display
   - Shows startup overlay
   - Spawns `_startup_sequence()` in a background thread

### 4. Startup Sequence (Background Thread)

```
_startup_sequence()
   ├── load_peripheral_config()      # Create config for DAQ/camera
   ├── PeripheralManager()           # Create manager instance
   ├── _start_daq()                  # Launch DAQ subprocess
   ├── _wait_for_connection()        # Wait for arduino_connected.signal
   ├── _start_camera()               # Launch camera subprocess
   ├── serial.Serial()               # Open serial port to behaviour rig
   ├── reset_arduino_via_dtr()       # Reset Arduino
   ├── BehaviourRigLink()            # Create protocol communication layer
   ├── link.send_hello/wait_hello()  # Handshake with Arduino
   └── protocol_class()              # Create protocol instance
```

**User sees:** Startup overlay with progress log

- **On success:** Calls `_on_startup_complete()` on main thread
- **On error:** Calls `_on_startup_error()` on main thread

### 5. Session Running

```
_on_startup_complete()
   ├── _hide_startup_overlay()
   ├── running_mode.activate(session_info)
   ├── _show_mode(RUNNING)
   ├── running_mode.start_timer()
   └── Thread(_run_protocol_thread)    # Start protocol in background
```

- Running mode shows: session summary, timer, log, Stop button
- Protocol runs in background thread via `current_protocol.run()`
- Protocol emits events → `_on_protocol_event()` → `_handle_event()` → updates UI

**User sees:** Running mode with live timer and event log

### 6. Session Ends (Stop or Complete)

**If user clicks Stop:**
```
RunningMode (Stop button clicked)
   └── on_stop callback
       └── RigWindow._stop_session()
           └── current_protocol.request_abort()
```

The protocol checks `_abort_requested` in its run loop and exits cleanly.

**When protocol finishes:**
```
_run_protocol_thread() completes
   └── _on_protocol_complete()
```

### 7. Cleanup and Post-Session

```
_on_protocol_complete()
   ├── running_mode.stop_timer()
   ├── Get final status and duration
   ├── _cleanup_session()
   │      ├── link.shutdown()              # Send shutdown to Arduino
   │      ├── link.stop()                  # Stop BehavLink thread
   │      ├── serial.close()               # Close serial port
   │      └── peripheral_manager.stop()
   │             ├── _stop_camera_gracefully()   # Create stop signal, wait
   │             ├── _cleanup_daq()              # Wait for DAQ to finish
   │             └── _cleanup_signal_files()     # Delete .signal files
   ├── post_session_mode.activate(summary)
   └── _show_mode(POST_SESSION)
```

**User sees:** Post-session summary with status, duration, save path, and "New Session" button

### 8. New Session or Close

**If user clicks "New Session":**
```
PostSessionMode (New Session button clicked)
   └── on_new_session callback
       └── RigWindow._new_session()
           └── _show_mode(SETUP)
```

Back to setup screen.

**If user closes window:**
```
Window close event
   └── RigWindow._on_close()
       ├── If session running: confirm dialog, then _stop_session()
       └── _force_close()
           ├── _cleanup_session()
           └── root.destroy()
```

### Key Files Summary

| File | Purpose |
|------|---------|
| `main.py` | Entry point, defines config path |
| `launcher.py` | Rig selection window |
| `gui/rig_window.py` | **Orchestrator** - manages modes, hardware, session lifecycle |
| `gui/modes/setup_mode.py` | Config UI (cohort, mouse, protocol params) |
| `gui/modes/running_mode.py` | Active session UI (timer, log, stop button) |
| `gui/modes/post_session_mode.py` | Summary UI (results, new session button) |
| `core/peripheral_manager.py` | Manages DAQ and camera subprocesses |
| `core/protocol_base.py` | Base class for protocols |
| `protocols/*.py` | Protocol implementations |

### Data Flow

```
User selections (SetupMode)
        ↓
   session_config dict
        ↓
   PeripheralConfig (for DAQ/camera paths)
        ↓
   Protocol instance (with parameters + BehavLink)
        ↓
   Protocol events → RunningMode log
        ↓
   Final status + duration → PostSessionMode summary
```

---

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
- Live performance monitoring graphs
- Parameter presets (save/load)
- Session notes and metadata

## License

[Your license here]

## Author

[Your name/organisation]
