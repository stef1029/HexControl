# BehavLink Quick Start

## Standalone usage

```python
import serial
from BehavLink import BehaviourRigLink, reset_arduino_via_dtr

# Open serial port
ser = serial.Serial("COM7", baudrate=115200, timeout=0.1)

# Reset Arduino and wait for startup
reset_arduino_via_dtr(ser)

# Create link and start receiver thread
link = BehaviourRigLink(ser, board_type="giga")
link.start()

try:
    # Handshake
    link.send_hello()
    link.wait_hello(timeout=3.0)

    # Control hardware
    link.led_set(0, 255)          # LED on at port 0
    link.valve_pulse(0, 500)      # 500ms reward at port 0

    # Wait for sensor event
    event = link.wait_for_event(timeout=10.0)
    if event:
        print(f"Port {event.port} triggered")

    link.led_set(0, 0)            # LED off

    # Shutdown Arduino
    link.shutdown()

finally:
    link.stop()
    ser.close()
```

## Context manager

```python
import serial
from BehavLink import BehaviourRigLink

ser = serial.Serial("COM7", baudrate=115200, timeout=0.1)

with BehaviourRigLink(ser) as link:
    link.send_hello()
    link.wait_hello()

    link.led_set(0, 255)
    # ... use link ...
    link.shutdown()
```

The context manager calls `start()` on entry and `stop()` on exit.

## Constructor

```python
BehaviourRigLink(
    serial_port: serial.Serial,
    *,
    receive_timeout: float = 0.1,
    board_type: str = "giga",
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `serial_port` | required | An open `serial.Serial` instance |
| `receive_timeout` | `0.1` | Timeout for serial reads (seconds) |
| `board_type` | `"giga"` | Arduino board type (`"giga"` or `"mega"`) |

## Lifecycle

1. **Create** -- `BehaviourRigLink(ser)` initialises internal state
2. **Start** -- `link.start()` spawns the receiver thread that reads incoming frames
3. **Handshake** -- `send_hello()` + `wait_hello()` verifies communication with the Arduino
4. **Use** -- Call hardware control methods and wait for events
5. **Shutdown** -- `link.shutdown()` sends the shutdown command to reset the Arduino
6. **Stop** -- `link.stop()` terminates the receiver thread
