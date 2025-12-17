"""
Behaviour Rig Communication Library
====================================

This module provides a reliable serial communication interface for behavioural
experiment rigs. It handles:
    - Binary framed messaging with CRC16 checksums
    - Sequence-numbered commands with automatic retry on timeout
    - Asynchronous sensor event reception with deduplication

The communication protocol uses a latest-wins strategy for sensor events,
ensuring the host always receives the most recent trigger without queue buildup.
All six sensors are monitored continuously; events include the port number.

Hardware Capabilities
---------------------
    - 6 LEDs with brightness control (0-255, software PWM)
    - 6 solenoid valves with timed pulse delivery
    - 6 spotlights with hardware PWM brightness control
    - IR illuminator with PWM brightness control
    - 6 piezo buzzers with frequency control
    - Overhead I2C speaker with preset tones
    - 4 configurable GPIO pins (input with events or output)
    - 6 infrared sensor gates with debounced detection

Typical Usage
-------------
    with serial.Serial(port, 115200, timeout=0.1) as ser:
        link = BehaviourRigLink(ser)
        link.start()
        
        link.send_hello()
        link.wait_hello(timeout=3.0)
        
        # Configure GPIOs
        link.gpio_configure(0, GPIOMode.OUTPUT)
        link.gpio_configure(1, GPIOMode.INPUT)
        
        # Set up lighting
        link.spotlight_set(port=0, brightness=50)
        link.ir_set(brightness=255)
        
        # Run a trial
        link.led_set(port=0, brightness=255)
        event = link.wait_for_event(port=0, timeout=30.0)
        link.acknowledge_event(event.event_id)
        link.led_set(port=0, brightness=0)
        link.valve_pulse(port=0, duration_ms=500)
        
        link.shutdown()
        link.stop()
"""

import queue
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional

import serial


# =============================================================================
# Protocol Constants
# =============================================================================

START_BYTE = 0x02

# Handshake commands
CMD_HELLO = 0x01
CMD_HELLO_ACK = 0x81

# Host-to-device commands (all include sequence number)
CMD_LED_SET = 0x10
CMD_SPOTLIGHT_SET = 0x11
CMD_IR_SET = 0x12
CMD_BUZZER_SET = 0x13
CMD_SPEAKER_SET = 0x15
CMD_GPIO_CONFIG = 0x17
CMD_GPIO_SET = 0x18
CMD_VALVE_PULSE = 0x21
CMD_EVENT_ACK = 0x91
CMD_SHUTDOWN = 0x7F

# Device-to-host responses
CMD_ACK = 0xA0
CMD_SENSOR_EVENT = 0x90
CMD_GPIO_EVENT = 0x92

# Status codes
STATUS_OK = 0x00
STATUS_INVALID_PARAMS = 0x01
STATUS_UNKNOWN_CMD = 0x02
STATUS_WRONG_MODE = 0x03


# =============================================================================
# Enumerations
# =============================================================================

class GPIOMode(IntEnum):
    """
    GPIO pin configuration modes.
    
    Attributes:
        OUTPUT: Pin configured as digital output, controllable via gpio_set().
        INPUT: Pin configured as digital input with pull-up, triggers events.
    """
    OUTPUT = 0
    INPUT = 1


class SpeakerFrequency(IntEnum):
    """
    Frequency presets for the overhead I2C speaker module.
    
    These correspond to the frequency codes accepted by the speaker:
        0 = No sound
        1 = 1000 Hz
        2 = 1500 Hz
        3 = 2200 Hz (commonly used for GO cue)
        4 = 3300 Hz
        5 = 5000 Hz
        6 = 7000 Hz (commonly used for NOGO cue)
    """
    OFF = 0
    FREQ_1000_HZ = 1
    FREQ_1500_HZ = 2
    FREQ_2200_HZ = 3
    FREQ_3300_HZ = 4
    FREQ_5000_HZ = 5
    FREQ_7000_HZ = 6


class SpeakerDuration(IntEnum):
    """
    Duration presets for the overhead I2C speaker module.
    
    These correspond to the duration codes accepted by the speaker:
        0 = No sound
        1 = 50 ms
        2 = 100 ms
        3 = 200 ms
        4 = 500 ms
        5 = 1000 ms
        6 = 2000 ms
        7 = Continuous (until turned off)
    """
    OFF = 0
    DURATION_50_MS = 1
    DURATION_100_MS = 2
    DURATION_200_MS = 3
    DURATION_500_MS = 4
    DURATION_1000_MS = 5
    DURATION_2000_MS = 6
    CONTINUOUS = 7


class EventType(IntEnum):
    """
    Event type identifiers for distinguishing sensor and GPIO events.
    
    Attributes:
        SENSOR: Event from one of the 6 infrared sensor gates.
        GPIO: Event from a GPIO pin configured as input.
    """
    SENSOR = 0
    GPIO = 1


# =============================================================================
# Logging Utility
# =============================================================================

def log_message(message: str) -> None:
    """
    Prints a timestamped log message to stdout.
    
    Args:
        message: The message to log.
    """
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


# =============================================================================
# CRC16-CCITT-FALSE Implementation
# =============================================================================

def calculate_crc16(data: bytes) -> int:
    """
    Calculates the CRC16-CCITT-FALSE checksum for a byte sequence.
    
    This is the standard CRC-16 variant used in many serial protocols,
    with polynomial 0x1021 and initial value 0xFFFF.
    
    Args:
        data: The bytes to checksum.
        
    Returns:
        The 16-bit CRC value.
    """
    crc = 0xFFFF
    
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021)
            else:
                crc = (crc << 1)
            crc &= 0xFFFF
    
    return crc


# =============================================================================
# Frame Construction
# =============================================================================

