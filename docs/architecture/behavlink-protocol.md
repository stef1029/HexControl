# BehavLink Protocol Specification

This page documents the wire-level binary protocol used between the host computer and the Arduino behaviour board.

## Frame format

Every message (host-to-device and device-to-host) uses the same frame structure:

```
[START] [CMD] [LEN_LO] [LEN_HI] [PAYLOAD...] [CRC_LO] [CRC_HI]
```

| Field | Bytes | Description |
|-------|-------|-------------|
| START | 1 | Always `0x02` |
| CMD | 1 | Command byte (see command table) |
| LEN_LO | 1 | Payload length, low byte |
| LEN_HI | 1 | Payload length, high byte |
| PAYLOAD | variable | Command-specific data |
| CRC_LO | 1 | CRC16 checksum, low byte |
| CRC_HI | 1 | CRC16 checksum, high byte |

Minimum frame size: 6 bytes (4 header + 0 payload + 2 CRC).

## CRC16 checksum

**Algorithm:** CRC16-CCITT-FALSE

| Property | Value |
|----------|-------|
| Polynomial | `0x1021` |
| Initial value | `0xFFFF` |
| Input reflection | No |
| Output reflection | No |

The CRC is computed over the **header + payload** bytes (START, CMD, LEN_LO, LEN_HI, and all payload bytes).

```python
def calculate_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc
```

## Command table

### Host-to-device commands

| Byte | Name | Payload | Description |
|------|------|---------|-------------|
| `0x01` | `CMD_HELLO` | 0 bytes | Handshake request |
| `0x10` | `CMD_LED_SET` | `[seq_lo, seq_hi, port, brightness]` | Set LED brightness |
| `0x11` | `CMD_SPOTLIGHT_SET` | `[seq_lo, seq_hi, port, brightness]` | Set spotlight brightness |
| `0x12` | `CMD_IR_SET` | `[seq_lo, seq_hi, brightness]` | Set IR illuminator |
| `0x13` | `CMD_BUZZER_SET` | `[seq_lo, seq_hi, port, state]` | Set buzzer on/off |
| `0x15` | `CMD_SPEAKER_SET` | `[seq_lo, seq_hi, freq, duration]` | Set speaker tone |
| `0x17` | `CMD_GPIO_CONFIG` | `[seq_lo, seq_hi, pin, mode]` | Configure GPIO pin |
| `0x18` | `CMD_GPIO_SET` | `[seq_lo, seq_hi, pin, state]` | Set GPIO output |
| `0x21` | `CMD_VALVE_PULSE` | `[seq_lo, seq_hi, port, dur_lo, dur_hi]` | Timed valve pulse |
| `0x7F` | `CMD_SHUTDOWN` | `[seq_lo, seq_hi]` | Shutdown and reset |
| `0x91` | `CMD_EVENT_ACK` | `[event_id (4 bytes), event_type]` | Acknowledge event |

### Device-to-host responses

| Byte | Name | Payload | Description |
|------|------|---------|-------------|
| `0x81` | `CMD_HELLO_ACK` | 0 bytes | Handshake response |
| `0xA0` | `CMD_ACK` | `[seq_lo, seq_hi, status]` | Command acknowledgement |
| `0x90` | `CMD_SENSOR_EVENT` | `[event_id (4 bytes), port, is_activation, timestamp_ms (4 bytes)]` | IR sensor trigger |
| `0x92` | `CMD_GPIO_EVENT` | `[event_id (4 bytes), pin, is_activation, timestamp_ms (4 bytes)]` | GPIO input change |

## Sequence numbers

All host-to-device commands (except `CMD_HELLO` and `CMD_EVENT_ACK`) include a 16-bit sequence number in the first two payload bytes (little-endian). The sequence:

- Starts at 1
- Increments per command
- Wraps at 0xFFFF back to 1 (skips 0)

The device echoes the sequence number in its `CMD_ACK` response.

## Reliable delivery

Host commands use a retry mechanism:

1. Send command with sequence number N
2. Wait up to `DEFAULT_TIMEOUT` (0.2s) for `CMD_ACK` with matching sequence N
3. If timeout, retry (up to `DEFAULT_RETRIES` = 10 times)
4. If all retries exhausted, raise an error

## Status codes

The `CMD_ACK` payload includes a status byte:

| Code | Constant | Meaning |
|------|----------|---------|
| `0x00` | `STATUS_OK` | Command executed |
| `0x01` | `STATUS_INVALID_PARAMS` | Parameters out of range |
| `0x02` | `STATUS_UNKNOWN_CMD` | Unrecognised command byte |
| `0x03` | `STATUS_WRONG_MODE` | Pin/port configured in wrong mode |

## Event protocol

Sensor and GPIO events are sent by the device asynchronously. The host must acknowledge each event to stop retransmission.

### Event payload (10 bytes)

```
[event_id (4 bytes, LE)] [port/pin (1)] [is_activation (1)] [timestamp_ms (4 bytes, LE)]
```

- `event_id` -- Unique 32-bit identifier assigned by the device
- `port/pin` -- Port 0-5 (sensor) or pin 0-5 (GPIO)
- `is_activation` -- 1 = triggered/LOW, 0 = released/HIGH
- `timestamp_ms` -- Arduino `millis()` value at trigger

### Event acknowledgement

```
CMD_EVENT_ACK (0x91): [event_id (4 bytes, LE)] [event_type (1)]
```

Event types: `0` = SENSOR, `1` = GPIO.

### Deduplication

The host uses a **latest-wins** strategy: if a new event arrives for the same port/pin with the same activation state as the latest buffered event, it replaces the old one. This prevents queue buildup during rapid triggering (e.g. a mouse repeatedly breaking and restoring a beam).
