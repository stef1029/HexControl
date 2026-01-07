"""
Scales Communication Library
============================

This module provides a clean interface for reading weight data from scales
connected to behavioural experiment rigs. It supports both wired (rigs 3, 4)
and wireless (rigs 1, 2) scale configurations.

Features:
    - Background thread continuously reads and logs all scale data
    - Simple get_weight() method returns the most recent weight
    - Automatic calibration application
    - CSV logging with timestamps
"""

import csv
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import serial


# =============================================================================
# Configuration Data Classes
# =============================================================================

@dataclass(frozen=True)
class ScalesConfig:
    """
    Configuration for a specific scales unit.

    Attributes:
        port: Serial port name (e.g., "COM7" or "/dev/ttyUSB0").
        baud_rate: Serial baud rate.
        scale: Calibration scale factor (gradient).
        intercept: Calibration intercept (zero offset).
        is_wired: True for wired scales, False for wireless.
    """
    port: str
    baud_rate: int
    scale: float = 1.0
    intercept: float = 0.0
    is_wired: bool = False

    @classmethod
    def from_yaml_dict(cls, config_dict: dict) -> "ScalesConfig":
        """
        Create a ScalesConfig from a YAML configuration dictionary.
        
        Expected keys:
            - com_port: Serial port name
            - baud_rate: Serial baud rate
            - is_wired: (optional) Whether scales are wired type
            - calibration_scale: (optional) Scale factor for calibration
            - calibration_intercept: (optional) Intercept for calibration
        """
        return cls(
            port=config_dict["com_port"],
            baud_rate=config_dict["baud_rate"],
            scale=config_dict.get("calibration_scale", 1.0),
            intercept=config_dict.get("calibration_intercept", 0.0),
            is_wired=config_dict.get("is_wired", False),
        )


# =============================================================================
# Scales Class
# =============================================================================

