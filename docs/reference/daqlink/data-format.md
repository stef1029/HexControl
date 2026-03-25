# DAQ Data Format

## Binary message format

The Arduino DAQ sends 9-byte binary messages terminated by `0x02 0x01`:

```
[byte0] [byte1] [byte2] [byte3] [byte4] [byte5] [byte6] [byte7] [byte8] [0x02] [0x01]
```

Each message contains two interleaved values:

- **Message ID** (32-bit): `(byte[0] << 24) | (byte[2] << 16) | (byte[4] << 8) | byte[6]`
- **Message word** (40-bit): `(byte[1] << 32) | (byte[3] << 24) | (byte[5] << 16) | (byte[7] << 8) | byte[8]`

The message word is a bitfield encoding the state of all rig channels.

## Channel map

Each bit in the 40-bit message word represents one channel. The channels are ordered least-significant bit first:

| Bit | Channel | Description |
|-----|---------|-------------|
| 0 | SENSOR6 | IR sensor at port 5 |
| 1 | SENSOR1 | IR sensor at port 0 |
| 2 | SENSOR5 | IR sensor at port 4 |
| 3 | SENSOR2 | IR sensor at port 1 |
| 4 | SENSOR4 | IR sensor at port 3 |
| 5 | SENSOR3 | IR sensor at port 2 |
| 6 | LED_3 | LED at port 2 |
| 7 | LED_4 | LED at port 3 |
| 8 | LED_2 | LED at port 1 |
| 9 | LED_5 | LED at port 4 |
| 10 | LED_1 | LED at port 0 |
| 11 | LED_6 | LED at port 5 |
| 12 | VALVE4 | Valve at port 3 |
| 13 | VALVE3 | Valve at port 2 |
| 14 | VALVE5 | Valve at port 4 |
| 15 | VALVE2 | Valve at port 1 |
| 16 | VALVE6 | Valve at port 5 |
| 17 | VALVE1 | Valve at port 0 |
| 18 | GO_CUE | Go cue signal |
| 19 | NOGO_CUE | No-go cue signal |
| 20 | CAMERA | Camera trigger |
| 21 | SCALES | Scales trigger |
| 22 | LASER | Laser trigger |

!!! note
    Channel numbering on the hardware doesn't map 1:1 to port indices. For example, SENSOR1 corresponds to port 0, and it's at bit position 1 (not 0).

## HDF5 output

Each session produces an HDF5 file: `{date_time}_{mouse_id}-ArduinoDAQ.h5`

### Structure

```
session-ArduinoDAQ.h5
├── message_ids          # uint32 array of sequential message IDs
├── timestamps           # float64 array of relative timestamps (seconds)
├── channel_data/
│   ├── SENSOR1          # Binary data for each channel
│   ├── SENSOR2
│   ├── ...
│   ├── LED_1
│   ├── ...
│   ├── VALVE1
│   ├── ...
│   ├── GO_CUE
│   ├── NOGO_CUE
│   ├── CAMERA
│   ├── SCALES
│   └── LASER
└── (attributes)
    ├── mouse_ID         # Mouse identifier
    ├── date_time        # Session timestamp
    ├── No_of_messages   # Total messages recorded
    ├── reliability      # Percentage of messages received correctly
    ├── time_taken       # Session duration in seconds
    └── messages_per_second  # Average acquisition rate
```

### Reading HDF5 data

```python
import h5py

with h5py.File("session-ArduinoDAQ.h5", "r") as f:
    timestamps = f["timestamps"][:]
    sensor1 = f["channel_data"]["SENSOR1"][:]
    led1 = f["channel_data"]["LED_1"][:]

    print(f"Recording duration: {timestamps[-1]:.1f}s")
    print(f"Messages recorded: {f.attrs['No_of_messages']}")
    print(f"Reliability: {f.attrs['reliability']:.1f}%")
```

## Serial protocol

| Command | Byte | Direction | Description |
|---------|------|-----------|-------------|
| Start | `0x73` (`'s'`) | Host -> Arduino | Begin acquisition |
| Echo | `0x73` (`'s'`) | Arduino -> Host | Confirm connection |
| End | `0x65` (`'e'`) | Host -> Arduino | Stop acquisition |

The host sends `'s'` and waits up to 5 seconds for the Arduino to echo `'s'` back, confirming the connection. After the echo, the Arduino begins streaming binary messages continuously.
