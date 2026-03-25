# BehavLink Simulation

BehavLink provides simulation components for testing without physical hardware.

## SimulatedRig

Drop-in replacement for `BehaviourRigLink`. Has the same public API but doesn't require serial hardware.

```python
from BehavLink.simulation import SimulatedRig, VirtualRigState

# Interactive mode (with GUI visualisation)
state = VirtualRigState()
rig = SimulatedRig(virtual_state=state)

# Passive mode (headless, all commands are no-ops)
rig = SimulatedRig()
```

### Two modes

**Interactive mode** (when `virtual_state` is provided):

- Hardware commands update the `VirtualRigState` so the GUI can visualise LED/valve/spotlight states
- `wait_for_event()` blocks on a threading condition until events are injected via `VirtualRigState.inject_sensor_event()`
- Valve pulses automatically reset after their duration

**Passive mode** (when `virtual_state` is `None`):

- All hardware commands are silently accepted (no-ops)
- `wait_for_event()` sleeps for the timeout duration and returns `None`
- Suitable for headless unit testing

### Constructor

```python
SimulatedRig(
    serial_port=None,
    virtual_state: VirtualRigState | None = None,
    *,
    receive_timeout: float = 0.1,
    clock=None,
)
```

The optional `clock` parameter accepts a `BehaviourClock` for time acceleration.

---

## VirtualRigState

Thread-safe shared state model that holds the complete hardware state. Used by `SimulatedRig` (writes state) and the GUI's `VirtualRigWindow` (reads state).

```python
from BehavLink.simulation import VirtualRigState

state = VirtualRigState()

# Hardware state is updated by SimulatedRig
# GUI reads snapshots
snapshot = state.take_snapshot_if_dirty()
if snapshot:
    print(f"LED 0 brightness: {snapshot.led_brightness[0]}")
```

### State fields

| Field | Type | Description |
|-------|------|-------------|
| `led_brightness` | `list[int]` (6) | LED brightness per port |
| `spotlight_brightness` | `list[int]` (6) | Spotlight brightness per port |
| `ir_brightness` | `int` | IR illuminator brightness |
| `buzzer_state` | `list[bool]` (6) | Buzzer on/off per port |
| `speaker_active` | `bool` | Whether speaker is playing |
| `speaker_frequency` | `int` | Current speaker frequency preset |
| `speaker_duration` | `int` | Current speaker duration preset |
| `valve_pulsing` | `list[bool]` (6) | Whether each valve is currently pulsing |
| `gpio_modes` | `list[GPIOMode \| None]` (6) | GPIO pin modes |
| `gpio_output_states` | `list[bool]` (6) | GPIO output states |

### Injecting events

The GUI (or test code) injects sensor events that `SimulatedRig.wait_for_event()` will receive:

```python
# Simulate a nose-poke at port 0
state.inject_sensor_event(port=0, is_activation=True)

# Simulate a GPIO event on pin 1
state.inject_gpio_event(pin=1, is_activation=True)
```

### Snapshots

`VirtualRigState` uses a dirty flag to track changes. The GUI polls with `take_snapshot_if_dirty()` which returns `None` if nothing changed since the last call.

```python
# Efficient polling (only processes changes)
snapshot = state.take_snapshot_if_dirty()
if snapshot is not None:
    update_gui(snapshot)
```

### Weight simulation

```python
state.set_weight(25.0)     # Set simulated platform weight
weight = state.get_weight() # Read simulated weight
```

---

## MockSerial

Minimal stand-in for `serial.Serial`. All reads return empty bytes, all writes succeed silently.

```python
from BehavLink import MockSerial

mock = MockSerial(port="MOCK", baudrate=115200)
# Use in place of serial.Serial where a port object is needed
```

### Methods

| Method | Behaviour |
|--------|-----------|
| `write(data)` | Returns `len(data)` (no-op) |
| `read(size)` | Returns `b""` |
| `close()` | No-op |
| `reset_input_buffer()` | No-op |
| `reset_output_buffer()` | No-op |

Also provides `mock_reset_arduino_via_dtr()` which skips the real reset delay.

---

## BehaviourClock

Virtual clock for time acceleration during simulation. When a `BehaviourClock` is active, `protocol.sleep()` and `protocol.now()` use virtual time instead of wall clock time.

```python
from behaviour_rig_system.simulation.behavior_clock import BehaviourClock

clock = BehaviourClock(speed=5.0)  # 5x faster than real time
clock.start()

# protocol.sleep(10.0) now completes in 2 seconds
# protocol.now() advances at 5x real time
```

This allows you to run through hundreds of trials in minutes instead of hours.
