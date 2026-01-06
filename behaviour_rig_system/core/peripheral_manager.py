"""
Peripheral Manager

Handles the startup and shutdown of peripheral processes (DAQ, camera) for behaviour sessions.
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
class PeripheralConfig:
    """Configuration for peripheral processes."""
    # Rig info
    rig_name: str
    rig_number: int
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
    connection_timeout: int = 30
    camera_fps: int = 30
    camera_window_width: int = 640
    camera_window_height: int = 512


def load_peripheral_config(rig_config: dict, mouse_id: str = "test", save_directory: str = "") -> PeripheralConfig:
    """
    Load peripheral configuration from rig config and global settings.
    
    Args:
        rig_config: Dict with rig-specific settings (including config_path)
        mouse_id: Mouse identifier for this session
        save_directory: Full path to the save directory (e.g., D:\\behaviour_data\\cohort_name)
        
    Returns:
        PeripheralConfig with all settings populated
    """
    config_path = rig_config.get("config_path")
    if not config_path:
        config_path = Path(__file__).parent.parent / "config" / "rigs.yaml"
    
    with open(config_path) as f:
        full_config = yaml.safe_load(f)
    
    process_settings = full_config.get("processes", {})
    
    rig_name = rig_config.get("name", "Rig 1")
    try:
        rig_number = int(rig_name.split()[-1])
    except (ValueError, IndexError):
        rig_number = 1
    
    date_time = datetime.now().strftime("%y%m%d_%H%M%S")
    session_folder = os.path.join(save_directory, f"{date_time}_{mouse_id}")
    
    return PeripheralConfig(
        rig_name=rig_name,
        rig_number=rig_number,
        camera_serial=rig_config.get("camera_serial", ""),
        mouse_id=mouse_id,
        session_folder=session_folder,
        date_time=date_time,
        python_path=process_settings.get("python_path", "python"),
        serial_listen_script=process_settings.get("serial_listen_script", ""),
        camera_executable=process_settings.get("camera_executable", ""),
        connection_timeout=process_settings.get("connection_timeout", 30),
        camera_fps=process_settings.get("camera_fps", 30),
        camera_window_width=process_settings.get("camera_window_width", 640),
        camera_window_height=process_settings.get("camera_window_height", 512),
    )


class PeripheralManager:
    """
    Manages the startup and shutdown of peripheral processes (DAQ, camera).
    """
    
    def __init__(
        self,
        config: PeripheralConfig,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self._log = log_callback or print
        
        # Process handles
        self.daq_process: Optional[subprocess.Popen] = None
        self.camera_process: Optional[subprocess.Popen] = None
        
        # State
        self.is_started = False
        self.session_folder_created = False
        self.last_error: Optional[str] = None
    
    def start(self) -> bool:
        """Start peripheral processes (DAQ and camera). Returns True on success."""
        self._log(f"Starting peripherals: {self.config.rig_name}, Mouse: {self.config.mouse_id}")
        self._log(f"Session folder: {self.config.session_folder}")
        
        try:
            os.makedirs(self.config.session_folder, exist_ok=True)
            self.session_folder_created = True
            
            if not self._start_daq():
                return False
            
            if not self._wait_for_connection():
                self._cleanup_daq()
                return False
            
            if not self._start_camera():
                self._cleanup_daq()
                return False
            
            self.is_started = True
            self._log("Peripherals started successfully")
            return True
            
        except Exception as e:
            self._log(f"Exception during startup: {e}")
            self.stop()
            return False
    
    def stop(self) -> None:
        """Stop all peripheral processes in the correct order."""
        self._log("Stopping peripherals...")
        
        self._stop_camera_gracefully()
        self._create_daq_stop_signal()
        self._cleanup_daq()
        self._cleanup_signal_files()
        
        self.is_started = False
        self._log("Peripherals stopped")
    
    def is_running(self) -> bool:
        """Check if peripheral processes are running."""
        if not self.is_started:
            return False
        
        if self.daq_process is not None and self.daq_process.poll() is not None:
            return False
        
        if self.camera_process is not None and self.camera_process.poll() is not None:
            return False
        
        return True
    
    def _start_daq(self) -> bool:
        """Start the Arduino DAQ process."""
        if not self.config.serial_listen_script:
            self._log("No serial listen script configured, skipping DAQ")
            return True
        
        if not os.path.exists(self.config.serial_listen_script):
            self.last_error = f"Serial listen script not found: {self.config.serial_listen_script}"
            self._log(self.last_error)
            return False
        
        if not os.path.exists(self.config.python_path):
            self.last_error = f"Python executable not found: {self.config.python_path}"
            self._log(self.last_error)
            return False
        
        command = [
            self.config.python_path,
            self.config.serial_listen_script,
            "--id", self.config.mouse_id,
            "--date", self.config.date_time,
            "--path", self.config.session_folder,
            "--rig", str(self.config.rig_number),
        ]
        
        try:
            self.daq_process = subprocess.Popen(
                command,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self._log(f"DAQ started (PID: {self.daq_process.pid})")
            return True
        except Exception as e:
            self.last_error = f"Failed to start Arduino DAQ: {e}"
            self._log(self.last_error)
            return False
    
    def _wait_for_connection(self) -> bool:
        """Wait for the Arduino connection signal file."""
        if self.daq_process is None:
            return True
        
        signal_file = os.path.join(
            self.config.session_folder,
            f"rig_{self.config.rig_number}_arduino_connected.signal"
        )
        
        self._log(f"Waiting for DAQ connection (timeout: {self.config.connection_timeout}s)...")
        start_time = time.time()
        
        while time.time() - start_time < self.config.connection_timeout:
            if os.path.exists(signal_file):
                self._log("DAQ connected")
                return True
            
            if self.daq_process.poll() is not None:
                self.last_error = f"DAQ process terminated (exit code: {self.daq_process.returncode})"
                self._log(self.last_error)
                return False
            
            time.sleep(0.5)
        
        self.last_error = f"Timeout waiting for Arduino connection ({self.config.connection_timeout}s)"
        self._log(self.last_error)
        return False
    
    def _start_camera(self) -> bool:
        """Start the camera process."""
        if not self.config.camera_executable:
            self._log("No camera executable configured, skipping camera")
            return True
        
        if not os.path.exists(self.config.camera_executable):
            self.last_error = f"Camera executable not found: {self.config.camera_executable}"
            self._log(self.last_error)
            return False
        
        if not self.config.camera_serial:
            self._log("No camera serial number configured, skipping camera")
            return True
        
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
            self._log(f"Camera started (PID: {self.camera_process.pid})")
            return True
        except Exception as e:
            self.last_error = f"Failed to start camera: {e}"
            self._log(self.last_error)
            return False
    
    def _stop_camera_gracefully(self) -> None:
        """Stop the camera by creating its stop signal file."""
        if self.camera_process is None:
            return
        
        stop_signal_file = os.path.join(
            self.config.session_folder,
            f"stop_camera_{self.config.rig_number}.signal"
        )
        
        try:
            os.makedirs(self.config.session_folder, exist_ok=True)
            with open(stop_signal_file, 'w') as f:
                f.write(f"Stop requested at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            self._log(f"Error creating camera stop signal: {e}")
        
        try:
            self.camera_process.wait(timeout=15)
            self._log(f"Camera stopped (exit code: {self.camera_process.returncode})")
        except subprocess.TimeoutExpired:
            self._log("Camera timeout, terminating...")
            try:
                self.camera_process.terminate()
                self.camera_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.camera_process.kill()
        except Exception as e:
            self._log(f"Error stopping camera: {e}")
        finally:
            self.camera_process = None
    
    def _create_daq_stop_signal(self) -> None:
        """Create the signal file that tells the DAQ to stop gracefully."""
        signal_file = os.path.join(
            self.config.session_folder,
            f"rig_{self.config.rig_number}_camera_finished.signal"
        )
        try:
            os.makedirs(self.config.session_folder, exist_ok=True)
            with open(signal_file, 'w') as f:
                f.write(f"Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            self._log(f"Error creating DAQ stop signal: {e}")
    
    def _cleanup_daq(self) -> None:
        """Clean up the DAQ process."""
        if self.daq_process is None:
            return
        
        try:
            self.daq_process.wait(timeout=10)
            self._log(f"DAQ stopped (exit code: {self.daq_process.returncode})")
        except subprocess.TimeoutExpired:
            self._log("DAQ timeout, terminating...")
            try:
                self.daq_process.terminate()
                self.daq_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.daq_process.kill()
        except Exception as e:
            self._log(f"Error stopping DAQ: {e}")
        finally:
            self.daq_process = None
    
    def _cleanup_signal_files(self) -> None:
        """Remove signal files from the session folder."""
        signal_files = [
            f"rig_{self.config.rig_number}_arduino_connected.signal",
            f"rig_{self.config.rig_number}_camera_finished.signal",
            f"stop_camera_{self.config.rig_number}.signal",
        ]
        
        for filename in signal_files:
            path = os.path.join(self.config.session_folder, filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
