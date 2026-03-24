# Behaviour Rig System

A modular framework for running behaviour experiments on custom Arduino-based hardware rigs, with a tkinter GUI built on top of what is fundamentally a linear script.

## Overview

At its core, a behaviour session is a straight-line sequence:

1. Ask the user for inputs (mouse, protocol, parameters, save location)
2. Start peripheral processes (DAQ, camera, scales)
3. Connect to the Arduino rig over serial
4. Run the experiment protocol
5. Clean up hardware
6. Show results

This system wraps that sequence in a GUI so the user gets forms instead of `input()` prompts, live displays instead of `print()` statements, and the ability to cancel or stop at any point without the window freezing.

---

## System Architecture

### The Three Layers

The system is split into three layers that each have a single job:

```
┌─────────────────────────────────────────────────────┐
│  GUI Layer (gui/)                                   │
│  Displays things, takes user input, owns widgets    │
│  No business logic — just shows what it's told      │
├─────────────────────────────────────────────────────┤
│  Controller Layer (core/session_controller.py)      │
│  Runs the session lifecycle on background threads   │
│  No tkinter — communicates through named events     │
├─────────────────────────────────────────────────────┤
│  Hardware Layer (core/ + external libs)             │
│  Protocol execution, peripheral management,         │
│  serial communication, performance tracking         │
└─────────────────────────────────────────────────────┘
```

**Why separate them?** The session lifecycle involves blocking operations (waiting for hardware connections, running experiment loops) that take seconds or minutes. If those run on the GUI thread, the window freezes. So the controller runs them on background threads, and the GUI reacts to what the controller reports.

### Who runs what

The GUI is the main thing running. It owns the tkinter `mainloop()`, creates the controller, and tells it to do things in response to button presses (`start_session`, `stop_session`, etc.).

