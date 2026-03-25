# Wired vs Wireless Scales

ScalesLink supports two scale hardware types with different serial protocols. The `is_wired` flag in `ScalesConfig` selects the appropriate parser.

## Wired scales

Used on rigs with direct serial connections.

| Property | Value |
|----------|-------|
| Baud rate | Typically 115200 |
| Message format | 8 binary bytes + 2-byte delimiter (`0x02 0x03`) |
| Message IDs | Yes (32-bit counter) |
| Tare support | Yes (`'t'` command) |
| Start/stop commands | `'e'` (reset), `'s'` (start) |

### Binary message format

```
[id0] [val0] [id1] [val1] [id2] [val2] [id3] [val3] [0x02] [0x03]
```

- **Even bytes** (0, 2, 4, 6): Message ID (big-endian, 32-bit)
- **Odd bytes** (1, 3, 5, 7): Raw value (big-endian, 32-bit float packed as int)

### Hardware commands

| Command | Byte | Description |
|---------|------|-------------|
| Reset | `'e'` | Reset/end acquisition |
| Start | `'s'` | Begin streaming readings |
| Tare | `'t'` | Zero the scales (blocks ~3 seconds) |

## Wireless scales

Used on rigs with Bluetooth or wireless serial adapters.

| Property | Value |
|----------|-------|
| Baud rate | Configurable (typically 115200) |
| Message format | ASCII float values, one per line |
| Message IDs | No |
| Tare support | No (raises `RuntimeError`) |
| Start/stop commands | None (streams continuously) |

### ASCII format

Each line contains a single floating-point number representing the raw scale reading:

```
-5423.12
-5422.89
-5423.45
```

## Calibration

Both types use the same linear calibration formula:

```python
weight_grams = ((raw_value - intercept) * scale) / 1000
```

- `raw_value` is the parsed integer/float from the serial data
- `intercept` is the zero-load raw reading
- `scale` is the conversion factor (determined by the calibration procedure)
- Division by 1000 converts from milligrams to grams

## Choosing the right config

In `rigs.yaml`:

```yaml
scales:
  board_name: "rig_1_scales"
  baud_rate: 115200
  is_wired: true                    # <-- set based on hardware
  calibration_scale: 0.22375
  calibration_intercept: -5617.39
```

Set `is_wired: true` for wired scales, `is_wired: false` for wireless.
