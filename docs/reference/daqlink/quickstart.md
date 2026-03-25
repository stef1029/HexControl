# DAQLink Quick Start

## Using DAQManager

The typical usage is through `DAQManager`, which handles subprocess lifecycle:

```python
from DAQLink import DAQManager

manager = DAQManager(
    mouse_id="M001",
    date_time="250325_140000",
    session_folder="D:\\behaviour_data\\session",
    rig_number=1,
    daq_board_name="rig_1_daq",
    board_registry_path="C:\\path\\to\\board_registry.json",
    connection_timeout=30,
    log_callback=print,
)

# Launch the DAQ subprocess
if manager.start():
    print("DAQ subprocess started")

    # Wait for Arduino connection
    if manager.wait_for_connection():
        print("DAQ connected to Arduino")

        # ... run your experiment ...
        # DAQ records continuously in the background

    else:
        print(f"Connection failed: {manager.last_error}")

    # Stop recording and clean up
    manager.stop()
else:
    print(f"Failed to start: {manager.last_error}")
```

## What happens during a session

1. `start()` launches the DAQ serial listener as a subprocess
2. The subprocess opens the serial port, resets the Arduino via DTR, and waits for the handshake
3. `wait_for_connection()` polls for a signal file that the subprocess creates once the Arduino is connected
4. The subprocess records all incoming binary messages (rig state changes) with timestamps
5. `stop()` creates a stop signal file, waits for the subprocess to finish, and cleans up signal files
6. The subprocess saves all recorded data to an HDF5 file in the session folder

## Simulation mode

```python
manager = DAQManager(
    mouse_id="M001",
    date_time="250325_140000",
    session_folder="D:\\behaviour_data\\session",
    rig_number=1,
    simulate=True,   # Skip subprocess, return success immediately
)
```

When `simulate=True`, no subprocess is launched. `start()` and `wait_for_connection()` return `True` immediately.
