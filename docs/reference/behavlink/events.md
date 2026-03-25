# Events & Sensors

BehavLink provides an asynchronous event system for handling IR sensor beam breaks and GPIO input changes. Events are received by a background thread and buffered for the protocol to consume.

## Sensor events

Each of the 6 ports has an IR sensor that detects nose-pokes. When a beam is broken (or restored), the Arduino sends a `CMD_SENSOR_EVENT` (`0x90`) frame.

### SensorEvent dataclass

```python
@dataclass
class SensorEvent:
    event_id: int        # Unique identifier for this event
    port: int            # Which port was triggered (0-5)
    is_activation: bool  # True = beam broken, False = beam restored
    timestamp_ms: int    # Arduino millis() value at trigger
    received_time: float # Host monotonic time when received
```

### Waiting for events

```python
# Block until any sensor triggers (or timeout)
event = link.wait_for_event(timeout=10.0)

# Wait for a specific port
event = link.wait_for_event(port=0, timeout=10.0)

if event is None:
    print("Timeout")
else:
    print(f"Port {event.port}, activation={event.is_activation}")
```

**`wait_for_event()` parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `port` | `int \| None` | `None` | Filter for a specific port (None = any port) |
| `timeout` | `float \| None` | `None` | Seconds to wait (None = wait forever) |
| `consume` | `bool` | `True` | Remove the event from the buffer after returning |
| `auto_acknowledge` | `bool` | `True` | Automatically send ACK to the Arduino |
| `drain_first` | `bool` | `True` | Clear pending events before waiting |

### Non-blocking access

```python
# Get the most recent event without waiting
event = link.get_latest_event()
event = link.get_latest_event(clear_buffer=True)  # Also clear buffer

# Drain all pending events
events = link.drain_events()  # Returns list[SensorEvent]
```

### Event acknowledgement

Events are sent with an `event_id`. The Arduino retransmits events until acknowledged. By default, `wait_for_event()` sends the acknowledgement automatically (`auto_acknowledge=True`).

For manual control:

```python
from BehavLink import EventType

event = link.wait_for_event(auto_acknowledge=False)
if event:
    # ... process event ...
    link.acknowledge_event(event.event_id, EventType.SENSOR)
```

### Event buffering

Events are stored in a deque with a maximum size of 1024 entries. The buffer uses a **latest-wins deduplication** strategy: if a new event arrives for the same port with the same activation state as the latest buffered event, it replaces the old one. This prevents queue buildup during rapid triggering.

---

## GPIO events

GPIO pins configured as `INPUT` generate events when their state changes.

### GPIOEvent dataclass

```python
@dataclass
class GPIOEvent:
    event_id: int        # Unique identifier
    pin: int             # Which GPIO pin triggered (0-5)
    is_activation: bool  # True = pin went LOW, False = pin went HIGH
    timestamp_ms: int    # Arduino millis() value
    received_time: float # Host monotonic time
```

### Usage

```python
from BehavLink import GPIOMode

# Configure pin as input (enables event generation)
link.gpio_configure(1, GPIOMode.INPUT)

# Wait for GPIO event
gpio_event = link.wait_for_gpio_event(timeout=5.0)
gpio_event = link.wait_for_gpio_event(pin=1, timeout=5.0)  # Specific pin

# Non-blocking
event = link.get_latest_gpio_event()
events = link.drain_gpio_events()
```

**`wait_for_gpio_event()` parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pin` | `int \| None` | `None` | Filter for a specific pin (None = any pin) |
| `timeout` | `float \| None` | `None` | Seconds to wait |
| `consume` | `bool` | `True` | Remove from buffer after returning |

---

## Event types

The `EventType` enum distinguishes between sensor and GPIO events (used for acknowledgement):

```python
from BehavLink import EventType

EventType.SENSOR  # = 0, IR sensor events
EventType.GPIO    # = 1, GPIO input events
```

## Best practices

1. **Use short timeouts in loops** -- Call `wait_for_event(timeout=0.1)` inside a loop that also checks `self.check_stop()`, rather than using a single long timeout
2. **Drain before waiting** -- The default `drain_first=True` in `wait_for_event()` clears stale events, ensuring you only get events that occur after you start waiting
3. **Use auto-acknowledge** -- Keep the default `auto_acknowledge=True` unless you need to process the event before confirming receipt
