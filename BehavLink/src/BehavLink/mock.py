"""
Mock serial stubs — stand-in for serial.Serial and reset_arduino_via_dtr.

Provides MockSerial (no-op serial port) and mock_reset_arduino_via_dtr
(skips the DTR toggle delay) for use in simulate mode and tests.

For the full simulated rig link, see BehavLink.simulation.SimulatedRig.

Usage:
    from BehavLink.mock import MockSerial, mock_reset_arduino_via_dtr

    serial_port = MockSerial()
    mock_reset_arduino_via_dtr(serial_port)
    serial_port.close()
"""


class MockSerial:
    """
    Minimal stand-in for serial.Serial.

    Supports the methods called by rig_window.py (close) and
    reset_arduino_via_dtr (dtr attribute).
    """

    def __init__(self, port: str = "MOCK", baudrate: int = 115200, timeout: float = 0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.dtr = False
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, data: bytes) -> int:
        return len(data)

    def read(self, size: int = 1) -> bytes:
        return b""

    def reset_input_buffer(self) -> None:
        pass

    def reset_output_buffer(self) -> None:
        pass


def mock_reset_arduino_via_dtr(serial_port, post_reset_delay: float = 0.0) -> None:
    """
    Mock version of reset_arduino_via_dtr that skips the delay.

    The real function toggles DTR and waits ~1.2 s for the Arduino to reboot.
    The mock just returns immediately.
    """
    pass
