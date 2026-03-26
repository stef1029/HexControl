# DAQLink

Arduino DAQ data acquisition library for behavioural experiment rigs.

## Overview

DAQLink provides serial communication with Arduino Mega-based DAQ systems for recording rig state during behavioural experiments. It streams binary-encoded event messages, performs incremental backups, and archives data to HDF5 and JSON formats.

### Features

- Asynchronous serial communication with Arduino Mega
- Binary message parsing with error handling
- Incremental NumPy backups during acquisition
- HDF5 and JSON archival with channel data
- Signal file coordination with companion processes (camera, etc.)
- Progress bars and coloured console output

## Installation

```bash
pip install -e .
```

## Usage

### Command Line

```bash
python -m DAQLink.serial_listen --id mouse001 --rig 1 --path D:\data\session
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--id` | Mouse ID | `NoID` |
| `--date` | Datetime stamp (YYMMDD_HHMMSS) | Current time |
| `--path` | Output directory | Current directory |
| `--rig` | Rig number (1-4) | `1` |
| `--port` | COM port (overrides rig-based selection) | None |

### Programmatic Usage

```python
import asyncio
from DAQLink import listen

asyncio.run(listen(
    new_mouse_id="mouse001",
    new_date_time="250107_143000",
    new_path="D:/data/session",
    rig="1",
))
```

## Signal File Coordination

The DAQ script coordinates with other processes using signal files:

- Creates `rig_X_arduino_connected.signal` when connected
- Watches for `rig_X_camera_finished.signal` to stop acquisition

## Output Files

- `{session}-ArduinoDAQ.h5` - HDF5 with timestamps and channel data
- `{session}-ArduinoDAQ.json` - Metadata and raw data
- `backup_files/` - Incremental NumPy backups (deleted after consolidation)

## Channel Map

All DAQ boards use the same standardised 24-channel layout. Channel names and bit positions are identical across systems, so `serial_listen.py` and the viewer work without board-specific configuration.

| Bits | Group | Channels |
|------|-------|----------|
| 0-5 | Sensors | SENSOR6, SENSOR1, SENSOR5, SENSOR2, SENSOR4, SENSOR3 |
| 6-11 | LEDs | LED_3, LED_4, LED_2, LED_5, LED_1, LED_6 |
| 12-17 | Valves | VALVE4, VALVE3, VALVE5, VALVE2, VALVE6, VALVE1 |
| 18-19 | Links | DAQ_LINK0, DAQ_LINK1 (ctrl board link pins, recorded by DAQ) |
| 20-23 | External | EXT_0, EXT_1, EXT_2, EXT_3 (extra input channels) |

### EXT pin mapping by board

The EXT channels map to different physical pins depending on the DAQ board:

| Channel | Mega DAQ | Giga DAQ |
|---------|----------|----------|
| EXT_0 | pin 50 | pin 48 |
| EXT_1 | pin 51 | pin 49 |
| EXT_2 | pin 62 (camera) | pin 50 |
| EXT_3 | pin 63 (scales) | pin 51 |
