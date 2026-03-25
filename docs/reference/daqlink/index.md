# DAQLink

DAQLink provides asynchronous data acquisition from Arduino Mega DAQ boards. It records the state of all rig outputs (LEDs, valves, sensors, cues) as binary events with timestamps, saving them to HDF5 files for offline analysis.

The DAQ runs as a **subprocess** managed by `DAQManager`, with signal file coordination for start/stop synchronisation between the main application and the acquisition process.

## Guides

- [Quick Start](quickstart.md) -- Using DAQManager to record a session
- [Manager API](manager.md) -- DAQManager constructor, methods, and signal file protocol
- [Data Format](data-format.md) -- HDF5 output structure and channel map
