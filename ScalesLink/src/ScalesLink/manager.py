"""
Scales Manager - Manages the lifecycle of the ScalesLink server subprocess.

Encapsulates the subprocess launch, client connection, and cleanup
that was previously inline in PeripheralManager.

Usage:
    manager = ScalesManager(
        com_port="COM10",
        baud_rate=9600,
        tcp_port=5101,
        is_wired=True,
        calibration_scale=0.22375,
        calibration_intercept=-5617.39,
        session_folder="/path/to/session",
        date_time="250219_120000",
        mouse_id="mouse1",
        log_callback=print,
    )
    
    if manager.start():
        # Use the client to get weights
        weight = manager.client.get_weight()
    
    manager.stop()
"""

import os
import subprocess
import sys
import time
from typing import Callable, Optional, TYPE_CHECKING

from .client import ScalesClient

if TYPE_CHECKING:
    from BehavLink.simulation import VirtualRigState


class ScalesManager:
    """
    Manages the lifecycle of the ScalesLink server subprocess and its client.
    
    Handles launching the TCP server subprocess, connecting the client,
    and graceful shutdown.
    """
    
    def __init__(
        self,
        com_port: str,
        baud_rate: int,
        tcp_port: int,
        is_wired: bool = False,
        calibration_scale: float = 1.0,
        calibration_intercept: float = 0.0,
        session_folder: str = "",
        date_time: str = "",
        mouse_id: str = "",
        log_callback: Optional[Callable[[str], None]] = None,
        simulate: bool = False,
        virtual_rig_state: Optional["VirtualRigState"] = None,
    ):
        """
        Initialise the scales manager.
        
        Args:
            com_port: Serial port for the scales hardware.
            baud_rate: Serial baud rate.
            tcp_port: TCP port for the server to listen on.
            is_wired: Whether the scales use wired (vs wireless) protocol.
            calibration_scale: Linear calibration scale factor.
            calibration_intercept: Linear calibration intercept.
            session_folder: Path to the session output folder (for log file).
            date_time: Date/time string for this session (for log filename).
            mouse_id: Mouse identifier for this session (for log filename).
            log_callback: Optional callback for log messages.
            simulate: If True, skip subprocess launch and create a mock client.
            virtual_rig_state: When simulate=True and this is provided,
                               the mock client reads weight from the shared
                               VirtualRigState (driven by the GUI slider).
        """
        self._simulate = simulate
        self._virtual_rig_state = virtual_rig_state
        
        if not simulate:
            if not com_port:
                raise ValueError("com_port must be provided for scales")
            if not tcp_port:
                raise ValueError("tcp_port must be provided for scales")
        
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.tcp_port = tcp_port
        self.is_wired = is_wired
        self.calibration_scale = calibration_scale
        self.calibration_intercept = calibration_intercept
        self.session_folder = session_folder
        self.date_time = date_time
        self.mouse_id = mouse_id
        self._log = log_callback or print
        
        self._process: Optional[subprocess.Popen] = None
        self._log_file_handle = None
        self._log_file_path: Optional[str] = None
        self._started: bool = False
        self.client: Optional[ScalesClient] = None
        self.last_error: Optional[str] = None
    
    @property
    def is_running(self) -> bool:
        """Check if the scales server process is alive."""
        if self._simulate:
            return self._started
        return self._process is not None and self._process.poll() is None
    
    def start(self) -> bool:
        """
        Start the scales server subprocess and connect the client.
        
        Returns:
            True if the server started and the client connected successfully.
        """
        if self._simulate:
            return self._start_simulated()

        self._log(f"Starting scales on {self.com_port} (TCP port {self.tcp_port})...")
        
        # Build log path in session folder
        log_path = ""
        if self.session_folder and self.date_time and self.mouse_id:
            log_filename = f"{self.date_time}_{self.mouse_id}_scales_data.csv"
            log_path = os.path.join(self.session_folder, log_filename)
        
        # Build command to run scales server
        command = [
            sys.executable,  # Use same Python interpreter
            "-m", "ScalesLink.server",
            "--port", self.com_port,
            "--baud", str(self.baud_rate),
            "--tcp", str(self.tcp_port),
            "--scale", str(self.calibration_scale),
            "--intercept", str(self.calibration_intercept),
        ]
        
        if log_path:
            command.extend(["--log", log_path])
        
        if self.is_wired:
            command.append("--wired")
        
        try:
            # Redirect stdout/stderr to a log file so we can diagnose failures.
            os.makedirs(self.session_folder, exist_ok=True)
            self._log_file_path = os.path.join(
                self.session_folder, f"scales_server.log"
            )
            self._log_file_handle = open(self._log_file_path, "w")
            
            self._process = subprocess.Popen(
                command,
                stdout=self._log_file_handle,
                stderr=subprocess.STDOUT,
            )
            self._log(f"Scales server started (PID: {self._process.pid})")
            self._log(f"Scales output -> {self._log_file_path}")
        except Exception as e:
            self.last_error = f"Failed to start scales server: {e}"
            self._log(self.last_error)
            if self._log_file_handle:
                self._log_file_handle.close()
                self._log_file_handle = None
            return False
        
        # Wait for server to start up
        time.sleep(3)
        
        # Check if process is still running
        if self._process.poll() is not None:
            error_output = self._read_server_log()
            self.last_error = f"Scales server terminated (exit code: {self._process.returncode})"
            self._log(f"ERROR: {self.last_error}")
            if error_output:
                self._log(f"Scales server output:\n{error_output}")
            else:
                self._log("No output captured from scales server")
            self._close_log_file()
            self._process = None
            return False
        
        # Create client and verify connection
        return self._connect_client()
    
    def _connect_client(self) -> bool:
        """Create the TCP client and verify the server is responsive."""
        try:
            self.client = ScalesClient(tcp_port=self.tcp_port)
            
            # Retry ping a few times while server starts up
            for attempt in range(5):
                if self.client.ping(timeout=2.0):
                    self._log("Scales server connected")
                    
                    # Get initial weight
                    weight = self.client.get_weight()
                    if weight is not None:
                        self._log(f"Initial weight: {weight:.2f}g")
                    else:
                        self._log("Scales ready (no initial reading)")
                    
                    return True
                
                time.sleep(1)
            
            self.last_error = "Failed to connect to scales server (timeout)"
            self._log(self.last_error)
            self._cleanup_process()
            return False
            
        except Exception as e:
            self.last_error = f"Failed to connect scales client: {e}"
            self._log(self.last_error)
            self._cleanup_process()
            return False
    
    def stop(self) -> None:
        """Stop the scales server gracefully."""
        if self._simulate:
            if self._started:
                self._log("Scales (simulated): stopping")
                if self.client is not None:
                    self.client = None
                self._started = False
            return

        # Send shutdown via client
        if self.client is not None:
            try:
                self._log("Sending shutdown to scales server...")
                self.client.shutdown()
            except Exception as e:
                self._log(f"Error sending shutdown to scales: {e}")
            finally:
                self.client = None
        
        self._cleanup_process()
    
    def _read_server_log(self, max_lines: int = 50) -> str:
        """Read the last N lines from the scales server log file."""
        if not self._log_file_path:
            return ""
        try:
            # Flush before reading so any buffered output is written
            if self._log_file_handle and not self._log_file_handle.closed:
                self._log_file_handle.flush()
            with open(self._log_file_path, "r") as f:
                lines = f.readlines()
            # Return the last max_lines, stripped of excess whitespace
            tail = lines[-max_lines:] if len(lines) > max_lines else lines
            return "".join(tail).strip()
        except (OSError, IOError):
            return ""
    
    def _close_log_file(self) -> None:
        """Close the log file handle if open."""
        if self._log_file_handle is not None:
            try:
                self._log_file_handle.close()
            except Exception:
                pass
            self._log_file_handle = None
    
    def _cleanup_process(self) -> None:
        """Clean up the scales server process if still running."""
        if self._process is None:
            return
        
        try:
            self._process.wait(timeout=5)
            exit_code = self._process.returncode
            self._log(f"Scales server stopped (exit code: {exit_code})")
            if exit_code not in (0, None):
                error_output = self._read_server_log()
                if error_output:
                    self._log(f"Scales server output:\n{error_output}")
        except subprocess.TimeoutExpired:
            self._log("Scales server timeout, terminating...")
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
        except Exception as e:
            self._log(f"Error stopping scales server: {e}")
        finally:
            self._close_log_file()
            self._process = None
            self.client = None

    # ── Simulated mode ──────────────────────────────────────────────────

    def _start_simulated(self) -> bool:
        """Start in simulated mode — no subprocess, mock or virtual client."""
        if self._virtual_rig_state is not None:
            self._log("Scales (simulated): starting virtual scales (weight from GUI)")
            self.client = _VirtualScalesClient(self._virtual_rig_state)
        else:
            self._log("Scales (simulated): starting mock scales (weight = 0.0g)")
            self.client = _MockScalesClient()
        self._started = True
        return True


class _MockScalesClient:
    """Internal mock client — returns 0.0 for all weight readings."""

    def get_weight(self, timeout: float = 5.0) -> Optional[float]:
        return 0.0

    def ping(self, timeout: float = 5.0) -> bool:
        return True

    def connect(self, timeout: float = 10.0) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def shutdown(self) -> bool:
        return True


class _VirtualScalesClient:
    """Internal simulated client — reads weight from VirtualRigState."""

    def __init__(self, state: "VirtualRigState") -> None:
        self._state = state

    def get_weight(self, timeout: float = 5.0) -> Optional[float]:
        return self._state.get_weight()

    def ping(self, timeout: float = 5.0) -> bool:
        return True

    def connect(self, timeout: float = 10.0) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def shutdown(self) -> bool:
        return True
