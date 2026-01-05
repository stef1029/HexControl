"""
Hardware Abstraction Layer for Behaviour Rig.

This module provides a clean interface to the behaviour rig hardware,
wrapping the lower-level BehavLink library. It handles:
    - Connection management and error recovery
    - Hardware state tracking
    - Consistent API across different rig configurations
    - Logging via callbacks for GUI integration

The HardwareInterface class is the main entry point for protocols to
interact with the rig hardware.

Example Usage:
    with HardwareInterface(port="COM7") as hw:
        hw.connect()
        hw.led_set(0, 128)
        hw.valve_pulse(0, 100)
"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Generator

import serial

from BehavLink import (
    BehaviourRigLink,
    GPIOMode,
    SpeakerDuration,
    SpeakerFrequency,
    reset_arduino_via_dtr,
)


@dataclass
class SensorEvent:
    """
    Represents a sensor activation or deactivation event.

    Attributes:
        port: The sensor port number (0-5).
        is_activation: True if sensor was activated, False if released.
        event_id: Unique identifier for this event.
        timestamp: Time the event was received.
    """

    port: int
    is_activation: bool
    event_id: int
    timestamp: float = 0.0


class HardwareInterface:
    """
    High-level interface to the behaviour rig hardware.

    This class provides methods to control all hardware components on the
    rig, including LEDs, spotlights, buzzers, valves, and sensors. It
    wraps the BehavLink library and adds:
        - Connection state management
        - Simulation mode for testing without hardware
        - Logging callbacks for GUI integration
        - Consistent error handling

    Attributes:
        port: Serial port the rig is connected to.
        baud_rate: Communication baud rate.
        is_connected: Whether currently connected to hardware.
        simulation_mode: Whether running without real hardware.
    """

    def __init__(
        self,
        port: str = "COM7",
        baud_rate: int = 115200,
        simulation_mode: bool = False,
        log_callback: Callable[[str], None] | None = None,
    ):
        """
        Initialise the hardware interface.

        Args:
            port: Serial port to connect to (e.g., "COM7" or "/dev/ttyUSB0").
            baud_rate: Serial communication baud rate.
            simulation_mode: If True, no actual hardware communication occurs.
                Useful for testing protocols without a connected rig.
            log_callback: Optional callback function for log messages. If
                provided, all status messages will be sent to this callback
                instead of being printed to console.
        """
        self.port = port
        self.baud_rate = baud_rate
        self.simulation_mode = simulation_mode
        self._log_callback = log_callback

        self._serial: serial.Serial | None = None
        self._link: BehaviourRigLink | None = None
        self._is_connected = False

    # =========================================================================
    # Logging
    # =========================================================================

    def _log(self, message: str) -> None:
        """
        Log a message via the callback or to console.

        Args:
            message: The message to log.
        """
        if self._log_callback is not None:
            self._log_callback(message)
        else:
            print(message)

    def set_log_callback(self, callback: Callable[[str], None] | None) -> None:
        """
        Set the logging callback function.

        Args:
            callback: Function to receive log messages, or None to use console.
        """
        self._log_callback = callback

    # =========================================================================
    # Connection Management
    # =========================================================================

    def connect(self, reset_arduino: bool = True) -> None:
        """
        Establish connection with the behaviour rig.

        Args:
            reset_arduino: Whether to reset the Arduino before connecting.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        if self.simulation_mode:
            self._is_connected = True
            self._log(f"[SIMULATION] Connected to simulated rig on {self.port}")
            return

        try:
            self._log(f"Opening serial connection on {self.port}...")
            self._serial = serial.Serial(
                self.port, self.baud_rate, timeout=0.1
            )

            if reset_arduino:
                self._log("Resetting Arduino...")
                reset_arduino_via_dtr(self._serial)

            self._log("Creating BehaviourRigLink...")
            self._link = BehaviourRigLink(self._serial)
            self._link.__enter__()

            self._log("Sending hello...")
            self._link.send_hello()
            self._link.wait_hello(timeout=5.0)

            self._is_connected = True
            self._log(f"Connected to rig on {self.port}")

        except Exception as e:
            self._cleanup_connection()
            raise ConnectionError(
                f"Failed to connect to rig on {self.port}: {e}"
            ) from e

    def disconnect(self) -> None:
        """
        Close the connection to the behaviour rig.

        Safe to call even if not connected.
        """
        if self.simulation_mode:
            self._is_connected = False
            self._log("[SIMULATION] Disconnected from simulated rig")
            return

        self._cleanup_connection()
        self._log(f"Disconnected from rig on {self.port}")

    def _cleanup_connection(self) -> None:
        """Clean up connection resources."""
        if self._link is not None:
            try:
                self._link.__exit__(None, None, None)
            except Exception:
                pass
            self._link = None

        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to hardware."""
        return self._is_connected

    def __enter__(self) -> "HardwareInterface":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures disconnection."""
        self.disconnect()

    # =========================================================================
    # LED Control
    # =========================================================================

    def led_set(self, port: int, brightness: int) -> None:
        """
        Set the brightness of an LED.

        Args:
            port: LED port number (0-5).
            brightness: Brightness level (0-255, where 0 is off).

        Raises:
            ValueError: If port or brightness is out of range.
            ConnectionError: If not connected to hardware.
        """
        self._validate_port(port, 6, "LED")
        self._validate_brightness(brightness)
        self._require_connection()

        if self.simulation_mode:
            self._log(f"[SIMULATION] LED {port} set to brightness {brightness}")
            return

        self._link.led_set(port, brightness)

    def led_off(self, port: int) -> None:
        """
        Turn off an LED.

        Args:
            port: LED port number (0-5).
        """
        self.led_set(port, 0)

    def led_all_off(self) -> None:
        """Turn off all LEDs."""
        for port in range(6):
            self.led_set(port, 0)

    # =========================================================================
    # Spotlight Control
    # =========================================================================

    def spotlight_set(self, port: int, brightness: int) -> None:
        """
        Set the brightness of a spotlight.

        Args:
            port: Spotlight port number (0-5), or 255 for all spotlights.
            brightness: Brightness level (0-255, where 0 is off).

        Raises:
            ValueError: If port or brightness is out of range.
            ConnectionError: If not connected to hardware.
        """
        if port != 255:
            self._validate_port(port, 6, "Spotlight")
        self._validate_brightness(brightness)
        self._require_connection()

        if self.simulation_mode:
            if port == 255:
                self._log(
                    f"[SIMULATION] All spotlights set to brightness {brightness}"
                )
            else:
                self._log(
                    f"[SIMULATION] Spotlight {port} set to brightness {brightness}"
                )
            return

        self._link.spotlight_set(port, brightness)

    def spotlight_off(self, port: int) -> None:
        """
        Turn off a spotlight.

        Args:
            port: Spotlight port number (0-5), or 255 for all.
        """
        self.spotlight_set(port, 0)

    def spotlight_all_off(self) -> None:
        """Turn off all spotlights."""
        self.spotlight_set(255, 0)

    # =========================================================================
    # IR Illuminator Control
    # =========================================================================

    def ir_set(self, brightness: int) -> None:
        """
        Set the brightness of the IR illuminator.

        Args:
            brightness: Brightness level (0-255, where 0 is off).

        Raises:
            ValueError: If brightness is out of range.
            ConnectionError: If not connected to hardware.
        """
        self._validate_brightness(brightness)
        self._require_connection()

        if self.simulation_mode:
            self._log(f"[SIMULATION] IR illuminator set to brightness {brightness}")
            return

        self._link.ir_set(brightness)

    def ir_off(self) -> None:
        """Turn off the IR illuminator."""
        self.ir_set(0)

    # =========================================================================
    # Buzzer Control
    # =========================================================================

    def buzzer_set(self, port: int, on: bool) -> None:
        """
        Turn a buzzer on or off.

        Args:
            port: Buzzer port number (0-5), or 255 for all buzzers.
            on: True to turn on, False to turn off.

        Raises:
            ValueError: If port is out of range.
            ConnectionError: If not connected to hardware.
        """
        if port != 255:
            self._validate_port(port, 6, "Buzzer")
        self._require_connection()

        if self.simulation_mode:
            state_str = "ON" if on else "OFF"
            if port == 255:
                self._log(f"[SIMULATION] All buzzers {state_str}")
            else:
                self._log(f"[SIMULATION] Buzzer {port} {state_str}")
            return

        self._link.buzzer_set(port, on)

    def buzzer_on(self, port: int) -> None:
        """Turn a buzzer on."""
        self.buzzer_set(port, True)

    def buzzer_off(self, port: int) -> None:
        """Turn a buzzer off."""
        self.buzzer_set(port, False)

    def buzzer_all_off(self) -> None:
        """Turn off all buzzers."""
        self.buzzer_set(255, False)

    # =========================================================================
    # Speaker Control
    # =========================================================================

    def speaker_set(
        self, frequency: SpeakerFrequency, duration: SpeakerDuration
    ) -> None:
        """
        Play a tone on the overhead speaker.

        Args:
            frequency: Frequency preset to play (from BehavLink.SpeakerFrequency).
            duration: Duration preset for the tone (from BehavLink.SpeakerDuration).

        Raises:
            ConnectionError: If not connected to hardware.
        """
        self._require_connection()

        if self.simulation_mode:
            self._log(
                f"[SIMULATION] Speaker: {frequency.name}, {duration.name}"
            )
            return

        self._link.speaker_set(frequency, duration)

    def speaker_off(self) -> None:
        """Turn off the speaker."""
        self.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)

    # =========================================================================
    # Valve Control
    # =========================================================================

    def valve_pulse(self, port: int, duration_ms: int) -> None:
        """
        Pulse a solenoid valve open for a specified duration.

        Args:
            port: Valve port number (0-5).
            duration_ms: Duration to hold valve open in milliseconds.

        Raises:
            ValueError: If port or duration is out of range.
            ConnectionError: If not connected to hardware.
        """
        self._validate_port(port, 6, "Valve")
        if duration_ms < 0 or duration_ms > 10000:
            raise ValueError("Valve duration must be between 0 and 10000 ms")
        self._require_connection()

        if self.simulation_mode:
            self._log(f"[SIMULATION] Valve {port} pulsed for {duration_ms} ms")
            return

        self._link.valve_pulse(port, duration_ms)

    # =========================================================================
    # GPIO Control
    # =========================================================================

    def gpio_configure(self, pin: int, mode: GPIOMode) -> None:
        """
        Configure a GPIO pin's mode.

        Args:
            pin: GPIO pin number (0-5).
            mode: Pin mode (from BehavLink.GPIOMode).

        Raises:
            ValueError: If pin is out of range.
            ConnectionError: If not connected to hardware.
        """
        self._validate_port(pin, 6, "GPIO")
        self._require_connection()

        if self.simulation_mode:
            self._log(f"[SIMULATION] GPIO {pin} configured as {mode.name}")
            return

        self._link.gpio_configure(pin, mode)

    def gpio_set(self, pin: int, high: bool) -> None:
        """
        Set a GPIO output pin state.

        Args:
            pin: GPIO pin number (0-5).
            high: True for HIGH, False for LOW.

        Raises:
            ValueError: If pin is out of range.
            ConnectionError: If not connected to hardware.
        """
        self._validate_port(pin, 6, "GPIO")
        self._require_connection()

        if self.simulation_mode:
            state_str = "HIGH" if high else "LOW"
            self._log(f"[SIMULATION] GPIO {pin} set {state_str}")
            return

        self._link.gpio_set(pin, high)

    # =========================================================================
    # Sensor Events
    # =========================================================================

    def wait_for_sensor_event(
        self, timeout: float = 1.0, auto_acknowledge: bool = True
    ) -> SensorEvent | None:
        """
        Wait for a sensor event.

        Args:
            timeout: Maximum time to wait in seconds.
            auto_acknowledge: Whether to automatically acknowledge the event.

        Returns:
            SensorEvent if one occurred, None if timeout.

        Raises:
            ConnectionError: If not connected to hardware.
        """
        self._require_connection()

        if self.simulation_mode:
            # In simulation mode, return None (no events)
            import time
            time.sleep(min(timeout, 0.1))
            return None

        try:
            event = self._link.wait_for_event(
                timeout=timeout, auto_acknowledge=auto_acknowledge
            )
            return SensorEvent(
                port=event.port,
                is_activation=event.is_activation,
                event_id=event.event_id,
            )
        except TimeoutError:
            return None

    def drain_sensor_events(self) -> None:
        """
        Clear any pending sensor events from the buffer.

        Raises:
            ConnectionError: If not connected to hardware.
        """
        self._require_connection()

        if self.simulation_mode:
            return

        self._link.drain_events()

    # =========================================================================
    # Safety Methods
    # =========================================================================

    def all_off(self) -> None:
        """
        Turn off all outputs.

        Safe method to reset all hardware to an idle state.
        """
        if not self._is_connected:
            return

        self.led_all_off()
        self.spotlight_all_off()
        self.ir_off()
        self.buzzer_all_off()
        self.speaker_off()

        for pin in range(6):
            try:
                self.gpio_set(pin, False)
            except Exception:
                pass

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    def _validate_port(self, port: int, max_port: int, name: str) -> None:
        """Validate a port number is in range."""
        if not 0 <= port < max_port:
            raise ValueError(f"{name} port must be between 0 and {max_port - 1}")

    def _validate_brightness(self, brightness: int) -> None:
        """Validate a brightness value is in range."""
        if not 0 <= brightness <= 255:
            raise ValueError("Brightness must be between 0 and 255")

    def _require_connection(self) -> None:
        """Raise an error if not connected."""
        if not self._is_connected:
            raise ConnectionError(
                "Not connected to hardware. Call connect() first."
            )


@contextmanager
def hardware_connection(
    port: str = "COM7",
    baud_rate: int = 115200,
    simulation_mode: bool = False,
    log_callback: Callable[[str], None] | None = None,
) -> Generator[HardwareInterface, None, None]:
    """
    Context manager for hardware connections.

    Ensures the connection is properly closed even if an error occurs.

    Args:
        port: Serial port to connect to.
        baud_rate: Serial communication baud rate.
        simulation_mode: If True, no actual hardware communication occurs.
        log_callback: Optional callback for log messages.

    Yields:
        Connected HardwareInterface instance.

    Example:
        with hardware_connection("COM7") as hw:
            hw.led_set(0, 128)
    """
    hw = HardwareInterface(
        port=port,
        baud_rate=baud_rate,
        simulation_mode=simulation_mode,
        log_callback=log_callback,
    )
    try:
        hw.connect()
        yield hw
    finally:
        hw.disconnect()
