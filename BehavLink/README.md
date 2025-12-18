# Behaviour Rig

Serial communication library for Arduino-based behavioural experiment rigs.

## Installation

```bash
uv add behaviour-rig
```

Or install from source:

```bash
cd behaviour_rig
uv pip install -e .
```

## Quick Start

```python
import serial
from behaviour_rig import BehaviourRigLink, GPIOMode

with serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1) as ser:
    with BehaviourRigLink(ser) as link:
        # Establish connection
        link.send_hello()
        link.wait_hello(timeout=3.0)

        # Run a trial
        link.led_set(port=0, brightness=255)
        event = link.wait_for_event(port=0, timeout=30.0)
        link.led_set(port=0, brightness=0)
        link.valve_pulse(port=0, duration_ms=500)
```

## Hardware Capabilities

| Component | Count | Control Type | Notes |
|-----------|-------|--------------|-------|
| LEDs | 6 | Software PWM (0-255) | Port-addressable |
| Spotlights | 6 | Hardware PWM (0-255) | Port-addressable or all at once |
| IR Illuminator | 1 | Hardware PWM (0-255) | Single unit |
| Solenoid Valves | 6 | Timed pulse (1-65535 ms) | Non-blocking pulse |
| Piezo Buzzers | 6 | On/Off | Port-addressable or all at once |
| Overhead Speaker | 1 | Preset frequencies/durations | I2C module |
| GPIO Pins | 6 | Input (with events) or Output | Directly configurable |
| IR Sensor Gates | 6 | Input only | Debounced, generates events |

## API Reference

### BehaviourRigLink

The main communication class managing bidirectional serial communication with the rig.

#### Constructor

```python
BehaviourRigLink(serial_port: serial.Serial, *, receive_timeout: float = 0.1)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `serial_port` | `serial.Serial` | required | An open, configured serial port instance |
| `receive_timeout` | `float` | `0.1` | Timeout in seconds for individual read operations in the receive loop |

The class can be used as a context manager, which automatically calls `start()` on entry and `shutdown()` + `stop()` on exit:

```python
with BehaviourRigLink(ser) as link:
    # link.start() called automatically
    ...
# link.shutdown() and link.stop() called automatically
```

#### Class Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_RETRIES` | `10` | Default number of retry attempts for commands |
| `DEFAULT_TIMEOUT` | `0.2` | Default timeout in seconds for acknowledgement |
| `EVENT_BUFFER_SIZE` | `1024` | Maximum number of events buffered before oldest are discarded |
| `NUM_PORTS` | `6` | Number of LED/spotlight/valve/buzzer/sensor ports |
| `NUM_GPIO_PINS` | `6` | Number of GPIO pins |
| `ALL_PORTS` | `255` | Special value to address all ports simultaneously |

---

### Lifecycle Methods

#### `start()`

```python
start() -> None
```

Starts the background receive thread that processes incoming data from the rig. This thread handles acknowledgements for sent commands and buffers incoming sensor/GPIO events.

**Must be called before sending any commands.** If using the context manager, this is called automatically.

---

#### `stop()`

```python
stop() -> None
```

Signals the background receive thread to terminate and waits up to 1 second for it to finish. Safe to call multiple times. Does not send any commands to the rig.

---

#### `send_hello()`

```python
send_hello() -> None
```

Sends a `HELLO` handshake packet to the rig. The rig responds with `HELLO_ACK` to confirm it is ready to receive commands. This should be called after `start()` and before any other commands.

---

#### `wait_hello(timeout)`

```python
wait_hello(timeout: float = 3.0) -> None
```

Blocks until the `HELLO_ACK` response is received from the rig.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `float` | `3.0` | Maximum time to wait in seconds |

**Raises:**
- `TimeoutError` if no acknowledgement is received within the timeout
- `RuntimeError` if the receive thread encountered an error

---

#### `shutdown()`

```python
shutdown() -> None
```

Sends the shutdown command to the rig, which turns off all outputs (LEDs, valves, spotlights, IR, buzzers, speaker, GPIO outputs) and resets the Arduino. After shutdown, the rig must be re-initialised with `send_hello()` before further use.

**Note:** All GPIO configurations are lost after shutdown and must be reconfigured.

---

### LED Control

#### `led_set(port, brightness)`

```python
led_set(port: int, brightness: int) -> None
```

Sets the brightness of an LED using software PWM.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 | The LED port to control |
| `brightness` | `int` | 0-255 | Brightness level (0 = off, 255 = full brightness) |