def build_frame(command: int, payload: bytes = b"") -> bytes:
    """
    Constructs a complete framed message ready for transmission.
    
    Frame format: [START][CMD][LEN_LO][LEN_HI][PAYLOAD...][CRC_LO][CRC_HI]
    
    Args:
        command: The command byte identifying the message type.
        payload: Optional payload data.
        
    Returns:
        The complete frame as bytes.
    """
    header = struct.pack("<BBH", START_BYTE, command, len(payload))
    crc = calculate_crc16(header + payload)
    
    return header + payload + struct.pack("<H", crc)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class SensorEvent:
    """
    Represents a sensor trigger event received from the rig.
    
    Attributes:
        event_id: Unique identifier for this event (increments with each trigger).
        port: The sensor port that triggered (0-5).
        is_activation: True if sensor was activated, False if released.
        timestamp_ms: Arduino millis() value when the trigger was detected.
        received_time: Host-side monotonic timestamp when the event was received.
    """
    event_id: int
    port: int
    is_activation: bool
    timestamp_ms: int
    received_time: float


@dataclass(frozen=True)
class GPIOEvent:
    """
    Represents a GPIO input trigger event received from the rig.
    
    Attributes:
        event_id: Unique identifier for this event (increments with each trigger).
        pin: The GPIO pin that triggered (0-3).
        is_activation: True if GPIO went LOW (activated), False if went HIGH (released).
        timestamp_ms: Arduino millis() value when the trigger was detected.
        received_time: Host-side monotonic timestamp when the event was received.
    """
    event_id: int
    pin: int
    is_activation: bool
    timestamp_ms: int
    received_time: float


# =============================================================================
# Main Communication Class
# =============================================================================

