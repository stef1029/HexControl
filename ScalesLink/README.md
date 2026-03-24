# ScalesLink

Serial communication library for reading weight data from behavioural experiment rig scales.

## Overview

ScalesLink provides a clean interface for reading calibrated weight data from scales connected to behavioural experiment rigs. It supports both wired (rigs 3, 4) and wireless (rigs 1, 2) scale configurations.

### Features

- Background thread continuously reads and logs all scale data
- Simple `get_weight()` method returns the most recent weight
- Automatic calibration application
- CSV logging with timestamps
- Built-in calibration utility

## Installation

```bash
pip install -e .
```

## Usage

### Basic Usage

```python
from ScalesLink import Scales

# Using predefined rig configuration
with Scales(rig=3, log_path="scales_log.csv") as scales:
    weight = scales.get_weight()
    print(f"Current weight: {weight:.2f} g")
```

### Custom Configuration

```python
from ScalesLink import Scales, ScalesConfig

config = ScalesConfig(
    port="COM10",
    baud_rate=9600,
    scale=0.1725,
    intercept=-1327.66,
    is_wired=True,
)

with Scales(config=config) as scales:
    weight = scales.get_weight()
```

### Calibration

```python
from ScalesLink import run_calibration

# Interactive calibration for rig 3
run_calibration(rig=3)
```

## Rig Configurations

| Rig | Type | Port | Baud Rate |
|-----|------|------|-----------|
| 1 | Wireless | COM12 | 115200 |
| 2 | Wireless | COM5 | 115200 |
| 3 | Wired | COM10 | 9600 |
| 4 | Wired | COM12 | 9600 |

## API Reference

### Scales Class

- `start()` - Opens serial connection and starts background read thread
- `stop()` - Stops background thread and closes serial connection
- `get_weight()` - Returns most recent weight in grams (or None)
- `get_weight_with_age()` - Returns (weight, age_seconds) tuple
- `clear()` - Clears current weight reading
- `tare()` - Zeros the scales (wired only)

### ScalesConfig Dataclass

- `port` - Serial port name
- `baud_rate` - Serial baud rate
- `scale` - Calibration scale factor
- `intercept` - Calibration intercept
- `is_wired` - True for wired scales, False for wireless
