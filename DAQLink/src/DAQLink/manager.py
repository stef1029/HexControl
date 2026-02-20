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

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

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
        connection_timeout: int = 30,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialise the DAQ manager.
        
        Args:
            mouse_id: Mouse identifier for this session.
            date_time: Date/time string for this session.
            session_folder: Path to the session output folder.
            rig_number: Rig number (used for signal file naming).
            connection_timeout: Seconds to wait for Arduino connection.
            log_callback: Optional callback for log messages.
        """
        self.python_path = sys.executable
        self.serial_listen_script = _SERIAL_LISTEN_SCRIPT
        self.mouse_id = mouse_id
        self.date_time = date_time
        self.session_folder = session_folder
        self.rig_number = rig_number
        self.connection_timeout = connection_timeout
        self._log = log_callback or print
        
        self._process: Optional[subprocess.Popen] = None
        self.last_error: Optional[str] = None
    
    @property
    def is_running(self) -> bool:
        """Check if the DAQ process is alive."""
        return self._process is not None and self._process.poll() is None
    
    def start(self) -> bool:
        """
        Start the DAQ subprocess.
        
        Returns:
            True if the DAQ process launched successfully.
        """
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
        
        try:
            # CREATE_NEW_CONSOLE is Windows-only; use default on other platforms
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            
            self._process = subprocess.Popen(command, **kwargs)
            self._log(f"DAQ started (PID: {self._process.pid})")
            return True
        except Exception as e:
            self.last_error = f"Failed to start Arduino DAQ: {e}"
            self._log(self.last_error)
            return False
    
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
                return False
            
            time.sleep(0.5)
        
        self.last_error = f"Timeout waiting for Arduino connection ({self.connection_timeout}s)"
        self._log(self.last_error)
        return False
    
    def stop(self) -> None:
        """
        Stop the DAQ process gracefully.
        
        Creates the camera-finished signal file (which the DAQ watches
        to know it should stop), then waits for the process to exit.
        """
        self._create_stop_signal()
        self._cleanup_process()
        self._cleanup_signal_files()
    
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
    
    def _cleanup_process(self) -> None:
        """Wait for the DAQ process to exit, terminating if necessary."""
        if self._process is None:
            return
        
        try:
            self._process.wait(timeout=10)
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
                except Exception:
                    pass
