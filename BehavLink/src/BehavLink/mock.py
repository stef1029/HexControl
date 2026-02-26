"""
Mock BehaviourRigLink - Simulates the rig serial link without hardware.

Provides the same interface as BehaviourRigLink but all commands are no-ops.
Event-waiting methods return None (simulating timeout) so protocols can
be tested without physical sensors.

Also provides MockSerial as a stand-in for serial.Serial (supports close()).

Usage:
    from BehavLink.mock import MockBehaviourRigLink, MockSerial

    serial_port = MockSerial()
    link = MockBehaviourRigLink(serial_port)
    link.start()
    link.send_hello()
    link.wait_hello(timeout=5.0)
    ...
    link.shutdown()
    link.stop()
    serial_port.close()
"""

import time
from dataclasses import dataclass
from typing import Optional

from BehavLink.link import (
    EventType,
    GPIOEvent,
    GPIOMode,
    SensorEvent,
    SpeakerDuration,
    SpeakerFrequency,
)


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
    The mock just logs and returns immediately.
    """
    pass


class MockBehaviourRigLink:
    """
    Mock BehaviourRigLink that accepts all commands as no-ops.

    Matches the public interface of BehaviourRigLink so rig_window.py
    and protocols can use it as a drop-in replacement.
    """

    # Constants (match real class)
    DEFAULT_RETRIES = 10
    DEFAULT_TIMEOUT = 0.2
    EVENT_BUFFER_SIZE = 1024
    NUM_PORTS = 6
    NUM_GPIO_PINS = 6
    ALL_PORTS = 255

    def __init__(self, serial_port=None, *, receive_timeout: float = 0.1):
        self._running = False
        self._gpio_modes: dict[int, GPIOMode] = {}

    # ----- Lifecycle -----

    def start(self) -> None:
        """Simulate starting the receive thread."""
        self._running = True

    def stop(self) -> None:
        """Simulate stopping the receive thread."""
        self._running = False

    def shutdown(self) -> None:
        """Simulate sending shutdown command to rig."""
        self._gpio_modes.clear()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        self.stop()

    # ----- Handshake -----

    def send_hello(self) -> None:
        """No-op: simulate sending HELLO."""
        pass

    def wait_hello(self, timeout: float = 3.0) -> None:
        """No-op: simulate receiving HELLO_ACK instantly."""
        pass

    # ----- Hardware control -----

    def led_set(self, port: int, brightness: int) -> None:
        pass

    def spotlight_set(self, port: int, brightness: int) -> None:
        pass

    def ir_set(self, brightness: int) -> None:
        pass

    def buzzer_set(self, port: int, state: bool) -> None:
        pass

    def speaker_set(self, frequency: SpeakerFrequency, duration: SpeakerDuration) -> None:
        pass

    def valve_pulse(self, port: int, duration_ms: int) -> None:
        pass

    # ----- GPIO -----

    def gpio_configure(self, pin: int, mode: GPIOMode) -> None:
        self._gpio_modes[pin] = mode

    def gpio_set(self, pin: int, state: bool) -> None:
        pass

    def gpio_get_mode(self, pin: int) -> Optional[GPIOMode]:
        return self._gpio_modes.get(pin)

    # ----- Sensor events -----

    def get_latest_event(self, *, clear_buffer: bool = False) -> Optional[SensorEvent]:
        return None

    def drain_events(self) -> list[SensorEvent]:
        return []

    def wait_for_event(
        self,
        *,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True,
        auto_acknowledge: bool = True,
        drain_first: bool = True,
    ) -> Optional[SensorEvent]:
        """Simulate waiting for a sensor event. Returns None (timeout)."""
        if timeout is not None:
            time.sleep(timeout)
        return None

    # ----- GPIO events -----

    def get_latest_gpio_event(self, *, clear_buffer: bool = False) -> Optional[GPIOEvent]:
        return None

    def drain_gpio_events(self) -> list[GPIOEvent]:
        return []

    def wait_for_gpio_event(
        self,
        *,
        pin: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True,
    ) -> GPIOEvent:
        """Simulate waiting for a GPIO event. Raises TimeoutError."""
        if timeout is not None:
            time.sleep(timeout)
        raise TimeoutError("MockBehaviourRigLink: no GPIO events in mock mode")

    # ----- Event acknowledgement -----

    def acknowledge_event(self, event_id: int, event_type: EventType) -> None:
        pass