class Scales:
    """
    Interface for reading calibrated weight data from scales.

    This class runs a background thread that continuously reads from the scales
    and optionally logs all readings to a CSV file. The most recent weight can
    be retrieved at any time via get_weight().

    Args:
        rig: Rig number (1-4) to use predefined configuration.
        config: Custom ScalesConfig (overrides rig parameter if provided).
        log_path: Path to CSV file for logging. If None, no logging is performed.

    Example:
        with Scales(rig=3, log_path="scales_log.csv") as scales:
            weight = scales.get_weight()
            print(f"Current weight: {weight:.2f} g")
    """

    def __init__(
        self,
        config: ScalesConfig,
        log_path: Optional[str | Path] = None,
    ):
        """
        Initialises the scales interface.

        Args:
            config: ScalesConfig with port, baud_rate, and calibration settings.
            log_path: Optional path for CSV logging of all readings.
        """
        self._config = config

        self._log_path = Path(log_path) if log_path is not None else None

        # Serial connection
        self._serial: Optional[serial.Serial] = None

        # Thread control
        self._stop_flag = threading.Event()
        self._read_thread: Optional[threading.Thread] = None

        # Current weight storage (thread-safe via lock)
        self._weight_lock = threading.Lock()
        self._current_weight: Optional[float] = None
        self._last_update_time: Optional[float] = None
        self._message_id: Optional[int] = None

        # Buffer for wired scales parsing
        self._data_buffer = bytearray()

        # Logging
        self._log_file = None
        self._csv_writer = None
        self._log_lock = threading.Lock()
        self._log_start_time: Optional[float] = None

    # -------------------------------------------------------------------------
    # Context Manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> "Scales":
        """Enables use as a context manager."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensures clean shutdown when exiting context."""
        self.stop()

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """
        Opens the serial connection and starts the background read thread.

        For wired scales (rigs 3, 4), sends the start acquisition command.
        """
        # Open serial connection
        self._serial = serial.Serial(
            self._config.port,
            self._config.baud_rate,
            timeout=0.1,
        )
        time.sleep(2)  # Allow connection to stabilise

        # For wired scales, send start commands
        if self._config.is_wired:
            self._serial.write(b'e')  # Reset
            self._serial.write(b's')  # Start acquisition

        # Open log file if configured
        if self._log_path is not None:
            self._log_file = open(self._log_path, 'w', newline='')
            self._csv_writer = csv.writer(self._log_file)
            self._csv_writer.writerow(['timestamp_s', 'weight_g', 'message_id'])
            self._log_start_time = time.time()

        # Start background thread
        self._stop_flag.clear()
        self._read_thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name="ScalesReader",
        )
        self._read_thread.start()

    def stop(self) -> None:
        """
        Stops the background thread and closes the serial connection.

        For wired scales, sends the stop acquisition command.
        """
        self._stop_flag.set()

        if self._read_thread is not None:
            self._read_thread.join(timeout=2.0)
            self._read_thread = None

        if self._serial is not None:
            if self._config.is_wired:
                try:
                    self._serial.write(b'e')  # Stop acquisition
                except Exception:
                    pass
            self._serial.close()
            self._serial = None

        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
            self._csv_writer = None

    # -------------------------------------------------------------------------
    # Public Interface
    # -------------------------------------------------------------------------

    def get_weight(self) -> Optional[float]:
        """
        Returns the most recent weight reading in grams.

        Returns:
            The calibrated weight in grams, or None if no reading is available.
        """
        with self._weight_lock:
            return self._current_weight

    def get_weight_with_age(self) -> tuple[Optional[float], Optional[float]]:
        """
        Returns the most recent weight and how old the reading is.

        Returns:
            A tuple of (weight_g, age_seconds). Both are None if no reading
            is available. Age is the time since the reading was received.
        """
        with self._weight_lock:
            if self._current_weight is None or self._last_update_time is None:
                return None, None
            age = time.monotonic() - self._last_update_time
            return self._current_weight, age

    def clear(self) -> None:
        """
        Clears the current weight reading.

        Useful for resetting state before waiting for a new reading.
        """
        with self._weight_lock:
            self._current_weight = None
            self._last_update_time = None

    def tare(self) -> None:
        """
        Sends the tare command to zero the scales.

        Only supported for wired scales (rigs 3, 4). Blocks for 3 seconds
        while the scales perform the tare operation.
        """
        if not self._config.is_wired:
            raise RuntimeError("Tare command only supported for wired scales")

        if self._serial is None:
            raise RuntimeError("Scales not started")

        self._serial.write(b't')
        time.sleep(3)

    # -------------------------------------------------------------------------
    # Background Reading
    # -------------------------------------------------------------------------

    def _read_loop(self) -> None:
        """
        Background thread that continuously reads from the scales.

        Parses incoming data, applies calibration, updates the current weight,
        and logs all readings to file if configured.
        """
        while not self._stop_flag.is_set():
            try:
                if self._config.is_wired:
                    self._read_wired()
                else:
                    self._read_wireless()
            except Exception:
                # Silently continue on read errors
                pass

    def _read_wired(self) -> None:
        """
        Reads and parses data from wired scales (rigs 3, 4).

        The wired protocol uses 8-byte messages with interleaved ID and value
        bytes, terminated by 0x02 0x03.
        """
        if self._serial.in_waiting == 0:
            time.sleep(0.01)
            return

        # Read all available data
        data = self._serial.read(self._serial.in_waiting)
        self._data_buffer.extend(data)

        # Prevent buffer overflow
        if len(self._data_buffer) > 20000:
            self._data_buffer = self._data_buffer[-10000:]

        # Process complete messages (delimited by 0x02 0x03)
        end_delimiter = b'\x02\x03'
        delimiter_index = self._data_buffer.find(end_delimiter)

        while delimiter_index != -1:
            message_data = self._data_buffer[:delimiter_index]
            self._data_buffer = self._data_buffer[delimiter_index + len(end_delimiter):]

            if len(message_data) == 8:
                # Deinterleave bytes
                id_bytes = message_data[::2]    # Even indices
                value_bytes = message_data[1::2]  # Odd indices

                message_id = int.from_bytes(id_bytes, byteorder='big', signed=False)
                raw_value = struct.unpack('>f', value_bytes)[0]

                # Apply calibration
                weight_g = ((raw_value - self._config.intercept) * self._config.scale) / 1000

                self._update_weight(weight_g, raw_value, message_id)

            delimiter_index = self._data_buffer.find(end_delimiter)

    def _read_wireless(self) -> None:
        """
        Reads and parses data from wireless scales (rigs 1, 2).

        The wireless protocol sends ASCII float values, one per line.
        """
        if self._serial.in_waiting == 0:
            time.sleep(0.01)
            return

        try:
            line = self._serial.readline().decode('utf-8').strip()
            if line:
                raw_value = float(line)
                weight_g = ((raw_value - self._config.intercept) * self._config.scale) / 1000
                self._update_weight(weight_g, raw_value, None)
        except (ValueError, UnicodeDecodeError):
            pass

    def _update_weight(
        self,
        weight_g: float,
        raw_value: float,
        message_id: Optional[int],
    ) -> None:
        """
        Updates the current weight and logs the reading.

        Args:
            weight_g: Calibrated weight in grams.
            raw_value: Raw sensor value before calibration.
            message_id: Message ID (for wired scales) or None.
        """
        timestamp = time.time()

        with self._weight_lock:
            self._current_weight = weight_g
            self._last_update_time = time.monotonic()
            self._message_id = message_id

        # Log to file
        if self._csv_writer is not None:
            with self._log_lock:
                relative_time = timestamp - self._log_start_time
                self._csv_writer.writerow([f"{relative_time:.4f}", f"{weight_g:.4f}", message_id])
                self._log_file.flush()