class BehaviourRigLink:
    """
    Reliable communication link for behavioural experiment rigs.
    
    This class manages bidirectional communication with an Arduino-based rig,
    providing:
        - Reliable command delivery with sequence numbers and acknowledgements
        - Automatic retry on timeout for commands
        - Asynchronous event reception with deduplication
        - Thread-safe event buffering with wait/drain operations
        - GPIO mode tracking with local validation
    
    The protocol uses a latest-wins strategy for sensor events: if a new event
    occurs before the previous one is acknowledged, the new event takes priority.
    
    Args:
        serial_port: An open serial.Serial instance.
        receive_timeout: Timeout in seconds for individual read operations.
    
    Example:
        >>> link = BehaviourRigLink(serial_port)
        >>> link.start()
        >>> link.send_hello()
        >>> link.wait_hello()
        >>> link.gpio_configure(0, GPIOMode.OUTPUT)
        >>> link.gpio_set(0, True)
        >>> link.stop()
    """
    
    # Default retry parameters for reliable commands
    DEFAULT_RETRIES = 10
    DEFAULT_TIMEOUT = 0.2
    
    # Maximum number of events to buffer
    EVENT_BUFFER_SIZE = 1024
    
    # Port/channel count constants
    NUM_PORTS = 6
    NUM_GPIO_PINS = 4
    ALL_PORTS = 255  # Special value meaning "all ports"
    
    def __init__(self, serial_port: serial.Serial, *, receive_timeout: float = 0.1):
        """
        Initialises the communication link.
        
        Args:
            serial_port: An open serial.Serial instance configured for the rig.
            receive_timeout: Read timeout in seconds for the receive loop.
        """
        self._serial = serial_port
        self._serial.timeout = receive_timeout
        
        # Thread control
        self._stop_flag = threading.Event()
        self._receive_thread: Optional[threading.Thread] = None
        
        # Acknowledgement tracking for reliable commands
        self._ack_queues: dict[int, queue.Queue[int]] = {}
        self._ack_lock = threading.Lock()
        
        # Sensor event buffer with thread synchronisation
        self._sensor_event_buffer: deque[SensorEvent] = deque(maxlen=self.EVENT_BUFFER_SIZE)
        self._sensor_event_lock = threading.Lock()
        self._sensor_event_signal = threading.Condition(self._sensor_event_lock)
        
        # GPIO event buffer with thread synchronisation
        self._gpio_event_buffer: deque[GPIOEvent] = deque(maxlen=self.EVENT_BUFFER_SIZE)
        self._gpio_event_lock = threading.Lock()
        self._gpio_event_signal = threading.Condition(self._gpio_event_lock)
        
        # State tracking
        self._last_sensor_event_id: Optional[int] = None
        self._last_gpio_event_id: Optional[int] = None
        self._hello_received = threading.Event()
        self._receive_error: Optional[Exception] = None
        
        # GPIO mode tracking (None = unconfigured)
        self._gpio_modes: list[Optional[GPIOMode]] = [None] * self.NUM_GPIO_PINS
        self._gpio_lock = threading.Lock()
        
        # Sequence number generator (starts at 1, wraps at 0xFFFF)
        self._next_sequence = 1
    
    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    def __enter__(self) -> "BehaviourRigLink":
        """Enables use as a context manager."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensures clean shutdown when exiting context."""
        try:
            self.shutdown()
        except Exception:
            pass  # Best effort shutdown
        self.stop()
    
    def start(self) -> None:
        """
        Starts the background receive thread.
        
        Call this before sending any commands. The receive thread handles
        incoming acknowledgements and sensor events.
        """
        self._stop_flag.clear()
        self._receive_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True,
            name="BehaviourRigReceiver"
        )
        self._receive_thread.start()
    
    def stop(self) -> None:
        """
        Stops the background receive thread.
        
        Blocks until the thread terminates (with a 1 second timeout).
        Safe to call multiple times.
        """
        self._stop_flag.set()
        if self._receive_thread is not None:
            self._receive_thread.join(timeout=1.0)
    
    # -------------------------------------------------------------------------
    # Sequence Number Management
    # -------------------------------------------------------------------------
    
    def _allocate_sequence(self) -> int:
        """
        Allocates the next sequence number for a command.
        
        Sequence numbers wrap from 0xFFFF back to 1 (0 is reserved).
        
        Returns:
            The allocated sequence number.
        """
        sequence = self._next_sequence
        self._next_sequence = (self._next_sequence + 1) & 0xFFFF
        if self._next_sequence == 0:
            self._next_sequence = 1
        return sequence
    
    # -------------------------------------------------------------------------
    # Handshake
    # -------------------------------------------------------------------------
    
    def send_hello(self) -> None:
        """
        Sends a HELLO handshake request to the rig.
        
        The rig should respond with HELLO_ACK. Use wait_hello() to block
        until the acknowledgement is received.
        """
        frame = build_frame(CMD_HELLO)
        self._serial.write(frame)
        log_message("TX HELLO")
    
    def wait_hello(self, timeout: float = 3.0) -> None:
        """
        Waits for the HELLO_ACK response from the rig.
        
        Args:
            timeout: Maximum time to wait in seconds.
            
        Raises:
            TimeoutError: If no HELLO_ACK is received within the timeout.
            RuntimeError: If the receive thread encountered an error.
        """
        if not self._hello_received.wait(timeout=timeout):
            raise TimeoutError("Did not receive HELLO_ACK from rig")
        
        if self._receive_error is not None:
            raise RuntimeError(f"Receive thread error: {self._receive_error}")
    
    # -------------------------------------------------------------------------
    # Sensor Event Access
    # -------------------------------------------------------------------------
    
    def get_latest_event(self, *, clear_buffer: bool = False) -> Optional[SensorEvent]:
        """
        Returns the most recent sensor event, if any.
        
        Args:
            clear_buffer: If True, clears all buffered events after retrieval.
            
        Returns:
            The most recent SensorEvent, or None if the buffer is empty.
        """
        with self._sensor_event_lock:
            if not self._sensor_event_buffer:
                return None
            
            event = self._sensor_event_buffer[-1]
            
            if clear_buffer:
                self._sensor_event_buffer.clear()
            
            return event
    
    def drain_events(self) -> list[SensorEvent]:
        """
        Returns and clears all buffered sensor events.
        
        Returns:
            A list of all buffered events in chronological order.
        """
        with self._sensor_event_lock:
            events = list(self._sensor_event_buffer)
            self._sensor_event_buffer.clear()
            return events
    
    def wait_for_event(
        self,
        *,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True,
        auto_acknowledge: bool = True 
    ) -> SensorEvent:
        """
        Waits for a sensor event to arrive.
        
        ... existing docstring ...
        
        Args:
            port: If specified, only returns events from this port.
            timeout: Maximum time to wait in seconds (None = wait forever).
            consume: If True (default), removes the event from the buffer after
                returning it. Set to False to peek without consuming.
            auto_acknowledge: If True (default), automatically acknowledges the
                event before returning. Set to False for manual acknowledgement.
            
        Returns:
            The matching SensorEvent.
            
        Raises:
            TimeoutError: If no matching event arrives within the timeout.
            RuntimeError: If the receive thread encountered an error.
        """
        deadline = None if timeout is None else (time.monotonic() + timeout)
        
        with self._sensor_event_lock:
            while True:
                if self._receive_error is not None:
                    raise RuntimeError(f"Receive thread error: {self._receive_error}")
                
                if self._sensor_event_buffer:
                    if port is None:
                        event = self._sensor_event_buffer[-1]
                        if consume:
                            self._sensor_event_buffer.pop()
                        # Auto-acknowledge before returning
                        if auto_acknowledge:
                            # Release lock before sending to avoid potential deadlock
                            self._sensor_event_lock.release()
                            try:
                                self.acknowledge_sensor_event(event.event_id)
                            finally:
                                self._sensor_event_lock.acquire()
                        return event
                    
                    for i in range(len(self._sensor_event_buffer) - 1, -1, -1):
                        if self._sensor_event_buffer[i].port == port:
                            event = self._sensor_event_buffer[i]
                            if consume:
                                del self._sensor_event_buffer[i]
                            if auto_acknowledge:
                                self._sensor_event_lock.release()
                                try:
                                    self.acknowledge_sensor_event(event.event_id)
                                finally:
                                    self._sensor_event_lock.acquire()
                            return event
                
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Timed out waiting for sensor event")
                    self._sensor_event_signal.wait(timeout=remaining)
                else:
                    self._sensor_event_signal.wait()
    
    # -------------------------------------------------------------------------
    # GPIO Event Access
    # -------------------------------------------------------------------------
    
    def get_latest_gpio_event(self, *, clear_buffer: bool = False) -> Optional[GPIOEvent]:
        """
        Returns the most recent GPIO event, if any.
        
        Args:
            clear_buffer: If True, clears all buffered GPIO events after retrieval.
            
        Returns:
            The most recent GPIOEvent, or None if the buffer is empty.
        """
        with self._gpio_event_lock:
            if not self._gpio_event_buffer:
                return None
            
            event = self._gpio_event_buffer[-1]
            
            if clear_buffer:
                self._gpio_event_buffer.clear()
            
            return event
    
    def drain_gpio_events(self) -> list[GPIOEvent]:
        """
        Returns and clears all buffered GPIO events.
        
        Returns:
            A list of all buffered GPIO events in chronological order.
        """
        with self._gpio_event_lock:
            events = list(self._gpio_event_buffer)
            self._gpio_event_buffer.clear()
            return events
    
    def wait_for_gpio_event(
        self,
        *,
        pin: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True
    ) -> GPIOEvent:
        """
        Waits for a GPIO event to arrive.
        
        If events are already buffered, returns the most recent matching event
        immediately. Otherwise, blocks until an event arrives.
        
        Args:
            pin: If specified, only returns events from this GPIO pin.
            timeout: Maximum time to wait in seconds (None = wait forever).
            consume: If True (default), removes the event from the buffer after
                returning it. Set to False to peek without consuming.
            
        Returns:
            The matching GPIOEvent.
            
        Raises:
            TimeoutError: If no matching event arrives within the timeout.
            RuntimeError: If the receive thread encountered an error.
        """
        deadline = None if timeout is None else (time.monotonic() + timeout)
        
        with self._gpio_event_lock:
            while True:
                # Check for receive thread errors
                if self._receive_error is not None:
                    raise RuntimeError(f"Receive thread error: {self._receive_error}")
                
                # Look for a matching event (most recent first)
                if self._gpio_event_buffer:
                    if pin is None:
                        event = self._gpio_event_buffer[-1]
                        if consume:
                            self._gpio_event_buffer.pop()
                        return event
                    
                    for i in range(len(self._gpio_event_buffer) - 1, -1, -1):
                        if self._gpio_event_buffer[i].pin == pin:
                            event = self._gpio_event_buffer[i]
                            if consume:
                                del self._gpio_event_buffer[i]
                            return event
                
                # Calculate remaining wait time
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Timed out waiting for GPIO event")
                    self._gpio_event_signal.wait(timeout=remaining)
                else:
                    self._gpio_event_signal.wait()
    
    # -------------------------------------------------------------------------
    # Reliable Command Sending
    # -------------------------------------------------------------------------
    
    def _send_reliable_command(
        self,
        command: int,
        payload_data: bytes,
        *,
        retries: int = DEFAULT_RETRIES,
        timeout: float = DEFAULT_TIMEOUT
    ) -> int:
        """
        Sends a sequence-numbered command and waits for acknowledgement.
        
        Automatically retries on timeout until the retry limit is reached.
        
        Args:
            command: The command byte.
            payload_data: Additional payload data (sequence number is prepended).
            retries: Maximum number of transmission attempts.
            timeout: Time to wait for each acknowledgement.
            
        Returns:
            The status code from the acknowledgement (0 = success).
            
        Raises:
            TimeoutError: If no acknowledgement is received after all retries.
        """
        sequence = self._allocate_sequence()
        full_payload = struct.pack("<H", sequence) + payload_data
        frame = build_frame(command, full_payload)
        
        # Create a queue to receive the acknowledgement
        ack_queue: queue.Queue[int] = queue.Queue(maxsize=1)
        
        with self._ack_lock:
            self._ack_queues[sequence] = ack_queue
        
        try:
            for attempt in range(1, retries + 1):
                self._serial.write(frame)
                log_message(f"TX cmd=0x{command:02X} seq={sequence} attempt={attempt}")
                
                try:
                    status = ack_queue.get(timeout=timeout)
                    log_message(f"RX ACK seq={sequence} status=0x{status:02X}")
                    return status
                except queue.Empty:
                    log_message(f"ACK timeout seq={sequence} (retrying)")
            
            raise TimeoutError(
                f"No acknowledgement after {retries} attempts "
                f"(cmd=0x{command:02X}, seq={sequence})"
            )
        finally:
            with self._ack_lock:
                self._ack_queues.pop(sequence, None)
    
    # -------------------------------------------------------------------------
    # LED Control
    # -------------------------------------------------------------------------
    
    def led_set(self, port: int, brightness: int = 255) -> None:
        """
        Sets the brightness of an LED.
        
        The LEDs use software PWM since their pins do not support hardware PWM.
        For simple on/off control, use brightness=255 for on and brightness=0 for off.
        
        Args:
            port: The LED port (0-5).
            brightness: Brightness level (0-255, where 0=off, 255=full brightness).
                Defaults to 255 (full brightness) for backwards compatibility.
            
        Raises:
            ValueError: If port or brightness is out of range.
            RuntimeError: If the command fails.
        """
        if not 0 <= port < self.NUM_PORTS:
            raise ValueError(f"Port must be 0-{self.NUM_PORTS - 1}, got {port}")
        if not 0 <= brightness <= 255:
            raise ValueError(f"Brightness must be 0-255, got {brightness}")
        
        payload = struct.pack("<BB", port, brightness)
        status = self._send_reliable_command(CMD_LED_SET, payload)
        
        if status != 0:
            raise RuntimeError(f"LED_SET failed with status=0x{status:02X}")
    
    def led_on(self, port: int) -> None:
        """
        Turns an LED on at full brightness.
        
        Convenience method equivalent to led_set(port, brightness=255).
        
        Args:
            port: The LED port (0-5).
        """
        self.led_set(port, brightness=255)
    
    def led_off(self, port: int) -> None:
        """
        Turns an LED off.
        
        Convenience method equivalent to led_set(port, brightness=0).
        
        Args:
            port: The LED port (0-5).
        """
        self.led_set(port, brightness=0)
    
    # -------------------------------------------------------------------------
    # Spotlight Control
    # -------------------------------------------------------------------------
    
    def spotlight_set(self, port: int, brightness: int) -> None:
        """
        Sets the brightness of a spotlight or all spotlights.
        
        Spotlights use hardware PWM for smooth dimming without flicker.
        
        Args:
            port: The spotlight port (0-5), or 255 to set all spotlights.
            brightness: Brightness level (0-255).
            
        Raises:
            ValueError: If port or brightness is out of range.
            RuntimeError: If the command fails.
        """
        if port != self.ALL_PORTS and not 0 <= port < self.NUM_PORTS:
            raise ValueError(f"Port must be 0-{self.NUM_PORTS - 1} or 255, got {port}")
        if not 0 <= brightness <= 255:
            raise ValueError(f"Brightness must be 0-255, got {brightness}")
        
        payload = struct.pack("<BB", port, brightness)
        status = self._send_reliable_command(CMD_SPOTLIGHT_SET, payload)
        
        if status != 0:
            raise RuntimeError(f"SPOTLIGHT_SET failed with status=0x{status:02X}")
    
    def spotlight_all_set(self, brightness: int) -> None:
        """
        Sets all spotlights to the same brightness.
        
        Convenience method equivalent to spotlight_set(255, brightness).
        
        Args:
            brightness: Brightness level (0-255).
        """
        self.spotlight_set(self.ALL_PORTS, brightness)
    
    def spotlight_all_off(self) -> None:
        """
        Turns off all spotlights.
        
        Convenience method equivalent to spotlight_set(255, 0).
        """
        self.spotlight_set(self.ALL_PORTS, 0)
    
    # -------------------------------------------------------------------------
    # IR Illuminator Control
    # -------------------------------------------------------------------------
    
    def ir_set(self, brightness: int) -> None:
        """
        Sets the brightness of the IR illuminator.
        
        The IR illuminator uses hardware PWM.
        
        Args:
            brightness: Brightness level (0-255).
            
        Raises:
            ValueError: If brightness is out of range.
            RuntimeError: If the command fails.
        """
        if not 0 <= brightness <= 255:
            raise ValueError(f"Brightness must be 0-255, got {brightness}")
        
        payload = struct.pack("<B", brightness)
        status = self._send_reliable_command(CMD_IR_SET, payload)
        
        if status != 0:
            raise RuntimeError(f"IR_SET failed with status=0x{status:02X}")
    
    def ir_on(self) -> None:
        """
        Turns the IR illuminator on at full brightness.
        
        Convenience method equivalent to ir_set(255).
        """
        self.ir_set(255)
    
    def ir_off(self) -> None:
        """
        Turns the IR illuminator off.
        
        Convenience method equivalent to ir_set(0).
        """
        self.ir_set(0)
    
    # -------------------------------------------------------------------------
    # Buzzer Control
    # -------------------------------------------------------------------------
    
    def buzzer_set(self, port: int, state: bool) -> None:
        """
        Sets the state of a buzzer or all buzzers.
        
        Args:
            port: The buzzer port (0-5), or 255 to control all buzzers.
            state: True to turn on, False to turn off.
            
        Raises:
            ValueError: If port is out of range.
            RuntimeError: If the command fails.
        """
        if port != self.ALL_PORTS and not 0 <= port < self.NUM_PORTS:
            raise ValueError(f"Port must be 0-{self.NUM_PORTS - 1} or 255, got {port}")
        
        state_byte = 1 if state else 0
        payload = struct.pack("<BB", port, state_byte)
        status = self._send_reliable_command(CMD_BUZZER_SET, payload)
        
        if status != 0:
            raise RuntimeError(f"BUZZER_SET failed with status=0x{status:02X}")
    
    # -------------------------------------------------------------------------
    # Overhead Speaker Control
    # -------------------------------------------------------------------------
    
    def speaker_set(
        self,
        frequency: SpeakerFrequency,
        duration: SpeakerDuration
    ) -> None:
        """
        Sets the overhead I2C speaker to play a sound.
        
        The speaker module has preset frequencies and durations. Use the
        SpeakerFrequency and SpeakerDuration enums for type safety, or
        pass integer codes directly.
        
        Common combinations:
            - GO cue: SpeakerFrequency.FREQ_2200_HZ, SpeakerDuration.CONTINUOUS
            - NOGO cue: SpeakerFrequency.FREQ_7000_HZ, SpeakerDuration.CONTINUOUS
            - Off: SpeakerFrequency.OFF, SpeakerDuration.OFF
        
        Args:
            frequency: Frequency preset (0-6 or SpeakerFrequency enum).
            duration: Duration preset (0-7 or SpeakerDuration enum).
            
        Raises:
            ValueError: If frequency or duration codes are out of range.
            RuntimeError: If the command fails.
        """
        freq_code = int(frequency)
        dur_code = int(duration)
        
        if not 0 <= freq_code <= 6:
            raise ValueError(f"Frequency code must be 0-6, got {freq_code}")
        if not 0 <= dur_code <= 7:
            raise ValueError(f"Duration code must be 0-7, got {dur_code}")
        
        payload = struct.pack("<BB", freq_code, dur_code)
        status = self._send_reliable_command(CMD_SPEAKER_SET, payload)
        
        if status != 0:
            raise RuntimeError(f"SPEAKER_SET failed with status=0x{status:02X}")
    
    def speaker_off(self) -> None:
        """
        Turns off the overhead speaker.
        
        Convenience method equivalent to speaker_set(OFF, OFF).
        """
        self.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)
    
    def speaker_go_cue(self, on: bool = True) -> None:
        """
        Activates or deactivates the GO cue sound (2200 Hz continuous).
        
        Args:
            on: True to start the GO cue, False to stop it.
        """
        if on:
            self.speaker_set(SpeakerFrequency.FREQ_2200_HZ, SpeakerDuration.CONTINUOUS)
        else:
            self.speaker_off()
    
    def speaker_nogo_cue(self, on: bool = True) -> None:
        """
        Activates or deactivates the NOGO cue sound (7000 Hz continuous).
        
        Args:
            on: True to start the NOGO cue, False to stop it.
        """
        if on:
            self.speaker_set(SpeakerFrequency.FREQ_7000_HZ, SpeakerDuration.CONTINUOUS)
        else:
            self.speaker_off()
    
    # -------------------------------------------------------------------------
    # GPIO Control
    # -------------------------------------------------------------------------
    
    def gpio_configure(self, pin: int, mode: GPIOMode) -> None:
        """
        Configures a GPIO pin as input or output.
        
        This must be called before using gpio_set() or waiting for GPIO events.
        
        When configured as INPUT:
            - The pin uses an internal pull-up resistor
            - Events are triggered when the pin goes LOW (activation) or HIGH (release)
            - Use wait_for_gpio_event() to receive events
        
        When configured as OUTPUT:
            - The pin starts LOW
            - Use gpio_set() to change the state
        
        Args:
            pin: The GPIO pin (0-3).
            mode: GPIOMode.OUTPUT or GPIOMode.INPUT.
            
        Raises:
            ValueError: If pin is out of range or mode is invalid.
            RuntimeError: If the command fails.
        """
        if not 0 <= pin < self.NUM_GPIO_PINS:
            raise ValueError(f"Pin must be 0-{self.NUM_GPIO_PINS - 1}, got {pin}")
        if not isinstance(mode, GPIOMode):
            raise ValueError(f"Mode must be GPIOMode.OUTPUT or GPIOMode.INPUT, got {mode}")
        
        payload = struct.pack("<BB", pin, int(mode))
        status = self._send_reliable_command(CMD_GPIO_CONFIG, payload)
        
        if status != 0:
            raise RuntimeError(f"GPIO_CONFIG failed with status=0x{status:02X}")
        
        # Update local mode tracking
        with self._gpio_lock:
            self._gpio_modes[pin] = mode
    
    def gpio_set(self, pin: int, state: bool) -> None:
        """
        Sets the state of a GPIO output pin.
        
        The pin must first be configured as an output using gpio_configure().
        
        Args:
            pin: The GPIO pin (0-3).
            state: True for HIGH, False for LOW.
            
        Raises:
            ValueError: If pin is out of range.
            RuntimeError: If the pin is not configured as output, or command fails.
        """
        if not 0 <= pin < self.NUM_GPIO_PINS:
            raise ValueError(f"Pin must be 0-{self.NUM_GPIO_PINS - 1}, got {pin}")
        
        # Check local mode tracking
        with self._gpio_lock:
            current_mode = self._gpio_modes[pin]
        
        if current_mode is None:
            raise RuntimeError(
                f"GPIO pin {pin} has not been configured. "
                f"Call gpio_configure(pin, GPIOMode.OUTPUT) first."
            )
        
        if current_mode != GPIOMode.OUTPUT:
            raise RuntimeError(
                f"GPIO pin {pin} is configured as INPUT, cannot set output state. "
                f"Reconfigure with gpio_configure(pin, GPIOMode.OUTPUT) to use as output."
            )
        
        state_byte = 1 if state else 0
        payload = struct.pack("<BB", pin, state_byte)
        status = self._send_reliable_command(CMD_GPIO_SET, payload)
        
        if status == STATUS_WRONG_MODE:
            raise RuntimeError(
                f"GPIO pin {pin} is configured as INPUT on the device. "
                f"Reconfigure with gpio_configure(pin, GPIOMode.OUTPUT) to use as output."
            )
        elif status != 0:
            raise RuntimeError(f"GPIO_SET failed with status=0x{status:02X}")
    
    def gpio_on(self, pin: int) -> None:
        """
        Sets a GPIO output pin HIGH.
        
        Convenience method equivalent to gpio_set(pin, True).
        
        Args:
            pin: The GPIO pin (0-3).
        """
        self.gpio_set(pin, True)
    
    def gpio_off(self, pin: int) -> None:
        """
        Sets a GPIO output pin LOW.
        
        Convenience method equivalent to gpio_set(pin, False).
        
        Args:
            pin: The GPIO pin (0-3).
        """
        self.gpio_set(pin, False)
    
    def gpio_get_mode(self, pin: int) -> Optional[GPIOMode]:
        """
        Returns the currently configured mode for a GPIO pin.
        
        Args:
            pin: The GPIO pin (0-3).
            
        Returns:
            GPIOMode.OUTPUT, GPIOMode.INPUT, or None if not yet configured.
            
        Raises:
            ValueError: If pin is out of range.
        """
        if not 0 <= pin < self.NUM_GPIO_PINS:
            raise ValueError(f"Pin must be 0-{self.NUM_GPIO_PINS - 1}, got {pin}")
        
        with self._gpio_lock:
            return self._gpio_modes[pin]
    
    # -------------------------------------------------------------------------
    # Valve Control
    # -------------------------------------------------------------------------
    
    def valve_pulse(self, port: int, duration_ms: int) -> None:
        """
        Triggers a timed pulse on a solenoid valve.
        
        The valve opens immediately and closes automatically after the
        specified duration. This is non-blocking; the Arduino handles
        the timing internally.
        
        Args:
            port: The valve port (0-5).
            duration_ms: Pulse duration in milliseconds (1-65535).
            
        Raises:
            ValueError: If port or duration is out of range.
            RuntimeError: If the command fails.
        """
        if not 0 <= port < self.NUM_PORTS:
            raise ValueError(f"Port must be 0-{self.NUM_PORTS - 1}, got {port}")
        if not 1 <= duration_ms <= 65535:
            raise ValueError(f"Duration must be 1-65535 ms, got {duration_ms}")
        
        payload = struct.pack("<BH", port, duration_ms)
        status = self._send_reliable_command(CMD_VALVE_PULSE, payload)
        
        if status != 0:
            raise RuntimeError(f"VALVE_PULSE failed with status=0x{status:02X}")
    
    # -------------------------------------------------------------------------
    # Event Acknowledgement
    # -------------------------------------------------------------------------
    
    def acknowledge_event(
        self,
        event_id: int,
        event_type: EventType = EventType.SENSOR
    ) -> None:
        """
        Acknowledges receipt of a sensor or GPIO event.
        
        The rig will stop retransmitting the event once it receives this
        acknowledgement.
        
        Args:
            event_id: The event_id from the SensorEvent or GPIOEvent to acknowledge.
            event_type: EventType.SENSOR or EventType.GPIO.
            
        Raises:
            RuntimeError: If the command fails.
        """
        payload = struct.pack("<BH", int(event_type), event_id)
        status = self._send_reliable_command(CMD_EVENT_ACK, payload)
        
        if status != 0:
            raise RuntimeError(f"EVENT_ACK failed with status=0x{status:02X}")
    
    def acknowledge_sensor_event(self, event_id: int) -> None:
        """
        Acknowledges receipt of a sensor event.
        
        Convenience method equivalent to acknowledge_event(event_id, EventType.SENSOR).
        
        Args:
            event_id: The event_id from the SensorEvent to acknowledge.
        """
        self.acknowledge_event(event_id, EventType.SENSOR)
    
    def acknowledge_gpio_event(self, event_id: int) -> None:
        """
        Acknowledges receipt of a GPIO event.
        
        Convenience method equivalent to acknowledge_event(event_id, EventType.GPIO).
        
        Args:
            event_id: The event_id from the GPIOEvent to acknowledge.
        """
        self.acknowledge_event(event_id, EventType.GPIO)
    
    # -------------------------------------------------------------------------
    # Shutdown
    # -------------------------------------------------------------------------
    
    def shutdown(self) -> None:
        """
        Shuts down the rig, turning off all outputs and resetting the device.
        
        This turns off all LEDs, valves, spotlights, IR, buzzers, speaker,
        and GPIO outputs, then resets the Arduino. The rig will need to be
        re-initialised with send_hello() after a shutdown.
        
        Note: GPIO configurations are lost after shutdown and must be
        reconfigured.
        """
        status = self._send_reliable_command(CMD_SHUTDOWN, b"")
        log_message(f"Shutdown acknowledged with status=0x{status:02X}")
        
        # Reset local GPIO mode tracking
        with self._gpio_lock:
            self._gpio_modes = [None] * self.NUM_GPIO_PINS
    
    # -------------------------------------------------------------------------
    # Frame Reception
    # -------------------------------------------------------------------------
    
    def _read_exact(self, num_bytes: int) -> bytes:
        """
        Reads exactly the specified number of bytes from serial.
        
        Args:
            num_bytes: The number of bytes to read.
            
        Returns:
            The received bytes.
            
        Raises:
            TimeoutError: If the read times out before all bytes are received.
        """
        buffer = bytearray()
        
        while len(buffer) < num_bytes and not self._stop_flag.is_set():
            chunk = self._serial.read(num_bytes - len(buffer))
            if not chunk:
                raise TimeoutError(
                    f"Timeout reading {num_bytes} bytes (received {len(buffer)})"
                )
            buffer.extend(chunk)
        
        return bytes(buffer)
    
    def _receive_frame(self) -> Optional[tuple[int, bytes]]:
        """
        Attempts to receive a complete framed message.
        
        Scans for the start byte, then reads the header, payload, and CRC.
        Validates the CRC before returning.
        
        Returns:
            A tuple of (command, payload) if a valid frame was received,
            or None if no data was available (normal idle condition).
            
        Raises:
            TimeoutError: If a frame starts but doesn't complete.
            ValueError: If the CRC check fails.
        """
        # Scan for start byte
        while not self._stop_flag.is_set():
            byte = self._serial.read(1)
            if not byte:
                return None  # No data available (normal idle)
            if byte[0] == START_BYTE:
                break
        
        if self._stop_flag.is_set():
            return None
        
        # Read command and length (may raise TimeoutError if stream stalls)
        header_rest = self._read_exact(3)
        command = header_rest[0]
        payload_length = struct.unpack_from("<H", header_rest, 1)[0]
        
        # Read payload and CRC
        payload = self._read_exact(payload_length)
        crc_bytes = self._read_exact(2)
        
        # Verify CRC
        received_crc = struct.unpack("<H", crc_bytes)[0]
        full_header = bytes([START_BYTE]) + header_rest
        calculated_crc = calculate_crc16(full_header + payload)
        
        if received_crc != calculated_crc:
            raise ValueError(
                f"CRC mismatch: received=0x{received_crc:04X}, "
                f"calculated=0x{calculated_crc:04X}"
            )
        
        return command, payload
    
    def _receive_loop(self) -> None:
        """
        Background thread that continuously receives and processes frames.
        
        Handles HELLO_ACK, command acknowledgements, sensor events, and GPIO events.
        Errors are captured and made available through wait methods.
        """
        try:
            while not self._stop_flag.is_set():
                message = self._receive_frame()
                
                if message is None:
                    continue  # Idle, no data available
                
                command, payload = message
                
                if command == CMD_HELLO_ACK:
                    self._hello_received.set()
                
                elif command == CMD_ACK:
                    if len(payload) != 3:
                        continue  # Malformed ACK
                    
                    sequence = struct.unpack_from("<H", payload, 0)[0]
                    status = payload[2]
                    
                    with self._ack_lock:
                        ack_queue = self._ack_queues.get(sequence)
                    
                    if ack_queue is not None:
                        ack_queue.put(status)
                
                elif command == CMD_SENSOR_EVENT:
                    if len(payload) != 8:
                        continue  # Malformed event
                    
                    event_id = struct.unpack_from("<H", payload, 0)[0]
                    port = payload[2]
                    is_activation = payload[3] == 1
                    timestamp_ms = struct.unpack_from("<I", payload, 4)[0]
                    
                    # Deduplicate repeated transmissions of the same event
                    if self._last_sensor_event_id == event_id:
                        # Still notify waiters (they may be waiting for any signal)
                        with self._sensor_event_lock:
                            self._sensor_event_signal.notify_all()
                        continue
                    
                    self._last_sensor_event_id = event_id
                    
                    event = SensorEvent(
                        event_id=event_id,
                        port=port,
                        is_activation=is_activation,
                        timestamp_ms=timestamp_ms,
                        received_time=time.monotonic()
                    )
                    
                    with self._sensor_event_lock:
                        self._sensor_event_buffer.append(event)
                        self._sensor_event_signal.notify_all()
                
                elif command == CMD_GPIO_EVENT:
                    if len(payload) != 8:
                        continue  # Malformed event
                    
                    event_id = struct.unpack_from("<H", payload, 0)[0]
                    pin = payload[2]
                    is_activation = payload[3] == 1
                    timestamp_ms = struct.unpack_from("<I", payload, 4)[0]
                    
                    # Deduplicate repeated transmissions of the same event
                    if self._last_gpio_event_id == event_id:
                        # Still notify waiters (they may be waiting for any signal)
                        with self._gpio_event_lock:
                            self._gpio_event_signal.notify_all()
                        continue
                    
                    self._last_gpio_event_id = event_id
                    
                    event = GPIOEvent(
                        event_id=event_id,
                        pin=pin,
                        is_activation=is_activation,
                        timestamp_ms=timestamp_ms,
                        received_time=time.monotonic()
                    )
                    
                    with self._gpio_event_lock:
                        self._gpio_event_buffer.append(event)
                        self._gpio_event_signal.notify_all()
                
                # Unknown commands are silently ignored
        
        except Exception as error:
            self._receive_error = error
            # Wake up any waiting threads so they can see the error
            with self._sensor_event_lock:
                self._sensor_event_signal.notify_all()
            with self._gpio_event_lock:
                self._gpio_event_signal.notify_all()