**Raises:**
- `ValueError` if port or brightness is out of range
- `RuntimeError` if the command fails or is not acknowledged
- `TimeoutError` if the rig does not respond after retries

---

### Spotlight Control

#### `spotlight_set(port, brightness)`

```python
spotlight_set(port: int, brightness: int) -> None
```

Sets the brightness of one or all spotlights using hardware PWM. Hardware PWM provides flicker-free dimming suitable for video recording.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 or 255 | The spotlight port to control, or 255 to set all spotlights simultaneously |
| `brightness` | `int` | 0-255 | Brightness level (0 = off, 255 = full brightness) |

**Raises:**
- `ValueError` if port or brightness is out of range
- `RuntimeError` if the command fails
- `TimeoutError` if the rig does not respond after retries

---

### IR Illuminator Control

#### `ir_set(brightness)`

```python
ir_set(brightness: int) -> None
```

Sets the brightness of the infrared illuminator using hardware PWM.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `brightness` | `int` | 0-255 | Brightness level (0 = off, 255 = full brightness) |

**Raises:**
- `ValueError` if brightness is out of range
- `RuntimeError` if the command fails
- `TimeoutError` if the rig does not respond after retries

---

### Buzzer Control

#### `buzzer_set(port, state)`

```python
buzzer_set(port: int, state: bool) -> None
```

Turns a buzzer on or off.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 or 255 | The buzzer port to control, or 255 to control all buzzers simultaneously |
| `state` | `bool` | - | `True` to turn on, `False` to turn off |

**Raises:**
- `ValueError` if port is out of range
- `RuntimeError` if the command fails
- `TimeoutError` if the rig does not respond after retries

---

### Speaker Control

#### `speaker_set(frequency, duration)`

```python
speaker_set(frequency: SpeakerFrequency, duration: SpeakerDuration) -> None
```

Plays a tone on the overhead I2C speaker module. The speaker has preset frequency and duration options.

| Parameter | Type | Description |
|-----------|------|-------------|
| `frequency` | `SpeakerFrequency` | The frequency preset to play |
| `duration` | `SpeakerDuration` | How long to play the tone |

To stop a continuous tone, call `speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)`.

**Raises:**
- `ValueError` if frequency or duration codes are out of range
- `RuntimeError` if the command fails
- `TimeoutError` if the rig does not respond after retries

---

### Valve Control

#### `valve_pulse(port, duration_ms)`

```python
valve_pulse(port: int, duration_ms: int) -> None
```

Triggers a timed pulse on a solenoid valve. The valve opens immediately when the command is acknowledged and closes automatically after the specified duration. This method returns as soon as the command is acknowledged; timing is handled by the Arduino.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 | The valve port to pulse |
| `duration_ms` | `int` | 1-65535 | Pulse duration in milliseconds |

**Raises:**
- `ValueError` if port or duration is out of range
- `RuntimeError` if the command fails
- `TimeoutError` if the rig does not respond after retries

---

### GPIO Control

#### `gpio_configure(pin, mode)`

```python
gpio_configure(pin: int, mode: GPIOMode) -> None
```

Configures a GPIO pin as either input or output. This must be called before using `gpio_set()` on an output pin or before GPIO events can be received from an input pin.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `pin` | `int` | 0-5 | The GPIO pin to configure |
| `mode` | `GPIOMode` | - | `GPIOMode.OUTPUT` or `GPIOMode.INPUT` |

**Input mode behaviour:**
- The pin uses an internal pull-up resistor
- Events are generated when the pin goes LOW (activation) and HIGH (release)
- Use `wait_for_gpio_event()` to receive events

**Output mode behaviour:**
- The pin starts in the LOW state
- Use `gpio_set()` to change the pin state

**Raises:**
- `ValueError` if pin is out of range or mode is invalid
- `RuntimeError` if the command fails
- `TimeoutError` if the rig does not respond after retries

---

#### `gpio_set(pin, state)`

```python
gpio_set(pin: int, state: bool) -> None
```

Sets the output state of a GPIO pin. The pin must first be configured as an output using `gpio_configure()`.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `pin` | `int` | 0-5 | The GPIO pin to set |
| `state` | `bool` | - | `True` for HIGH, `False` for LOW |

**Raises:**
- `ValueError` if pin is out of range
- `RuntimeError` if the pin has not been configured, is configured as INPUT, or the command fails
- `TimeoutError` if the rig does not respond after retries

---

#### `gpio_get_mode(pin)`

```python
gpio_get_mode(pin: int) -> Optional[GPIOMode]
```

Returns the currently configured mode for a GPIO pin. This queries the local state cache, not the device.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `pin` | `int` | 0-5 | The GPIO pin to query |

