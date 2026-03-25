# Calibration

## Two-point linear calibration

ScalesLink uses a simple linear calibration model:

```
weight_grams = ((raw_value - intercept) * scale) / 1000
```

Calibration determines two values:

- **`intercept`** -- The raw reading when nothing is on the scales (zero offset)
- **`scale`** -- The conversion factor from raw units to milligrams

## Calibration procedure

Run the calibration utility:

```bash
cd ScalesLink
python -m ScalesLink.calibrate
```

The interactive procedure:

1. **Empty reading** -- Remove everything from the scales. The utility collects ~200 readings and averages them. This becomes the `intercept`
2. **100g reading** -- Place a known 100g calibration weight on the scales. The utility collects ~200 readings and averages them
3. **Calculate** -- The utility computes:
    - `calibration_scale = 100000 / (hundred_reading - empty_reading)`
    - `calibration_intercept = empty_reading`
4. **Verify** -- The utility displays the calibration line, reading distributions, and summary statistics
5. **Update config** -- Copy the printed values into your `rigs.yaml`:

```yaml
scales:
  calibration_scale: 0.22375971500351627
  calibration_intercept: -5617.39
```

!!! tip
    Run calibration separately for each rig's scales, as each load cell has different characteristics. Store the values in the rig's config entry.

## Zeroing (tare)

Zeroing resets the scales to read zero with the current load. This is useful at the start of each day to compensate for drift.

### Single rig

```python
from ScalesLink import zero_scales

success, message = zero_scales(
    com_port="COM10",
    baud_rate=115200,
    timeout=2.0,
)
print(message)
```

### All rigs

```python
from ScalesLink import zero_all_scales, get_summary

results = zero_all_scales(
    rig_configs=rig_list,   # List of rig dicts from rigs.yaml
    registry=board_registry,
)

print(get_summary(results))
```

`zero_all_scales()` iterates over all rigs, skips disabled and wireless scales, resolves board names via the registry, and tares each one.

### ZeroResult

```python
@dataclass
class ZeroResult:
    rig_name: str    # Rig display name
    com_port: str    # Resolved COM port
    success: bool    # Whether tare succeeded
    message: str     # Status message
```

!!! warning
    Zeroing is only supported for **wired scales**. Calling `tare()` on wireless scales raises a `RuntimeError`.
