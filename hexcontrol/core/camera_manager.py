"""
Camera Manager - Manages the lifecycle of the camera executable subprocess.

Encapsulates the subprocess launch, signal-file-based shutdown, and cleanup
that was previously inline in PeripheralManager.

Usage:
    manager = CameraManager(
        camera_executable="/path/to/Camera.exe",
        camera_serial="24243513",
        mouse_id="mouse1",
        date_time="250219_120000",
        session_folder="/path/to/session",
        rig_number=1,
    )
    manager.on("log", lambda message: print(message))

    if manager.start():
        # Camera is recording
        ...

    manager.stop()
"""

import logging
import os
import subprocess
import sys
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CameraManager:
    """
    Manages the lifecycle of the camera executable subprocess.
    
    Handles launching the camera executable, and graceful shutdown
    via signal files.
    """
    
    def __init__(
        self,
        camera_executable: str,
        camera_serial: str,
        mouse_id: str,
        date_time: str,
        session_folder: str,
        rig_number: int,
        fps: int = 30,
        window_width: int = 640,
        window_height: int = 512,
        simulate: bool = False,
    ):
        """
        Initialise the camera manager.

        Args:
            camera_executable: Path to the camera executable.
            camera_serial: Camera serial number.
            mouse_id: Mouse identifier for this session.
            date_time: Date/time string for this session.
            session_folder: Path to the session output folder.
            rig_number: Rig number (used for signal file naming).
            fps: Camera frame rate.
            window_width: Preview window width.
            window_height: Preview window height.
            simulate: If True, skip subprocess launch and return success.
        """
        self._simulate = simulate

        if not simulate:
            if not camera_executable:
                raise ValueError("camera_executable must be provided")
            if not camera_serial:
                raise ValueError("camera_serial must be provided")

        self.camera_executable = camera_executable
        self.camera_serial = camera_serial
        self.mouse_id = mouse_id
        self.date_time = date_time
        self.session_folder = session_folder
        self.rig_number = rig_number
        self.fps = fps
        self.window_width = window_width
        self.window_height = window_height

        self._listeners: dict[str, list[Callable]] = {}
        self._process: Optional[subprocess.Popen] = None
        self._started: bool = False
        self.last_error: Optional[str] = None

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a callback for a named event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def _emit(self, event_name: str, **kwargs) -> None:
        """Fire an event to registered listeners."""
        if event_name == "log":
            message = kwargs.get("message", "")
            logger.info(f"[Camera] {message}")
        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception as e:
                logger.warning(f"listener error in '{event_name}': {e}")
    
    @property
    def is_running(self) -> bool:
        """Check if the camera process is alive."""
        if self._simulate:
            return self._started
        return self._process is not None and self._process.poll() is None
    
    def start(self) -> bool:
        """
        Start the camera subprocess.
        
        Returns:
            True if the camera process launched successfully.
        """
        if self._simulate:
            self._emit("log", message="Camera (simulated): skipping subprocess launch")
            self._started = True
            return True

        if not os.path.exists(self.camera_executable):
            self.last_error = f"Camera executable not found: {self.camera_executable}"
            self._emit("log", message=self.last_error)
            return False
        
        command = [
            self.camera_executable,
            "--id", self.mouse_id,
            "--date", self.date_time,
            "--path", self.session_folder,
            "--serial_number", self.camera_serial,
            "--fps", str(self.fps),
            "--windowWidth", str(self.window_width),
            "--windowHeight", str(self.window_height),
        ]
        
        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._emit("log", message=f"Camera started (PID: {self._process.pid})")

            # Health check: give the process a moment to fail fast
            time.sleep(1.0)
            if self._process.poll() is not None:
                stderr = ""
                try:
                    stderr = self._process.stderr.read().decode(errors="replace").strip()
                except Exception as e:
                    logger.warning(f"could not read camera stderr: {e}")
                self.last_error = (
                    f"Camera process exited immediately (code {self._process.returncode})"
                    + (f": {stderr}" if stderr else "")
                )
                self._emit("log", message=self.last_error)
                self._process = None
                return False

            return True
        except Exception as e:
            self.last_error = f"Failed to start camera: {e}"
            self._emit("log", message=self.last_error)
            return False
    
    def stop(self) -> None:
        """
        Stop the camera gracefully via signal file, then clean up.
        """
        if self._simulate:
            if self._started:
                self._emit("log", message="Camera (simulated): stopping")
                self._started = False
            return

        self._create_stop_signal()
        self._cleanup_process()
        self._cleanup_signal_files()
    
    def _create_stop_signal(self) -> None:
        """Create the signal file that tells the camera to stop."""
        if self._process is None:
            return
        
        stop_signal_file = os.path.join(
            self.session_folder,
            f"stop_camera_{self.rig_number}.signal"
        )
        
        try:
            os.makedirs(self.session_folder, exist_ok=True)
            with open(stop_signal_file, 'w') as f:
                f.write(f"Stop requested at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            self._emit("log", message=f"Error creating camera stop signal: {e}")
    
    def _cleanup_process(self) -> None:
        """Wait for the camera process to exit, terminating if necessary."""
        if self._process is None:
            return
        
        try:
            self._process.wait(timeout=15)
            self._emit("log", message=f"Camera stopped (exit code: {self._process.returncode})")
        except subprocess.TimeoutExpired:
            self._emit("log", message="Camera timeout, terminating...")
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        except Exception as e:
            self._emit("log", message=f"Error stopping camera: {e}")
        finally:
            self._process = None
    
    def _cleanup_signal_files(self) -> None:
        """Remove the camera stop signal file."""
        signal_file = os.path.join(
            self.session_folder,
            f"stop_camera_{self.rig_number}.signal"
        )
        if os.path.exists(signal_file):
            try:
                os.remove(signal_file)
            except Exception as e:
                logger.warning(f"could not remove signal file: {e}")