**Returns:** `GPIOMode.OUTPUT`, `GPIOMode.INPUT`, or `None` if the pin has not been configured.

**Raises:**
- `ValueError` if pin is out of range

---

### Sensor Event Methods

Sensor events are generated by the 6 infrared sensor gates when they detect an object entering or leaving the beam.

#### `wait_for_event(port, timeout, consume, auto_acknowledge)`

```python
wait_for_event(
    *,
    port: Optional[int] = None,
    timeout: Optional[float] = None,
    consume: bool = True,
    auto_acknowledge: bool = True
) -> SensorEvent
```

Blocks until a sensor event is received. If matching events are already in the buffer, returns the most recent one immediately.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `port` | `int` or `None` | `None` | If specified, only returns events from this port (0-5). If `None`, returns events from any port. |
| `timeout` | `float` or `None` | `None` | Maximum time to wait in seconds. If `None`, waits indefinitely. |
| `consume` | `bool` | `True` | If `True`, removes the event from the buffer after returning it. If `False`, leaves the event in the buffer (peek behaviour). |
| `auto_acknowledge` | `bool` | `True` | If `True`, automatically sends an acknowledgement to the rig before returning. If `False`, you must call `acknowledge_event()` manually. |

**Returns:** A `SensorEvent` object.

**Raises:**
- `TimeoutError` if no matching event arrives within the timeout
- `RuntimeError` if the receive thread encountered an error

---

#### `get_latest_event(clear_buffer)`

```python
get_latest_event(*, clear_buffer: bool = False) -> Optional[SensorEvent]
```

Returns the most recent sensor event from the buffer without blocking.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `clear_buffer` | `bool` | `False` | If `True`, clears all buffered events after retrieving the latest one |

**Returns:** The most recent `SensorEvent`, or `None` if the buffer is empty.

---

#### `drain_events()`

```python
drain_events() -> list[SensorEvent]
```

Returns all buffered sensor events and clears the buffer. Useful for clearing stale events before starting a new trial.

**Returns:** A list of `SensorEvent` objects in chronological order (oldest first).

---

### GPIO Event Methods

GPIO events are generated by pins configured as inputs when they change state.

#### `wait_for_gpio_event(pin, timeout, consume)`

```python
wait_for_gpio_event(
    *,
    pin: Optional[int] = None,
    timeout: Optional[float] = None,
    consume: bool = True
) -> GPIOEvent
```

Blocks until a GPIO event is received. If matching events are already in the buffer, returns the most recent one immediately.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pin` | `int` or `None` | `None` | If specified, only returns events from this pin (0-5). If `None`, returns events from any pin. |
| `timeout` | `float` or `None` | `None` | Maximum time to wait in seconds. If `None`, waits indefinitely. |
| `consume` | `bool` | `True` | If `True`, removes the event from the buffer after returning it. |

**Returns:** A `GPIOEvent` object.

**Raises:**
- `TimeoutError` if no matching event arrives within the timeout
- `RuntimeError` if the receive thread encountered an error

---

#### `get_latest_gpio_event(clear_buffer)`

```python
get_latest_gpio_event(*, clear_buffer: bool = False) -> Optional[GPIOEvent]
```

Returns the most recent GPIO event from the buffer without blocking.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `clear_buffer` | `bool` | `False` | If `True`, clears all buffered GPIO events after retrieving the latest one |

**Returns:** The most recent `GPIOEvent`, or `None` if the buffer is empty.

---

#### `drain_gpio_events()`

```python
drain_gpio_events() -> list[GPIOEvent]
```

Returns all buffered GPIO events and clears the buffer.

**Returns:** A list of `GPIOEvent` objects in chronological order (oldest first).

---

### Event Acknowledgement

#### `acknowledge_event(event_id, event_type)`

```python
acknowledge_event(event_id: int, event_type: EventType) -> None
```

Sends an acknowledgement to the rig for a received event. The rig retransmits events until acknowledged, so this stops retransmission.

If using `wait_for_event()` with `auto_acknowledge=True` (the default), you do not need to call this manually for sensor events.

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | `int` | The `event_id` field from the `SensorEvent` or `GPIOEvent` |
| `event_type` | `EventType` | `EventType.SENSOR` or `EventType.GPIO` |

**Raises:**
- `RuntimeError` if the command fails
- `TimeoutError` if the rig does not respond after retries

---

### Data Classes

#### `SensorEvent`

Immutable dataclass representing a sensor trigger event.

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `int` | Unique identifier for this event (used for acknowledgement) |
| `port` | `int` | The sensor port that triggered (0-5) |
| `is_activation` | `bool` | `True` if the sensor detected an object entering, `False` if leaving |
| `timestamp_ms` | `int` | Arduino `millis()` value when the event occurred |
| `received_time` | `float` | Host-side `time.monotonic()` value when the event was received |

---

#### `GPIOEvent`

Immutable dataclass representing a GPIO input trigger event.

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `int` | Unique identifier for this event (used for acknowledgement) |
| `pin` | `int` | The GPIO pin that triggered (0-5) |
| `is_activation` | `bool` | `True` if the pin went LOW, `False` if it went HIGH |
| `timestamp_ms` | `int` | Arduino `millis()` value when the event occurred |
| `received_time` | `float` | Host-side `time.monotonic()` value when the event was received |

---

### Enumerations

#### `GPIOMode`

```python
class GPIOMode(IntEnum):
    OUTPUT = 0  # Pin configured as digital output
    INPUT = 1   # Pin configured as digital input with pull-up
