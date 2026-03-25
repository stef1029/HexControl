# Library Reference

The behaviour rig system is built on three peripheral libraries, each installable independently:

| Library | Purpose |
|---------|---------|
| [BehavLink](behavlink/index.md) | Serial communication with the behaviour Arduino (LEDs, valves, sensors, speaker, GPIO) |
| [DAQLink](daqlink/index.md) | Asynchronous data acquisition from the DAQ Arduino (HDF5 recording) |
| [ScalesLink](scaleslink/index.md) | Weight measurement from platform scales (wired/wireless, TCP client-server) |

All three are installed automatically as local dependencies when you run `pip install -e .` from the project root. They can also be used standalone outside the GUI application.
