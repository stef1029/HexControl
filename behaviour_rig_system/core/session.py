"""
Session Manager

Handles the startup and shutdown sequence for behaviour sessions:
    1. Start Arduino DAQ process
    2. Wait for connection signal
    3. Start camera process
    4. Run protocol
    5. Shutdown processes in correct order
"""

import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import yaml


@dataclass
class SessionConfig:
    """Configuration for a behaviour session."""
    # Rig info
    rig_name: str
    rig_number: int
    serial_port: str
    camera_serial: str
    
    # Session info
    mouse_id: str
    session_folder: str
    date_time: str
    
    # Process paths
    python_path: str
    serial_listen_script: str
    camera_executable: str
    
    # Settings
    baud_rate: int = 115200
    connection_timeout: int = 30
    camera_fps: int = 30
    camera_window_width: int = 640
    camera_window_height: int = 512


def load_session_config(rig_config: dict, mouse_id: str = "test", save_directory: str = "") -> SessionConfig:
    """
    Load session configuration from rig config and global settings.
    
    Args:
        rig_config: Dict with rig-specific settings (including config_path)
        mouse_id: Mouse identifier for this session
        save_directory: Full path to the save directory (e.g., D:\\behaviour_data\\cohort_name)
        
    Returns:
        SessionConfig with all settings populated
    """
    # Load full config file using path from rig_config
    config_path = rig_config.get("config_path")
    if not config_path:
        config_path = Path(__file__).parent.parent / "config" / "rigs.yaml"
    
    with open(config_path) as f:
        full_config = yaml.safe_load(f)
    
    global_settings = full_config.get("global", {})
    process_settings = full_config.get("processes", {})
    
    # Extract rig number from name (e.g., "Rig 1" -> 1)
    rig_name = rig_config.get("name", "Rig 1")
    try:
        rig_number = int(rig_name.split()[-1])
    except (ValueError, IndexError):
        rig_number = 1
    
    # Create session folder path: save_directory / datetime_mouseID
    date_time = datetime.now().strftime("%y%m%d_%H%M%S")
    session_folder = os.path.join(save_directory, f"{date_time}_{mouse_id}")
    
    return SessionConfig(
        rig_name=rig_name,
        rig_number=rig_number,
        serial_port=rig_config.get("serial_port", "COM7"),
        camera_serial=rig_config.get("camera_serial", ""),
        mouse_id=mouse_id,
        session_folder=session_folder,
        date_time=date_time,
        python_path=process_settings.get("python_path", "python"),
        serial_listen_script=process_settings.get("serial_listen_script", ""),
        camera_executable=process_settings.get("camera_executable", ""),
        baud_rate=global_settings.get("baud_rate", 115200),
        connection_timeout=process_settings.get("connection_timeout", 30),
        camera_fps=process_settings.get("camera_fps", 30),
        camera_window_width=process_settings.get("camera_window_width", 640),
        camera_window_height=process_settings.get("camera_window_height", 512),
    )


