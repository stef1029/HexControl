# BehavLink Command Reference

All commands are sent via the `BehaviourRigLink` instance. Each command is framed with a CRC16 checksum and sequence number, with automatic retry on timeout.

## Hardware control

### `led_set(port, brightness)`

Set LED brightness at a specific port.

```python
link.led_set(0, 255)   # Port 0, full brightness
link.led_set(3, 128)   # Port 3, half brightness
link.led_set(0, 0)     # Port 0, off
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 | Reward port index |
| `brightness` | `int` | 0-255 | LED brightness (0 = off) |

Command byte: `0x10`

---

### `spotlight_set(port, brightness)`

Set spotlight brightness. Uses hardware PWM for flicker-free operation.

```python
link.spotlight_set(0, 255)     # Port 0 spotlight on
link.spotlight_set(255, 255)   # ALL spotlights on
link.spotlight_set(255, 0)     # ALL spotlights off
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 or 255 | Port index, or 255 for all ports |
| `brightness` | `int` | 0-255 | Spotlight brightness (0 = off) |

Command byte: `0x11`

---

### `ir_set(brightness)`

Set IR illuminator brightness.

```python
link.ir_set(200)   # IR on
link.ir_set(0)     # IR off
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `brightness` | `int` | 0-255 | IR brightness (0 = off) |

Command byte: `0x12`

---

### `buzzer_set(port, state)`

Turn a port buzzer on or off.

```python
link.buzzer_set(0, True)    # Buzzer on at port 0
link.buzzer_set(0, False)   # Buzzer off at port 0
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 | Reward port index |
| `state` | `bool` | -- | True = on, False = off |

Command byte: `0x13`

---

### `speaker_set(frequency, duration)`

Play a tone on the overhead I2C speaker.

```python
from BehavLink import SpeakerFrequency, SpeakerDuration

link.speaker_set(SpeakerFrequency.FREQ_3300_HZ, SpeakerDuration.DURATION_500_MS)
link.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)  # Stop
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `frequency` | `SpeakerFrequency` | Tone frequency preset |
| `duration` | `SpeakerDuration` | Tone duration preset |

**SpeakerFrequency values:**

| Value | Enum |
|-------|------|
| 0 | `OFF` |
| 1 | `FREQ_1000_HZ` |
| 2 | `FREQ_1500_HZ` |
| 3 | `FREQ_2200_HZ` |
| 4 | `FREQ_3300_HZ` |
| 5 | `FREQ_5000_HZ` |
| 6 | `FREQ_7000_HZ` |

**SpeakerDuration values:**

| Value | Enum |
|-------|------|
| 0 | `OFF` |
| 1 | `DURATION_50_MS` |
| 2 | `DURATION_100_MS` |
| 3 | `DURATION_200_MS` |
| 4 | `DURATION_500_MS` |
| 5 | `DURATION_1000_MS` |
| 6 | `DURATION_2000_MS` |
| 7 | `CONTINUOUS` |

Command byte: `0x15`

---

### `valve_pulse(port, duration_ms)`

Deliver a timed solenoid valve pulse (reward delivery).

```python
link.valve_pulse(0, 500)   # 500ms pulse at port 0
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `port` | `int` | 0-5 | Reward port index |
| `duration_ms` | `int` | 1-65535 | Pulse duration in milliseconds |

Command byte: `0x21`

---

### `gpio_configure(pin, mode)`

Configure a GPIO pin as input or output.

```python
from BehavLink import GPIOMode

link.gpio_configure(0, GPIOMode.OUTPUT)   # Pin 0 as output
link.gpio_configure(1, GPIOMode.INPUT)    # Pin 1 as input (generates events)
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `pin` | `int` | 0-5 | GPIO pin index |
| `mode` | `GPIOMode` | `OUTPUT` (0) or `INPUT` (1) | Pin mode |

Command byte: `0x17`

---

### `gpio_set(pin, state)`

Set a GPIO output pin high or low.

```python
link.gpio_set(0, True)    # Pin 0 HIGH
link.gpio_set(0, False)   # Pin 0 LOW
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `pin` | `int` | GPIO pin index (0-5) |
| `state` | `bool` | True = HIGH, False = LOW |

Command byte: `0x18`

---

## Lifecycle commands

### `send_hello()` / `wait_hello(timeout)`

Handshake with the Arduino behaviour project.

```python
link.send_hello()
link.wait_hello(timeout=3.0)  # Raises TimeoutError if no response
```

Command bytes: `0x01` (send) / `0x81` (receive)

### `shutdown()`

Send shutdown command to reset the Arduino.

```python
link.shutdown()
```

Command byte: `0x7F`

## Protocol details

### Frame format

```
[0x02] [CMD] [LEN_LO] [LEN_HI] [PAYLOAD...] [CRC_LO] [CRC_HI]
```

- `0x02` -- Start byte
- `CMD` -- Command byte (see table above)
- `LEN_LO/HI` -- Payload length (little-endian, 2 bytes)
- `PAYLOAD` -- Variable-length command data
- `CRC_LO/HI` -- CRC16-CCITT-FALSE checksum (little-endian, 2 bytes)

### CRC16

Algorithm: CRC16-CCITT-FALSE (polynomial `0x1021`, initial value `0xFFFF`). Computed over the header bytes (START, CMD, LEN_LO, LEN_HI) plus the payload.

### Reliable delivery

Host-to-device commands include a sequence number (1-65535, wraps, skips 0). The device responds with `CMD_ACK` (`0xA0`) containing the sequence number and a status code. If no ACK is received within `DEFAULT_TIMEOUT` (0.2s), the command is retried up to `DEFAULT_RETRIES` (10) times.

### Status codes

| Code | Constant | Meaning |
|------|----------|---------|
| `0x00` | `STATUS_OK` | Command executed successfully |
| `0x01` | `STATUS_INVALID_PARAMS` | Parameters out of range |
| `0x02` | `STATUS_UNKNOWN_CMD` | Unknown command byte |
| `0x03` | `STATUS_WRONG_MODE` | Pin/port in wrong mode for this operation |