# =============================================================================
# Utility Functions
# =============================================================================

def reset_arduino_via_dtr(serial_port: serial.Serial, post_reset_delay: float = 1.2) -> None:
    """
    Resets an Arduino-class device by toggling the DTR line.
    
    Many Arduino USB CDC implementations trigger a hardware reset when DTR
    is toggled. This ensures tests start from a known state and clears any
    stale data in the serial buffers.
    
    Args:
        serial_port: The open serial port connected to the Arduino.
        post_reset_delay: Time to wait after reset for the device to boot.
    """
    serial_port.dtr = False
    time.sleep(0.2)
    
    serial_port.reset_input_buffer()
    serial_port.reset_output_buffer()
    
    serial_port.dtr = True
    time.sleep(post_reset_delay)


# =============================================================================
# Test Script
# =============================================================================

def main() -> None:
    """
    Runs a comprehensive test sequence demonstrating all rig capabilities.
    
    This test sequence:
        1. Establishes connection with handshake
        2. Tests IR illuminator
        3. Tests spotlight control (individual and all)
        4. Tests buzzer tones
        5. Tests overhead speaker
        6. Tests GPIO configuration and output control
        7. Tests GPIO input events
        8. For each sensor port (0-5):
            a. Turns on the LED at full brightness
            b. Waits for sensor activation
            c. Waits for sensor release
            d. Acknowledges events
            e. Turns off LED and pulses valve
    
    Configuration is set via the constants below. Modify SERIAL_PORT to match
    your system.
    """
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    SERIAL_PORT = "COM7"
    BAUD_RATE = 115200
    SERIAL_TIMEOUT = 0.1
    
    HANDSHAKE_TIMEOUT = 3.0
    EVENT_TIMEOUT = 30.0
    VALVE_PULSE_DURATION_MS = 500
    INTER_PORT_DELAY = 0.25
    
    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT) as ser:
        log_message(f"Opened {SERIAL_PORT} at {BAUD_RATE} baud")
        reset_arduino_via_dtr(ser)

        with BehaviourRigLink(ser) as link:
            # Establish connection
            link.send_hello()
            link.wait_hello(timeout=HANDSHAKE_TIMEOUT)
            log_message("Handshake successful")
            
            # Test IR illuminator
            log_message("\n=== TESTING IR ILLUMINATOR ===")
            link.ir_set(255)
            log_message("IR ON (full brightness)")
            time.sleep(0.5)
            link.ir_set(128)
            log_message("IR at 50%")
            time.sleep(0.5)
            
            # Test spotlights
            log_message("\n=== TESTING SPOTLIGHTS ===")
            for port in range(6):
                link.spotlight_set(port, 100)
                log_message(f"Spotlight {port} ON")
                time.sleep(0.2)
                link.spotlight_set(port, 0)
            
            link.spotlight_all_set(50)
            log_message("All spotlights at 50%")
            time.sleep(0.5)
            link.spotlight_all_off()
            log_message("All spotlights OFF")
            
            # Test buzzers
            log_message("\n=== TESTING BUZZERS ===")
            for port in range(6):
                link.buzzer_set(port, 1)
                log_message(f"Buzzer {port} ON")
                time.sleep(0.3)
                link.buzzer_set(port, 0)
            
            # Test overhead speaker
            log_message("\n=== TESTING OVERHEAD SPEAKER ===")
            link.speaker_go_cue(True)
            log_message("GO cue ON")
            time.sleep(0.5)
            link.speaker_off()
            
            link.speaker_nogo_cue(True)
            log_message("NOGO cue ON")
            time.sleep(0.5)
            link.speaker_off()
            
            # Test GPIO outputs
            log_message("\n=== TESTING GPIO OUTPUTS ===")
            for pin in range(4):
                link.gpio_configure(pin, GPIOMode.OUTPUT)
                log_message(f"GPIO {pin} configured as OUTPUT")
                
                link.gpio_on(pin)
                log_message(f"GPIO {pin} HIGH")
                time.sleep(0.2)
                
                link.gpio_off(pin)
                log_message(f"GPIO {pin} LOW")
            
            # Test GPIO input (configure pin 0 as input and wait for event)
            log_message("\n=== TESTING GPIO INPUT ===")
            link.gpio_configure(0, GPIOMode.INPUT)
            log_message("GPIO 0 configured as INPUT - trigger it within 5 seconds...")
            
            try:
                gpio_event = link.wait_for_gpio_event(pin=0, timeout=5.0)
                event_type = "ACTIVATED" if gpio_event.is_activation else "RELEASED"
                log_message(
                    f"GPIO EVENT: pin={gpio_event.pin}, type={event_type}, "
                    f"timestamp={gpio_event.timestamp_ms}ms"
                )
                link.acknowledge_gpio_event(gpio_event.event_id)
            except TimeoutError:
                log_message("No GPIO event received (timeout)")
            
            # Reconfigure GPIO 0 back to output for cleanup
            link.gpio_configure(0, GPIOMode.OUTPUT)
            
            # Test error handling - try to set an input pin
            log_message("\n=== TESTING GPIO ERROR HANDLING ===")
            link.gpio_configure(1, GPIOMode.INPUT)
            try:
                link.gpio_set(1, True)
                log_message("ERROR: Should have raised RuntimeError!")
            except RuntimeError as e:
                log_message(f"Correctly caught error: {e}")
            
            # Test sensor/LED/valve on each port
            for port in range(6):
                log_message(f"\n=== TESTING PORT {port} ===")
                
                # Clear any stale events before starting this trial
                drained_events = link.drain_events()
                if drained_events:
                    log_message(f"Cleared {len(drained_events)} old events before trial")
                
                link.led_set(port, 255)
                log_message(f"LED[{port}] ON - waiting for sensor activation")
                
                # Wait for an activation on the correct port
                while True:
                    event = link.wait_for_event(timeout=EVENT_TIMEOUT)
                    event_type = "ACTIVATED" if event.is_activation else "RELEASED"
                    
                    if event.port == port and event.is_activation:
                        log_message(
                            f"Received EVENT: id={event.event_id}, port={event.port}, "
                            f"type={event_type}, timestamp={event.timestamp_ms}ms"
                        )
                        break
                    else:
                        log_message(
                            f"OTHER EVENT: id={event.event_id}, port={event.port}, "
                            f"type={event_type}"
                        )
                
                # Deliver reward
                link.led_set(port, 0)
                link.valve_pulse(port, VALVE_PULSE_DURATION_MS)
                log_message(
                    f"LED[{port}] OFF - VALVE[{port}] pulsed for "
                    f"{VALVE_PULSE_DURATION_MS}ms"
                )
                
                time.sleep(INTER_PORT_DELAY)
            
            log_message("\nAll tests completed successfully")
            

        # Always attempt clean shutdown
        log_message("Shutting down rig...")
        log_message("Done")


if __name__ == "__main__":
    main()