class SessionManager:
    """
    Manages the startup and shutdown of behaviour session processes.
    
    Handles:
        - Starting the Arduino DAQ subprocess
        - Waiting for connection confirmation
        - Starting the camera subprocess
        - Proper shutdown sequence
    """
    
    def __init__(
        self,
        config: SessionConfig,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the session manager.
        
        Args:
            config: Session configuration
            log_callback: Function to call for logging messages
        """
        self.config = config
        self._log = log_callback or print
        
        # Process handles
        self.daq_process: Optional[subprocess.Popen] = None
        self.camera_process: Optional[subprocess.Popen] = None
        
        # State
        self.is_started = False
        self.session_folder_created = False
        self.last_error: Optional[str] = None
    
    def start_session(self) -> bool:
        """
        Start the session processes (DAQ and camera).
        
        Returns:
            True if all processes started successfully, False otherwise
        """
        self._log("="*50)
        self._log("SESSION STARTUP SEQUENCE")
        self._log("="*50)
        self._log(f"Rig: {self.config.rig_name} (#{self.config.rig_number})")
        self._log(f"Mouse ID: {self.config.mouse_id}")
        self._log(f"Session folder: {self.config.session_folder}")
        self._log("-"*50)
        
        try:
            # Create session folder
            self._log("[Step 1/3] Creating session folder...")
            os.makedirs(self.config.session_folder, exist_ok=True)
            self.session_folder_created = True
            self._log("[Step 1/3] Session folder created ✓")
            
            # Start Arduino DAQ
            self._log("-"*50)
            self._log("[Step 2/3] Starting Arduino DAQ...")
            if not self._start_daq():
                self._log("[Step 2/3] FAILED - DAQ startup failed")
                return False
            self._log("[Step 2/3] DAQ started ✓")
            
            # Wait for connection signal
            self._log("-"*50)
            self._log("[Step 2b/3] Waiting for DAQ connection...")
            if not self._wait_for_connection():
                self._log("[Step 2b/3] FAILED - Connection failed")
                self._cleanup_daq()
                return False
            self._log("[Step 2b/3] DAQ connected ✓")
            
            # Start camera
            self._log("-"*50)
            self._log("[Step 3/3] Starting camera...")
            if not self._start_camera():
                self._log("[Step 3/3] FAILED - Camera startup failed")
                self._cleanup_daq()
                return False
            self._log("[Step 3/3] Camera started ✓")
            
            self.is_started = True
            self._log("="*50)
            self._log("SESSION STARTUP COMPLETE")
            self._log("="*50)
            return True
            
        except Exception as e:
            import traceback
            self._log(f"[ERROR] Exception during startup: {e}")
            self._log(f"[ERROR] Traceback: {traceback.format_exc()}")
            self.stop_session()
            return False
    
    def _start_daq(self) -> bool:
        """Start the Arduino DAQ process."""
        self._log("[DAQ] Checking configuration...")
        
        if not self.config.serial_listen_script:
            self._log("[DAQ] Warning: No serial listen script configured, skipping DAQ")
            return True
        
        self._log(f"[DAQ] Script path: {self.config.serial_listen_script}")
        if not os.path.exists(self.config.serial_listen_script):
            error_msg = f"Serial listen script not found: {self.config.serial_listen_script}"
            self._log(f"[DAQ] Error: {error_msg}")
            self.last_error = error_msg
            return False
        self._log("[DAQ] Script exists ✓")
        
        self._log(f"[DAQ] Python path: {self.config.python_path}")
        if not os.path.exists(self.config.python_path):
            error_msg = f"Python executable not found: {self.config.python_path}"
            self._log(f"[DAQ] Error: {error_msg}")
            self.last_error = error_msg
            return False
        self._log("[DAQ] Python exists ✓")
        
        self._log("[DAQ] Building command...")
        
        command = [
            self.config.python_path,
            self.config.serial_listen_script,
            "--id", self.config.mouse_id,
            "--date", self.config.date_time,
            "--path", self.config.session_folder,
            "--rig", str(self.config.rig_number),
        ]
        
        self._log(f"[DAQ] Command: {' '.join(command)}")
        self._log("[DAQ] Launching subprocess...")
        
        try:
            # Note: Don't use stdout/stderr PIPE with CREATE_NEW_CONSOLE
            # The new console handles the output - piping can cause hangs
            self.daq_process = subprocess.Popen(
                command,
                creationflags=subprocess.CREATE_NEW_CONSOLE,  # Windows: new console window
            )
            self._log(f"[DAQ] Process started (PID: {self.daq_process.pid}) ✓")
            return True
        except Exception as e:
            error_msg = f"Failed to start Arduino DAQ: {e}"
            self._log(f"[DAQ] Error: {error_msg}")
            self.last_error = error_msg
            return False
    
    def _wait_for_connection(self) -> bool:
        """Wait for the Arduino connection signal file."""
        self._log("[Connection] Starting connection wait...")
        
        if self.daq_process is None:
            self._log("[Connection] No DAQ process, skipping wait")
            return True  # DAQ not configured, skip
        
        signal_file = os.path.join(
            self.config.session_folder,
            f"rig_{self.config.rig_number}_arduino_connected.signal"
        )
        
        self._log(f"[Connection] Waiting for signal file...")
        self._log(f"[Connection] Path: {signal_file}")
        self._log(f"[Connection] Timeout: {self.config.connection_timeout}s")
        
        start_time = time.time()
        last_status_time = start_time
        
        while time.time() - start_time < self.config.connection_timeout:
            elapsed = time.time() - start_time
            
            # Log progress every 3 seconds
            if time.time() - last_status_time >= 3.0:
                self._log(f"[Connection] Still waiting... ({elapsed:.0f}s / {self.config.connection_timeout}s)")
                # Check if DAQ process is still alive
                poll_result = self.daq_process.poll()
                if poll_result is None:
                    self._log(f"[Connection] DAQ process still running (PID: {self.daq_process.pid})")
                last_status_time = time.time()
            
            # Check if signal file exists
            if os.path.exists(signal_file):
                self._log(f"[Connection] Signal file found! ({elapsed:.1f}s) ✓")
                return True
            
            # Check if DAQ process died
            if self.daq_process.poll() is not None:
                self._log(f"[Connection] DAQ process has terminated!")
                # Note: Can't get stdout/stderr since we're using CREATE_NEW_CONSOLE
                # Check the DAQ console window for error messages
                
                error_msg = f"DAQ process terminated unexpectedly (exit code: {self.daq_process.returncode}). Check the DAQ console window for details."
                
                self._log(f"[Connection] Error: {error_msg}")
                self.last_error = error_msg
                return False
            
            time.sleep(0.5)
        
        # Timeout reached - gather diagnostic info
        self._log(f"[Connection] TIMEOUT after {self.config.connection_timeout}s")
        self._log(f"[Connection] Checking folder contents...")
        
        try:
            if os.path.exists(self.config.session_folder):
                contents = os.listdir(self.config.session_folder)
                self._log(f"[Connection] Folder contains: {contents}")
            else:
                self._log(f"[Connection] Session folder does not exist!")
        except Exception as e:
            self._log(f"[Connection] Could not list folder: {e}")
        
        error_msg = f"Timeout waiting for Arduino connection ({self.config.connection_timeout}s)\n\nExpected signal file: {signal_file}"
        self._log(f"[Connection] {error_msg}")
        self.last_error = error_msg
        return False
    
    def _start_camera(self) -> bool:
        """Start the camera process."""
        if not self.config.camera_executable:
            self._log("Warning: No camera executable configured, skipping camera")
            return True
        
        if not os.path.exists(self.config.camera_executable):
            error_msg = f"Camera executable not found: {self.config.camera_executable}"
            self._log(f"Error: {error_msg}")
            self.last_error = error_msg
            return False
        
        if not self.config.camera_serial:
            self._log("Warning: No camera serial number configured, skipping camera")
            return True
        
        self._log("Starting camera process...")
        
        command = [
            self.config.camera_executable,
            "--id", self.config.mouse_id,
            "--date", self.config.date_time,
            "--path", self.config.session_folder,
            "--serial_number", self.config.camera_serial,
            "--fps", str(self.config.camera_fps),
            "--windowWidth", str(self.config.camera_window_width),
            "--windowHeight", str(self.config.camera_window_height),
        ]
        
        try:
            self.camera_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._log(f"Camera process started (PID: {self.camera_process.pid})")
            return True
        except Exception as e:
            error_msg = f"Failed to start camera: {e}"
            self._log(error_msg)
            self.last_error = error_msg
            return False
    
    def stop_session(self) -> None:
        """Stop all session processes in the correct order."""
        self._log("Stopping session...")
        
        # Stop camera first by creating its stop signal file
        self._stop_camera_gracefully()
        
        # The camera creates camera_finished.signal when it exits,
        # which tells the DAQ to stop. But if camera didn't run or failed,
        # we create it manually.
        self._create_daq_stop_signal()
        
        # Stop DAQ
        self._cleanup_daq()
        
        self.is_started = False
        self._log("Session stopped")
    
    def _stop_camera_gracefully(self) -> None:
        """Stop the camera by creating its stop signal file."""
        if self.camera_process is None:
            return
        
        self._log("Stopping camera gracefully...")
        
        # Create the stop signal file that the camera watches for
        stop_signal_file = os.path.join(
            self.config.session_folder,
            f"stop_camera_{self.config.rig_number}.signal"
        )
        self._log(f"Creating camera stop signal: {stop_signal_file}")
        
        try:
            os.makedirs(self.config.session_folder, exist_ok=True)
            with open(stop_signal_file, 'w') as f:
                f.write(f"Stop requested at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self._log("Camera stop signal created")
        except Exception as e:
            self._log(f"Error creating camera stop signal: {e}")
        
        # Wait for camera to stop gracefully (it checks the signal every 30 frames)
        self._log("Waiting for camera to stop gracefully (max 15s)...")
        try:
            self.camera_process.wait(timeout=15)
            self._log(f"Camera stopped gracefully (exit code: {self.camera_process.returncode})")
        except subprocess.TimeoutExpired:
            self._log("Camera did not stop gracefully, terminating...")
            try:
                self.camera_process.terminate()
                self.camera_process.wait(timeout=5)
                self._log(f"Camera terminated (exit code: {self.camera_process.returncode})")
            except subprocess.TimeoutExpired:
                self._log("Camera did not respond to terminate, killing...")
                self.camera_process.kill()
                self._log("Camera killed")
        except Exception as e:
            self._log(f"Error stopping camera: {e}")
        finally:
            self.camera_process = None
        
        # Stop DAQ
        self._cleanup_daq()
        
        # Clean up signal files
        self._cleanup_signal_files()
        
        self.is_started = False
        self._log("Session stopped")
    
    def _cleanup_signal_files(self) -> None:
        """Remove signal files from the session folder."""
        signal_patterns = [
            f"rig_{self.config.rig_number}_arduino_connected.signal",
            f"rig_{self.config.rig_number}_camera_finished.signal",
            f"stop_camera_{self.config.rig_number}.signal",
        ]
        
        for pattern in signal_patterns:
            signal_file = os.path.join(self.config.session_folder, pattern)
            if os.path.exists(signal_file):
                try:
                    os.remove(signal_file)
                    self._log(f"Removed signal file: {pattern}")
                except Exception as e:
                    self._log(f"Error removing {pattern}: {e}")
    
    def _create_daq_stop_signal(self) -> None:
        """Create the signal file that tells the DAQ to stop gracefully."""
        signal_file = os.path.join(
            self.config.session_folder,
            f"rig_{self.config.rig_number}_camera_finished.signal"
        )
        self._log(f"Creating DAQ stop signal: {signal_file}")
        try:
            # Create session folder if it doesn't exist
            os.makedirs(self.config.session_folder, exist_ok=True)
            with open(signal_file, 'w') as f:
                f.write(f"Session stopped at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self._log("DAQ stop signal created")
        except Exception as e:
            self._log(f"Error creating stop signal: {e}")
    
    def _cleanup_daq(self) -> None:
        """Clean up the DAQ process."""
        if self.daq_process is not None:
            self._log("Stopping Arduino DAQ...")
            
            # First, wait a bit for DAQ to notice the signal file and stop gracefully
            self._log("Waiting for DAQ to stop gracefully (max 10s)...")
            try:
                self.daq_process.wait(timeout=10)
                self._log(f"Arduino DAQ stopped gracefully (exit code: {self.daq_process.returncode})")
            except subprocess.TimeoutExpired:
                self._log("DAQ did not stop gracefully, terminating...")
                try:
                    self.daq_process.terminate()
                    self.daq_process.wait(timeout=5)
                    self._log(f"Arduino DAQ terminated (exit code: {self.daq_process.returncode})")
                except subprocess.TimeoutExpired:
                    self._log("DAQ did not respond to terminate, killing...")
                    self.daq_process.kill()
                    self._log("Arduino DAQ killed")
            except Exception as e:
                self._log(f"Error stopping DAQ: {e}")
            finally:
                self.daq_process = None
    
    def is_running(self) -> bool:
        """Check if session processes are running."""
        if not self.is_started:
            return False
        
        # Check DAQ process
        if self.daq_process is not None and self.daq_process.poll() is not None:
            return False
        
        # Check camera process
        if self.camera_process is not None and self.camera_process.poll() is not None:
            return False
        
        return True