The controller then does the actual work on background threads — starting hardware, running the protocol, cleaning up. But it has a problem: things happen during that work that the user needs to see. The DAQ connects, a trial completes, an error occurs. In a CLI script you'd just `print()`. Here, the controller can't touch the GUI (it doesn't even import tkinter). So instead, it announces what happened by calling `_emit()`, and whatever functions were registered beforehand get called.

The key insight is the direction: **the GUI pushes its own functions into the controller at setup time, not the other way around.** The controller never imports anything from the GUI. It just calls whatever functions are sitting in its `_listeners` dict, without knowing what they do.

### Event Pattern

This is the mechanism that makes the above work. Every component that needs to announce things implements the same ~10-line pattern independently (no shared base class):

```python
def on(self, event_name: str, callback: Callable) -> None:
    """Let someone register a function to be called when an event fires."""
    self._listeners.setdefault(event_name, []).append(callback)

def _emit(self, event_name: str, **kwargs) -> None:
    """Call all registered functions for this event."""
    for cb in self._listeners.get(event_name, []):
        try:
            cb(**kwargs)
        except Exception:
            pass
```

Think of `.on()` as giving someone your phone number, and `._emit()` as dialling it. The controller doesn't know who it's calling or what they'll do with the information — it just dials. If the GUI registered a function that updates a label, the label gets updated. If you registered `print` instead, it would print to the terminal. If nobody registered anything, the emit does nothing.

This is how the GUI "listens" without polling. There's no loop checking for new messages. The GUI handed the controller a set of functions during setup, and the controller calls them directly whenever something happens.

### Event hierarchy

Events don't go directly from hardware to GUI. They flow upward through a chain, where each layer translates and forwards to the one above it. Each hop adds context — a generic `"log"` from deep in the system becomes a specific `"protocol_log"` or `"startup_status"` by the time it reaches the GUI.

```
RigWindow (GUI)
│
│ listens to controller via .on()
│ receives: "startup_status", "protocol_log", "performance_update",
│           "stimulus", "protocol_complete", "cleanup_log", etc.
│
└── SessionController
    │
    │ listens to protocol, tracker, and peripheral manager via .on()
    │ translates and forwards their events as its own
    │
    ├── BaseProtocol
    │   │ emits: "log", "started", "error"
    │   │
    │   │ controller wires these at protocol creation time:
    │   │   protocol.on("log", ...)    → controller emits "protocol_log"
    │   │   protocol.on("error", ...)  → controller emits "protocol_log"
    │   │   protocol.on("started", ...) → controller emits "protocol_log"
    │   │
    │   │ Protocol authors just call self.log("message") — they never
    │   │ touch .on() or ._emit() directly. The wiring is invisible to them.
    │   │
    │   └── PerformanceTracker
    │       emits: "update", "stimulus"
    │
    │       controller wires these at tracker creation time:
    │         tracker.on("update", ...)   → controller emits "performance_update"
    │         tracker.on("stimulus", ...) → controller emits "stimulus"
    │
    │       Protocol authors call tracker.success() / tracker.stimulus() —
    │       the tracker emits events, the controller forwards them.
    │
    └── PeripheralManager
        │ emits: "log"
        │
        │ controller wires this at manager creation time:
        │   pm.on("log", ...) → controller emits "startup_status"
        │
        └── CameraManager
            emits: "log"

            PeripheralManager wires this when it creates the camera:
              camera.on("log", ...) → peripheral manager emits "log"

            So a camera log message travels:
              CameraManager → PeripheralManager → Controller → GUI
```

The controller is the middleman. It creates the lower-level components, wires their events into its own, and the GUI only ever talks to the controller. The protocol doesn't know the controller exists. The camera doesn't know the peripheral manager exists. Each component just calls `_emit()` and whoever created it decided what happens.

This also means the two-hop chain (e.g. protocol → controller → GUI) isn't redundant. The protocol emits `"log"` — a generic name that makes sense inside any protocol. The controller re-emits it as `"protocol_log"` — a specific name that the GUI can distinguish from `"startup_status"` or `"cleanup_log"`, which are also log messages but from different phases of the session.

### How the GUI registers its functions

All of the wiring between controller events and GUI updates happens in one place — `RigWindow._bind_controller_events()`:

```python
def _bind_controller_events(self):
    def on_main_thread(fn):
        def wrapper(**kwargs):
            self.root.after(0, lambda: fn(**kwargs))
        return wrapper

    self.controller.on("startup_status",    on_main_thread(self._on_startup_status))
    self.controller.on("protocol_log",      on_main_thread(self._on_protocol_log))
    self.controller.on("performance_update", on_main_thread(self._on_performance_update))
    # ... etc
```

Each `.on()` call takes one of RigWindow's own methods and pushes it into the controller's `_listeners` dict. After this runs, the controller's internal state looks something like:

```python
_listeners = {
    "startup_status":    [<wrapped _on_startup_status>],
    "protocol_log":      [<wrapped _on_protocol_log>],
    "performance_update": [<wrapped _on_performance_update>],
    ...
}
```

When the controller later calls `self._emit("startup_status", message="Starting DAQ...")`, it loops through that list and calls each function. The function happens to update a tkinter widget — but the controller doesn't know that.

### Thread safety

There's one complication: the controller calls `_emit()` from background threads, but tkinter widgets can only be touched from the main thread. That's what the `on_main_thread` wrapper handles. Instead of calling the GUI method directly, it schedules it via `root.after(0, fn)` — tkinter's way of saying "run this on the main thread next chance you get." The background thread doesn't wait; it fires and moves on. The main thread picks it up on its next loop iteration.

The full chain for a single message:

```
Background thread:
  controller._emit("startup_status", message="Starting DAQ...")
    → calls wrapper(message="Starting DAQ...")
      → wrapper calls root.after(0, _on_startup_status)
      → returns immediately (background thread continues its work)

Main thread (next loop iteration):
  tkinter processes its queue
    → runs _on_startup_status(message="Starting DAQ...")
      → updates the startup overlay label
```

This is the only place in the codebase where thread-to-GUI marshalling happens — all in that one `_bind_controller_events` method.

---

## Session Lifecycle

### Phase Diagram

```
IDLE ──→ STARTING ──→ RUNNING ──→ CLEANING_UP ──→ COMPLETED
           │              │
           ▼              ▼
      (cancelled)    STOPPING ──→ CLEANING_UP ──→ COMPLETED
           │
           ▼
         IDLE
```

These phases are tracked by `SessionPhase` in `core/session_state.py`.

### Detailed Flow

#### 1. Setup (IDLE phase)

**What the user sees:** A form with mouse selection, save directory, protocol tabs with parameter widgets, and a Start button.

**What happens:** `main.py` launches the Launcher window, which reads `rigs.yaml` and shows a button per rig. Clicking a rig opens a `RigWindow`, which creates a `SessionController` and shows `SetupMode`.

SetupMode generates its parameter form dynamically from whatever `get_parameters()` returns on each protocol class. When the user clicks Start, SetupMode validates inputs and packages them into a config dict:

```python
session_config = {
    "protocol_class": FullTaskWithWait,   # The class itself
    "parameters": {"num_trials": 100, "reward_duration": 0.1, ...},
    "mouse_id": "mouse_001",
    "save_directory": "D:\\behaviour_data\\cohort_name",
}
```

#### 2. Startup (STARTING phase)

**What the user sees:** An overlay with a progress log and cancel button.

**What happens:** `SessionController.start_session()` spawns a background thread that runs `_startup_sequence()` — a linear sequence of blocking calls:

```
_startup_sequence(config)
│
├── load_peripheral_config()           Build paths, resolve COM ports
├── PeripheralManager(config)          Create manager
│   ├── .start_daq()                   Launch Arduino DAQ subprocess
│   ├── .wait_for_daq_connection()     Block until signal file appears
│   ├── .start_camera()                Launch camera executable
│   └── .start_scales()                Launch scales server subprocess
│
├── serial.Serial(port, baud)          Open serial to behaviour Arduino
├── reset_arduino_via_dtr(serial)      Reset Arduino via DTR pin
├── BehaviourRigLink(serial)           Create communication layer
├── link.send_hello() / wait_hello()   Handshake with Arduino firmware
│
├── _write_session_metadata()          Save JSON with session info
│
├── Protocol(params, link)             Create protocol instance
├── PerformanceTracker()               Create tracker, wire events
└── emit("startup_complete")           Tell GUI everything is ready
```

Each step emits `"startup_status"` messages that appear in the overlay log. Between steps, the controller checks `_startup_cancelled` so the user can bail out at any point.

If anything fails, the controller emits `"startup_error"` and cleans up whatever was already started.

#### 3. Running (RUNNING phase)

**What the user sees:** Session summary, live performance stats, trial log, scales plot, session log, elapsed timer, and a Stop button.

**What happens:** After `"startup_complete"`, RigWindow switches to RunningMode and calls `controller.run_protocol()`, which spawns another background thread that calls `protocol.run()`.

The protocol's `run()` method executes the lifecycle: `_setup()` → `_run_protocol()` → `_cleanup()`. Inside `_run_protocol()`, the protocol author writes their experiment loop:

```python
def _run_protocol(self):
    self.perf_tracker.reset()
    for trial in range(self.parameters["num_trials"]):
        if self._check_abort():
            return
        self.log(f"Trial {trial + 1}")
        # ... experiment logic using self.link ...
        self.perf_tracker.success(correct_port=target, trial_duration=rt)
```

- `self.log("message")` → emits `"log"` → controller forwards as `"protocol_log"` → appears in session log
- `self.perf_tracker.success(...)` → tracker emits `"update"` → controller forwards as `"performance_update"` → RunningMode updates accuracy display
- `self._check_abort()` → returns True if the user clicked Stop

#### 4. Stopping (STOPPING phase)

When the user clicks Stop, `controller.stop_session()` calls `protocol.request_abort()`, which sets `_abort_requested = True` and calls `_on_abort()` (turns off rig outputs). The protocol loop checks this flag via `_check_abort()` and returns early.

#### 5. Cleanup (CLEANING_UP phase)

**What the user sees:** "Cleaning up..." messages in the session log.

**What happens:** After the protocol thread finishes, the controller:
1. Gathers results (final status, performance report, saves trial CSV)
2. Emits `"protocol_complete"` — RigWindow stops the timer
3. Runs hardware cleanup on a background thread:
   - `link.shutdown()` — send shutdown command to Arduino
   - `link.stop()` — stop the receive thread
   - `serial.close()` — close the serial port
   - `peripheral_manager.stop()` — stop camera, DAQ, scales subprocesses
4. Emits `"cleanup_complete"` — RigWindow switches to PostSessionMode

#### 6. Results (COMPLETED phase)

**What the user sees:** Post-session summary with status, elapsed time, save path, performance report, and a "New Session" button.

Clicking "New Session" returns to SetupMode and the cycle repeats.

---

## Thread Diagram

```
Main thread (tkinter)              Background threads
─────────────────────              ──────────────────
SetupMode visible
User fills form, clicks Start
  │
  ├──spawn────────────────────→    _startup_sequence()
  │                                  start DAQ...
StartupOverlay visible               wait for connection...
  shows status messages    ←──────   emit("startup_status")
  │                                  start camera, scales...
  │                                  open serial, handshake...
  receives startup_complete ←─────   emit("startup_complete")
  │
RunningMode visible
  │
  ├──spawn────────────────────→    _run_protocol_thread()
  │                                  protocol.run()
  shows log messages       ←──────     emit("protocol_log")
  updates accuracy display ←──────     emit("performance_update")
  shows stimulus markers   ←──────     emit("stimulus")
  │                                  protocol finishes
  receives protocol_complete ←────   emit("protocol_complete")
  │
  │                                ┌─spawn─────────────────
  │                                │ _cleanup_hardware_blocking()
  shows "Cleaning up..."          │   link.shutdown()
  │                                │   serial.close()
  │                                │   peripheral_manager.stop()
  receives cleanup_complete  ←────┘   done
  │
PostSessionMode visible
```

---

## Project Structure

```
behaviour_rig_system/
├── main.py                          # Entry point — config paths, launches launcher
│
├── core/                            # Business logic (no GUI dependency)
│   ├── session_controller.py        # Session lifecycle — startup, run, cleanup
│   ├── session_state.py             # SessionPhase, SessionConfig, SessionResult
│   ├── protocol_base.py             # BaseProtocol — abstract class for all protocols
│   ├── performance_tracker.py       # Trial outcome tracking and statistics
│   ├── peripheral_manager.py        # Orchestrates DAQ, camera, scales managers
│   ├── camera_manager.py            # Camera subprocess lifecycle
│   ├── board_registry.py            # Maps board names to COM ports
│   └── parameter_types.py           # Parameter definitions for GUI generation
│
├── protocols/                       # Experiment protocol implementations
│   ├── __init__.py                  # Auto-loader (scans folder for BaseProtocol subclasses)
│   ├── _protocol_template.py        # Template for new protocols (copy to create new ones)
│   ├── hardware_test.py             # Hardware test protocol
│   ├── full_task_with_wait.py       # Full behaviour task
│   └── auto_training.py             # Auto-training protocol
│
├── autotraining/                    # Auto-training engine (stage graph, transitions)
│   ├── engine.py                    # Runs the stage graph
│   ├── stage.py                     # Stage base class
│   ├── transitions.py               # Transition logic between stages
│   ├── persistence.py               # Save/load training state
│   └── definitions/                 # Stage and graph definitions
│
├── gui/                             # GUI layer (tkinter, no business logic)
│   ├── launcher.py                  # Multi-rig launcher window
│   ├── rig_window.py                # Thin view — modes + controller event binding
│   ├── startup_overlay.py           # Progress overlay during startup
│   ├── parameter_widget.py          # Builds parameter forms from protocol definitions
│   ├── scales_plot_widget.py        # Live weight plot (matplotlib in tkinter)
│   ├── virtual_rig_window.py        # Simulated rig controls (for testing)
│   ├── theme.py                     # Colours, fonts, widget styling
│   └── modes/
│       ├── setup_mode.py            # Session configuration form
│       ├── running_mode.py          # Live session display (stats, logs, timer)
│       └── post_session_mode.py     # Session results summary
│
├── config/
│   ├── rigs.yaml                    # Rig definitions (serial ports, peripherals)
│   └── board_registry.json          # Maps board friendly names to COM ports
│
├── post_processing/                 # Offline analysis tools
│   └── post_process_arduinoDAQ.py
│
└── tests/                           # Test scripts
    ├── test_daq_connection.py
    ├── test_camera.py
    ├── test_scales.py
    └── test_autotraining.py
```

### Key Files

| File | Role |
|------|------|
| `core/session_controller.py` | The "script" — runs the session lifecycle on background threads, emits events |
| `gui/rig_window.py` | The "display" — receives events, updates widgets, delegates user actions to controller |
| `core/protocol_base.py` | Abstract base class that all experiment protocols inherit from |
| `core/peripheral_manager.py` | Starts/stops DAQ, camera, and scales subprocesses |
| `core/performance_tracker.py` | Tracks trial outcomes (success/failure/timeout) and computes statistics |
| `gui/modes/setup_mode.py` | Config form — builds parameter widgets from protocol definitions |
| `gui/modes/running_mode.py` | Live display — performance stats, trial log, scales plot, session log |

---

## Creating New Protocols

### Quick Start

1. Copy `protocols/_protocol_template.py` to a new file (e.g. `protocols/my_protocol.py`)
2. Rename the class
3. Fill in `get_name()`, `get_description()`, `get_parameters()`, `_run_protocol()`
4. The protocol auto-loads — no registration needed

### Minimal Protocol

```python
from core.protocol_base import BaseProtocol

class MyProtocol(BaseProtocol):
    @classmethod
    def get_name(cls) -> str:
        return "My Protocol"

    @classmethod
    def get_description(cls) -> str:
        return "What this protocol does."

    @classmethod
    def get_parameters(cls) -> list:
        return []

    def _run_protocol(self) -> None:
        if self._check_abort():
            return
        self.log("Done")
```

### Protocol API

Inside `_run_protocol()`, you have access to:

| Attribute | What it is |
|-----------|------------|
| `self.parameters` | Dict of parameter values from the GUI form |
| `self.link` | `BehaviourRigLink` — controls LEDs, valves, sensors, etc. |
| `self.scales` | Scales client (`.get_weight()`) or None |
| `self.perf_tracker` | `PerformanceTracker` for recording trial outcomes |
| `self.rig_number` | Which rig this is running on |

Key methods:

| Method | Purpose |
|--------|---------|
| `self.log("message")` | Send a message to the session log |
| `self._check_abort()` | Returns True if user clicked Stop — check this in your loop |
| `self.perf_tracker.reset()` | Clear tracker and start timing |
| `self.perf_tracker.success(correct_port, trial_duration)` | Record a correct trial |
| `self.perf_tracker.failure(correct_port, chosen_port, trial_duration)` | Record an incorrect trial |
| `self.perf_tracker.timeout(correct_port, trial_duration)` | Record a timeout |
| `self.perf_tracker.stimulus(target_port)` | Log that a stimulus was presented |

### Optional Overrides

```python
def _setup(self) -> None:
    """Called before _run_protocol(). Use for initialisation."""
    pass

def _cleanup(self) -> None:
    """Called after _run_protocol() (always runs, even on error).
    Default: calls link.shutdown() to turn off rig outputs."""
    pass

def _on_abort(self) -> None:
    """Called when user clicks Stop.
    Default: calls link.shutdown() to turn off rig outputs."""
    pass
```

### Parameter Types

Parameters defined in `get_parameters()` are automatically rendered as GUI widgets in the setup form:

| Type | Widget | Example Use |
|------|--------|-------------|
| `IntParameter` | Spinbox | Trial counts, port numbers |
| `FloatParameter` | Spinbox | Delays, thresholds, durations |
| `BoolParameter` | Checkbox | Enable/disable options |
| `ChoiceParameter` | Dropdown | Selection from fixed options |
| `StringParameter` | Text entry | Free-form text input |

All parameters accept: `name`, `display_name`, `description`, `default`, `group`, `order`.
Numeric parameters also accept: `min_value`, `max_value`, `step`.

---

## Configuration

### rigs.yaml

Defines available rigs, their hardware, and experiment settings:

```yaml
global:
  baud_rate: 115200

rigs:
  - name: "Rig 1"
    serial_port: "COM7"
    board_type: "giga"
    camera_serial: "24243513"
    board_name: "behaviour_board_1"
    daq_board_name: "daq_board_1"
    enabled: true
    scales:
      board_name: "scales_board_1"
      baud_rate: 115200
      is_wired: false
      calibration_scale: 1.0
      calibration_intercept: 0.0

cohort_folders:
  - name: "My Experiment"
    directory: "D:\\behaviour_data\\my_experiment"

mice:
  - id: "mouse_001"
    description: "Control group"
```

### board_registry.json

Maps friendly board names to COM ports, so you don't hardcode COM port numbers in the rig config:

```json
{
  "behaviour_board_1": "COM7",
  "daq_board_1": "COM8",
  "scales_board_1": "COM9"
}
```

---

## Running

```bash
python main.py
```

Set `CONFIG_PATH` and `BOARD_REGISTRY_PATH` in `main.py` to point to your configuration files.

### Simulate Mode

The launcher has a "Simulate" checkbox that runs the entire system with mock hardware — useful for testing protocols and GUI changes without physical rigs connected.

---

## External Dependencies

| Package | Purpose |
|---------|---------|
| `BehavLink` | Serial communication with Arduino behaviour rigs |
| `DAQLink` | Arduino DAQ subprocess management |
| `ScalesLink` | Scales server subprocess and TCP client |
| `pyserial` | Serial port communication |
| `PyYAML` | Configuration file parsing |
| `matplotlib` | Live scales weight plot |
| `tkinter` | GUI framework (included with Python) |
