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

| Channel | Description |
|---------|-------------|
| SENSOR1-6 | IR sensor gates |
| LED_1-6 | LED states |
| VALVE1-6 | Solenoid valve states |
| GO_CUE | Go cue signal |
| NOGO_CUE | No-go cue signal |
| CAMERA | Camera trigger |
| SCALES | Scales trigger |
| LASER | Laser trigger |
