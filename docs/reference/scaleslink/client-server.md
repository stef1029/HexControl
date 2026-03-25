# Client-Server Architecture

ScalesLink uses a TCP client-server architecture to isolate blocking serial reads from the GUI thread. The scales hardware is read by a server running in a subprocess, and protocols access weight data through a lightweight TCP client.

## Why a subprocess?

Serial reads from the scales are blocking and continuous. Running them in the GUI process would either block the event loop or require complex threading. The subprocess architecture solves this:

1. **ScalesServer** runs in a separate process, continuously reading the serial port
2. **ScalesClient** runs in the main process, fetching weight on demand via TCP
3. Each rig gets a unique TCP port (`5100 + rig_number`) to prevent collisions

## ScalesManager

`ScalesManager` orchestrates the subprocess lifecycle and provides the client:

```python
from ScalesLink import ScalesManager

manager = ScalesManager(
    com_port="COM10",
    baud_rate=115200,
    tcp_port=5101,          # Unique per rig
    is_wired=True,
    calibration_scale=0.22375,
    calibration_intercept=-5617.39,
    session_folder="D:\\session",
    date_time="250325_140000",
    mouse_id="M001",
    log_callback=print,
)

if manager.start():
    # Client is connected and ready
    weight = manager.client.get_weight()

manager.stop()  # Graceful shutdown
```

### Constructor parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `com_port` | required | Serial port for scales hardware |
| `baud_rate` | required | Serial baud rate |
| `tcp_port` | required | TCP port for server to listen on |
| `is_wired` | `False` | Wired or wireless protocol |
| `calibration_scale` | `1.0` | Calibration scale factor |
| `calibration_intercept` | `0.0` | Calibration intercept |
| `session_folder` | `""` | For CSV log filename |
| `date_time` | `""` | For CSV log filename |
| `mouse_id` | `""` | For CSV log filename |
| `log_callback` | `None` | Status message function |
| `simulate` | `False` | Use mock client instead of subprocess |
| `virtual_rig_state` | `None` | For simulation mode (reads weight from VirtualRigState) |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `start()` | `bool` | Launch server subprocess and connect client |
| `stop()` | -- | Shutdown server gracefully |
| `is_running` | `bool` | Whether the subprocess is alive |
| `client` | `ScalesClient` | The connected TCP client |

### Simulation mode

=== "With VirtualRigState"
    ```python
    manager = ScalesManager(
        ...,
        simulate=True,
        virtual_rig_state=virtual_state,
    )
    ```
    Creates a mock client that reads weight from the `VirtualRigState` object (set by GUI sliders).

=== "Without VirtualRigState"
    ```python
    manager = ScalesManager(..., simulate=True)
    ```
    Creates a mock client that always returns `0.0g`.

---

## ScalesClient

TCP client for communicating with the scales server:

```python
from ScalesLink import ScalesClient

client = ScalesClient(tcp_port=5101)
if client.connect(timeout=10.0):
    weight = client.get_weight()
    print(f"Weight: {weight}")
    client.disconnect()
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `connect(timeout=10.0)` | `bool` | Verify connection by pinging server |
| `disconnect()` | -- | Disconnect from server (does NOT stop server) |
| `ping(timeout=5.0)` | `bool` | Check if server is responsive |
| `get_weight(timeout=5.0)` | `float \| None` | Get current calibrated weight in grams |
| `shutdown()` | `bool` | Send shutdown command to server |

### TCP protocol

Each command opens a new socket connection, sends the command string, receives the response, and closes the connection.

| Command | Response | Description |
|---------|----------|-------------|
| `PING` | `PONG` | Heartbeat check |
| `GET` | `"123.45"` or `"NONE"` | Current weight in grams |
| `SHUTDOWN` | `OK` | Graceful server shutdown |

---

## ScalesServer

The server wraps the `Scales` hardware interface and listens for TCP commands:

```python
from ScalesLink import ScalesServer, ScalesConfig

config = ScalesConfig(
    port="COM10",
    baud_rate=115200,
    scale=0.22375,
    intercept=-5617.39,
    is_wired=True,
)

server = ScalesServer(config, tcp_port=5101, log_path="scales.csv")
server.start()  # Blocks until SHUTDOWN received
```

The server is typically run as a subprocess via `ScalesManager`, not directly.

### Command-line entry point

```bash
python -m ScalesLink.server \
    --port COM10 \
    --baud 115200 \
    --tcp 5101 \
    --log scales.csv \
    --scale 0.22375 \
    --intercept -5617.39 \
    --wired
```

### Data logging

When `log_path` is configured, the server enables in-memory storage of all readings and saves them to CSV at shutdown:

```csv
timestamp_s,weight_g,message_id
0.0234,145.2300,12345
0.0456,145.2301,12346
```
