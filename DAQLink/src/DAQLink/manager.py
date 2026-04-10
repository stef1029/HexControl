"""
DAQ Manager - Manages the lifecycle of the Arduino DAQ subprocess.

Encapsulates the subprocess launch, signal file coordination, and cleanup
that was previously inline in PeripheralManager.

Usage:
    manager = DAQManager(
        mouse_id="mouse1",
        date_time="250219_120000",
        session_folder="/path/to/session",
        rig_number=1,
        connection_timeout=30,
        log_callback=print,
    )
    
    if manager.start():
        # DAQ is running and connected
        ...
    
    manager.stop()
"""

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Resolve the path to serial_listen.py within this package
_SERIAL_LISTEN_SCRIPT = str(Path(__file__).parent / "serial_listen.py")


class DAQManager:
    """
    Manages the lifecycle of the Arduino DAQ subprocess.
    
    Handles launching the serial listener script, waiting for the Arduino
    connection signal, and graceful shutdown via signal files.
    """
    
    def __init__(
        self,
        mouse_id: str,
        date_time: str,
        session_folder: str,
        rig_number: int,
        daq_board_name: str = "",
        board_registry_path: str = "",
        connection_timeout: int = 30,
        log_callback: Optional[Callable[[str], None]] = None,
        simulate: bool = False,
    ):
        """
        Initialise the DAQ manager.
        
        Args:
            mouse_id: Mouse identifier for this session.
            date_time: Date/time string for this session.
            session_folder: Path to the session output folder.
            rig_number: Rig number (used for signal file naming).
            daq_board_name: Board registry name for the DAQ Arduino. When set,
                            the COM port is resolved via the board registry and
                            passed to the serial_listen subprocess with ``--port``.
            board_registry_path: Path to the board_registry.json file.
            connection_timeout: Seconds to wait for Arduino connection.
            log_callback: Optional callback for log messages.
            simulate: If True, skip subprocess launch and return success.
        """
        self._simulate = simulate
        self.python_path = sys.executable
        self.serial_listen_script = _SERIAL_LISTEN_SCRIPT
        self.mouse_id = mouse_id
        self.date_time = date_time
        self.session_folder = session_folder
        self.rig_number = rig_number
        self.daq_board_name = daq_board_name
        self.board_registry_path = board_registry_path
        self.connection_timeout = connection_timeout
        self._log = log_callback or print
        
        self._process: Optional[subprocess.Popen] = None
        self._log_file_handle = None  # File handle for subprocess output
        self._log_file_path: Optional[str] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._started: bool = False
        self.last_error: Optional[str] = None
    
    @property
    def is_running(self) -> bool:
        """Check if the DAQ process is alive."""
        if self._simulate:
            return self._started
        return self._process is not None and self._process.poll() is None
    
    def start(self) -> bool:
        """
        Start the DAQ subprocess.
        
        Returns:
            True if the DAQ process launched successfully.
        """
        if self._simulate:
            self._log("DAQ (simulated): skipping subprocess launch")
            self._started = True
            return True

        if not os.path.exists(self.serial_listen_script):
            self.last_error = f"Serial listen script not found: {self.serial_listen_script}"
            self._log(self.last_error)
            return False
        
        if not os.path.exists(self.python_path):
            self.last_error = f"Python executable not found: {self.python_path}"
            self._log(self.last_error)
            return False
        
        command = [
            self.python_path,
            self.serial_listen_script,
            "--id", self.mouse_id,
            "--date", self.date_time,
            "--path", self.session_folder,
            "--rig", str(self.rig_number),
        ]
        
        # Resolve DAQ board name (or raw COM port) via board registry
        if self.daq_board_name:
            try:
                # Lazy import to avoid hard dependency
                import sys as _sys
                _brs_root = Path(__file__).resolve().parents[3] / "behaviour_rig_system"
                if str(_brs_root) not in _sys.path:
                    _sys.path.insert(0, str(_brs_root))
                from core.board_registry import BoardRegistry
                if not self.board_registry_path:
                    raise ValueError("board_registry_path is required to resolve DAQ board names")
                registry = BoardRegistry(Path(self.board_registry_path))
                daq_port = registry.resolve_port(self.daq_board_name)
                command.extend(["--port", daq_port])
                self._log(f"Resolved DAQ board '{self.daq_board_name}' -> {daq_port}")
            except Exception as e:
                self.last_error = f"Failed to resolve DAQ board '{self.daq_board_name}': {e}"
                self._log(self.last_error)
                return False
        
        try:
            # The session folder may not exist yet — create it.
            os.makedirs(self.session_folder, exist_ok=True)
            self._log_file_path = os.path.join(
                self.session_folder, f"daq_rig{self.rig_number}.log"
            )
            self._log_file_handle = open(self._log_file_path, "w", encoding="utf-8")

            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self._log(f"DAQ started (PID: {self._process.pid})")
            self._log(f"DAQ log -> {self._log_file_path}")

            # Start background thread to stream subprocess output
            self._reader_thread = threading.Thread(
                target=self._read_output_loop, daemon=True
            )
            self._reader_thread.start()

            return True
        except Exception as e:
            self.last_error = f"Failed to start Arduino DAQ: {e}"
            self._log(self.last_error)
            if self._log_file_handle:
                self._log_file_handle.close()
                self._log_file_handle = None
            return False
    
    def _read_output_loop(self) -> None:
        """Read subprocess stdout line-by-line, log each line and write to file."""
        try:
            for raw_line in self._process.stdout:
                line = raw_line.decode(errors="replace").rstrip("\n\r")
                if line:
                    self._log(f"[DAQ] {line}")
                if self._log_file_handle and not self._log_file_handle.closed:
                    try:
                        self._log_file_handle.write(raw_line.decode(errors="replace"))
                        self._log_file_handle.flush()
                    except Exception as e:
                        logger.warning(f"[DAQ] log write error: {e}")
        except Exception as e:
            logger.warning(f"[DAQ] output reader error: {e}")

    def wait_for_connection(self) -> bool:
        """
        Wait for the Arduino connection signal file.
        
        The DAQ subprocess creates a signal file once it has successfully
        connected to the Arduino. This method polls for that file.
        
        Returns:
            True if the connection signal was received within the timeout.
            
        Raises:
            RuntimeError: If start() has not been called.
        """
        if self._simulate:
            if not self._started:
                raise RuntimeError("DAQ process not started — call start() first")
            self._log("DAQ (simulated): connection ready")
            return True

        if self._process is None:
            raise RuntimeError("DAQ process not started — call start() first")
        
        signal_file = os.path.join(
            self.session_folder,
            f"rig_{self.rig_number}_arduino_connected.signal"
        )
        
        self._log(f"Waiting for DAQ connection (timeout: {self.connection_timeout}s)...")
        start_time = time.time()
        
        while time.time() - start_time < self.connection_timeout:
            if os.path.exists(signal_file):
                self._log("DAQ connected")
                return True
            
            if self._process.poll() is not None:
                self.last_error = f"DAQ process terminated (exit code: {self._process.returncode})"
                self._log(self.last_error)
                # Read the log file to show what went wrong
                self._report_subprocess_log()
                return False
            
            time.sleep(0.5)
        
        self.last_error = f"Timeout waiting for Arduino connection ({self.connection_timeout}s)"
        self._log(self.last_error)
        return False
    
    def _report_subprocess_log(self) -> None:
        """Read and report the DAQ subprocess log file contents."""
        log_path = getattr(self, '_log_file_path', None)
        if not log_path or not os.path.exists(log_path):
            self._log("No DAQ log file available")
            return
        
        # Close the file handle so all output is flushed
        if self._log_file_handle:
            try:
                self._log_file_handle.close()
            except Exception as e:
                logger.warning(f"[DAQ] error closing log file: {e}")
            self._log_file_handle = None
        
        try:
            with open(log_path, 'r') as f:
                contents = f.read().strip()
            if contents:
                self._log("--- DAQ subprocess output ---")
                for line in contents.splitlines():
                    self._log(f"  {line}")
                self._log("--- end DAQ output ---")
            else:
                self._log("DAQ log file is empty (process produced no output)")
        except Exception as e:
            self._log(f"Failed to read DAQ log: {e}")

    def stop(self) -> None:
        """
        Stop the DAQ process gracefully.
        
        Creates the camera-finished signal file (which the DAQ watches
        to know it should stop), then waits for the process to exit.
        """
        if self._simulate:
            if self._started:
                self._log("DAQ (simulated): stopping")
                self._started = False
            return

        self._create_stop_signal()
        self._cleanup_process()
        self._cleanup_signal_files()
        self._close_log_file()
    
    def _create_stop_signal(self) -> None:
        """Create the signal file that tells the DAQ to stop gracefully."""
        signal_file = os.path.join(
            self.session_folder,
            f"rig_{self.rig_number}_camera_finished.signal"
        )
        try:
            os.makedirs(self.session_folder, exist_ok=True)
            with open(signal_file, 'w') as f:
                f.write(f"Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            self._log(f"Error creating DAQ stop signal: {e}")
    
    def _close_log_file(self) -> None:
        """Close the subprocess log file handle."""
        if self._log_file_handle:
            try:
                self._log_file_handle.close()
            except Exception as e:
                logger.warning(f"[DAQ] error closing log file: {e}")
            self._log_file_handle = None

    def _cleanup_process(self) -> None:
        """Wait for the DAQ process to exit, terminating if necessary."""
        if self._process is None:
            return

        try:
            self._process.wait(timeout=30)
            self._log(f"DAQ stopped (exit code: {self._process.returncode})")
        except subprocess.TimeoutExpired:
            self._log("DAQ timeout, terminating...")
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        except Exception as e:
            self._log(f"Error stopping DAQ: {e}")
        finally:
            self._process = None

        # Wait for reader thread to finish flushing output
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=5)
            self._reader_thread = None
    
    def _cleanup_signal_files(self) -> None:
        """Remove signal files from the session folder."""
        signal_files = [
            f"rig_{self.rig_number}_arduino_connected.signal",
            f"rig_{self.rig_number}_camera_finished.signal",
        ]
        
        for filename in signal_files:
            path = os.path.join(self.session_folder, filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"[DAQ] error removing signal file: {e}")