# =============================================================================
# Calibration Utility
# =============================================================================

def run_calibration(rig: int) -> None:
    """
    Interactive calibration routine for scales.

    Guides the user through measuring empty and 100g reference weights,
    then outputs the calibration values to copy into the configuration.

    Args:
        rig: Rig number (1-4) to calibrate.
    """
    config = RIG_CONFIGS[rig]

    print(f"Calibrating scales on {config.port}")
    print()

    ser = serial.Serial(config.port, config.baud_rate, timeout=0.1)
    time.sleep(2)

    if config.is_wired:
        ser.write(b'e')
        ser.write(b't')  # Tare
        time.sleep(3)
        ser.write(b's')

    # Helper to read raw values
    data_buffer = bytearray()

    def read_raw() -> Optional[float]:
        nonlocal data_buffer

        if config.is_wired:
            if ser.in_waiting > 0:
                data_buffer.extend(ser.read(ser.in_waiting))
                delimiter = b'\x02\x03'
                idx = data_buffer.find(delimiter)
                if idx != -1:
                    msg = data_buffer[:idx]
                    data_buffer = data_buffer[idx + 2:]
                    if len(msg) == 8:
                        value_bytes = msg[1::2]
                        return struct.unpack('>f', value_bytes)[0]
            return None
        else:
            try:
                line = ser.readline().decode('utf-8').strip()
                return float(line) if line else None
            except (ValueError, UnicodeDecodeError):
                return None

    def average_readings(n: int = 50) -> float:
        ser.read_all()
        data_buffer.clear()
        total = 0.0
        count = 0
        while count < n:
            val = read_raw()
            if val is not None:
                total += val
                count += 1
        return total / n

    # Empty measurement
    input("Empty the scale, press Enter to continue...")
    print("Reading...")
    empty = average_readings()
    print(f"Empty reading: {empty}")

    # 100g measurement
    input("Place 100g on the scale, press Enter to continue...")
    print("Reading...")
    hundred = average_readings()
    print(f"100g reading: {hundred}")

    # Calculate calibration
    gradient = 100000 / (hundred - empty)  # 100g = 100000 mg

    print()
    print("=" * 50)
    print("Calibration values:")
    print(f"  scale = {gradient}")
    print(f"  intercept = {empty}")
    print("=" * 50)

    if config.is_wired:
        ser.write(b'e')
    ser.close()


# =============================================================================
# Standalone Test
# =============================================================================

if __name__ == "__main__":

    rig_num = 4

    calibrate = False

    if calibrate:
        run_calibration(rig_num)
    else:
        # Simple test - print weight continuously
        print(f"Testing scales on rig {rig_num}")
        print("Press Ctrl+C to exit")
        print()

        with Scales(rig=rig_num) as scales:
            try:
                while True:
                    weight = scales.get_weight()
                    if weight is not None:
                        print(f"\rWeight: {weight:8.2f} g", end="", flush=True)
                    time.sleep(0.05)
            except KeyboardInterrupt:
                print("\nExiting...")