```

---

#### `SpeakerFrequency`

```python
class SpeakerFrequency(IntEnum):
    OFF = 0           # No sound
    FREQ_1000_HZ = 1  # 1000 Hz
    FREQ_1500_HZ = 2  # 1500 Hz
    FREQ_2200_HZ = 3  # 2200 Hz
    FREQ_3300_HZ = 4  # 3300 Hz
    FREQ_5000_HZ = 5  # 5000 Hz
    FREQ_7000_HZ = 6  # 7000 Hz
```

---

#### `SpeakerDuration`

```python
class SpeakerDuration(IntEnum):
    OFF = 0             # No sound
    DURATION_50_MS = 1  # 50 ms
    DURATION_100_MS = 2 # 100 ms
    DURATION_200_MS = 3 # 200 ms
    DURATION_500_MS = 4 # 500 ms
    DURATION_1000_MS = 5 # 1000 ms
    DURATION_2000_MS = 6 # 2000 ms
    CONTINUOUS = 7      # Continuous until turned off
```

---

#### `EventType`

```python
class EventType(IntEnum):
    SENSOR = 0  # Event from infrared sensor gate
    GPIO = 1    # Event from GPIO input pin
```

---

### Utility Functions

#### `reset_arduino_via_dtr(serial_port, post_reset_delay)`

```python
reset_arduino_via_dtr(
    serial_port: serial.Serial,
    post_reset_delay: float = 1.2
) -> None
```

Resets an Arduino by toggling the DTR (Data Terminal Ready) line. Most Arduino boards with USB CDC trigger a hardware reset when DTR is toggled. This is useful for ensuring a clean start state.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `serial_port` | `serial.Serial` | required | The open serial port connected to the Arduino |
| `post_reset_delay` | `float` | `1.2` | Time in seconds to wait after reset for the bootloader to finish and the sketch to start |

---

#### `build_frame(command, payload)`

```python
build_frame(command: int, payload: bytes = b"") -> bytes
```

Constructs a complete framed message for the serial protocol.

Frame format: `[START][CMD][LEN_LO][LEN_HI][PAYLOAD...][CRC_LO][CRC_HI]`

| Parameter | Type | Description |
|-----------|------|-------------|
| `command` | `int` | The command byte (0x00-0xFF) |
| `payload` | `bytes` | Optional payload data |

**Returns:** The complete frame as bytes, ready for transmission.

---

#### `calculate_crc16(data)`

```python
calculate_crc16(data: bytes) -> int
```

Calculates the CRC16-CCITT-FALSE checksum for a byte sequence. Uses polynomial 0x1021 with initial value 0xFFFF.

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `bytes` | The bytes to checksum |

**Returns:** The 16-bit CRC value as an integer.

---

## Protocol Details

The library uses a binary framed protocol with the following characteristics:

- **Frame format:** `[0x02][CMD][LEN_LO][LEN_HI][PAYLOAD...][CRC_LO][CRC_HI]`
- **CRC:** CRC16-CCITT-FALSE (polynomial 0x1021, init 0xFFFF)
- **Byte order:** Little-endian for multi-byte values
- **Reliability:** Commands include sequence numbers and are retransmitted until acknowledged
- **Events:** Use a latest-wins strategy; new events supersede unacknowledged ones

## Thread Safety

The `BehaviourRigLink` class is thread-safe for concurrent access:

- Event buffers are protected by locks
- Multiple threads can wait for events simultaneously
- Command sending is serialised via the acknowledgement mechanism

However, the underlying `serial.Serial` object should only be accessed through the `BehaviourRigLink` instance while it is running.