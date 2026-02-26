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
        
        Supports both new board-registry style (board_name resolved to port)
        and legacy style (com_port directly).
        
        Expected keys (new style):
            - board_name: Human-readable key resolved via board registry
            - is_wired: (optional) Whether scales are wired type
            - calibration_scale: (optional) Scale factor for calibration
            - calibration_intercept: (optional) Intercept for calibration
            
        Expected keys (legacy style):
            - com_port: Serial port name
            - baud_rate: Serial baud rate
            - is_wired: (optional) Whether scales are wired type
            - calibration_scale: (optional) Scale factor for calibration
            - calibration_intercept: (optional) Intercept for calibration
        """
        board_name = config_dict.get("board_name", "")
        port = ""
        baud_rate = config_dict.get("baud_rate", 115200)
        
        if board_name:
            # Resolve COM port via board registry
            try:
                import sys
                from pathlib import Path
                _brs_root = Path(__file__).resolve().parents[3] / "behaviour_rig_system"
                if str(_brs_root) not in sys.path:
                    sys.path.insert(0, str(_brs_root))
                from core.board_registry import BoardRegistry
                registry = BoardRegistry()
                port = registry.find_board_port(board_name)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to resolve scales board '{board_name}': {e}"
                ) from e
        else:
            # Legacy: use com_port directly
            port = config_dict["com_port"]
        
        return cls(
            port=port,
            baud_rate=baud_rate,
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

        # In-memory storage for all readings (for end-of-session save)
        self._store_readings = False
        self._readings_buffer: list[tuple[float, float, Optional[int]]] = []
        self._readings_lock = threading.Lock()

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

    def get_message_id(self) -> Optional[int]:
        """
        Returns the most recent message ID (for wired scales).

        Returns:
            The message ID, or None if not available (wireless scales).
        """
        with self._weight_lock:
            return self._message_id

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
    # In-Memory Storage (for end-of-session save)
    # -------------------------------------------------------------------------

    def enable_reading_storage(self) -> None:
        """
        Enable storing all readings in memory.
        
        When enabled, every reading received will be stored in an internal
        buffer. Use get_all_readings() to retrieve them, and save_readings_to_csv()
        to write them to a file at the end of the session.
        """
        with self._readings_lock:
            self._store_readings = True
            self._readings_buffer.clear()
            self._log_start_time = time.time()

    def disable_reading_storage(self) -> None:
        """Disable storing readings in memory."""
        with self._readings_lock:
            self._store_readings = False

    def get_all_readings(self) -> list[tuple[float, float, Optional[int]]]:
        """
        Get all stored readings.
        
        Returns:
            List of (timestamp_s, weight_g, message_id) tuples.
        """
        with self._readings_lock:
            return list(self._readings_buffer)

    def get_reading_count(self) -> int:
        """Get the number of readings stored in memory."""
        with self._readings_lock:
            return len(self._readings_buffer)

    def save_readings_to_csv(self, path: Path) -> int:
        """
        Save all stored readings to a CSV file.
        
        Args:
            path: Path to the output CSV file.
            
        Returns:
            Number of readings saved.
        """
        with self._readings_lock:
            readings = list(self._readings_buffer)
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp_s', 'weight_g', 'message_id'])
            for timestamp, weight, msg_id in readings:
                writer.writerow([f"{timestamp:.6f}", f"{weight:.4f}", msg_id])
        
        return len(readings)

    def clear_readings_buffer(self) -> None:
        """Clear all stored readings from memory."""
        with self._readings_lock:
            self._readings_buffer.clear()

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

        # Store reading in memory buffer if enabled
        if self._store_readings:
            with self._readings_lock:
                if self._log_start_time is not None:
                    relative_time = timestamp - self._log_start_time
                    self._readings_buffer.append((relative_time, weight_g, message_id))

        # Log to file (immediate logging, if configured)
        if self._csv_writer is not None:
            with self._log_lock:
                relative_time = timestamp - self._log_start_time
                self._csv_writer.writerow([f"{relative_time:.4f}", f"{weight_g:.4f}", message_id])
                self._log_file.flush()
