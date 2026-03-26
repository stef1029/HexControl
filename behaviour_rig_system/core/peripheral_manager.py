"""
Peripheral Manager

Handles the startup and shutdown of peripheral processes (DAQ, camera, scales) for behaviour sessions.

Individual peripherals are managed by dedicated manager classes:
    - DAQLink.manager.DAQManager
    - ScalesLink.manager.ScalesManager
    - core.camera_manager.CameraManager

PeripheralManager orchestrates these managers and provides a unified interface
for the GUI layer.
"""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import yaml

from core.board_registry import BoardRegistry
from DAQLink.manager import DAQManager
from ScalesLink.manager import ScalesManager

from .camera_manager import CameraManager


@dataclass
class ScalesProcessConfig:
    """Configuration for scales subprocess."""
    board_name: str = ""
    baud_rate: int = 115200
    is_wired: bool = False
    calibration_scale: float = 1.0
    calibration_intercept: float = 0.0
    tcp_port: int = 5100


@dataclass
class PeripheralConfig:
    """Configuration for peripheral processes."""
    # Rig info
    rig_name: str
    rig_number: int
    camera_serial: str
    
    # Board tags (resolved to COM ports via board registry)
    behaviour_board_tag: str
    daq_board_tag: str
    board_registry_path: Path
    
    # Session info
    mouse_id: str
    session_folder: str
    multi_session_folder: str  # Parent folder containing all sessions from this run
    date_time: str
    
    # Process paths
    camera_executable: str
    
    # Board registry names
    daq_board_name: str = ""
    
    # Settings
    connection_timeout: int = 30
    camera_fps: int = 30
    camera_window_width: int = 960
    camera_window_height: int = 768
    
    # Scales subprocess config
    scales: ScalesProcessConfig = None


def _load_scales_config(rig_config: dict, rig_number: int) -> ScalesProcessConfig:
    """
    Load scales configuration from rig config.
    
    Args:
        rig_config: Dict with rig-specific settings (including scales sub-dict)
        rig_number: Rig number for TCP port assignment
        
    Returns:
        ScalesProcessConfig with all settings populated.
        
    Raises:
        ValueError: If scales section or board_name is missing from rig config.
    """
    scales_yaml = rig_config.get("scales")
    if not scales_yaml:
        raise ValueError("Scales configuration missing from rig config")
    
    board_name = scales_yaml.get("board_name", "")
    if not board_name:
        raise ValueError("Scales board_name missing from rig config")
    
    # Get baud rate from rigs config
    baud_rate = scales_yaml.get("baud_rate", 115200)
    
    # Assign unique TCP port per rig (5100 + rig_number)
    tcp_port = 5100 + rig_number
    
    return ScalesProcessConfig(
        board_name=board_name,
        baud_rate=baud_rate,
        is_wired=scales_yaml.get("is_wired", False),
        calibration_scale=scales_yaml.get("calibration_scale", 1.0),
        calibration_intercept=scales_yaml.get("calibration_intercept", 0.0),
        tcp_port=tcp_port,
    )


def load_peripheral_config(
    rig_config: dict, 
    mouse_id: str = "test", 
    save_directory: str = "",
    shared_multi_session: str | None = None
) -> PeripheralConfig:
    """
    Load peripheral configuration from rig config and global settings.
    
    Args:
        rig_config: Dict with rig-specific settings (including config_path)
        mouse_id: Mouse identifier for this session
        save_directory: Full path to the save directory (e.g., D:\\behaviour_data\\cohort_name)
        shared_multi_session: Optional shared multi-session folder timestamp.
                              If provided, uses this for the multi-session folder
                              instead of generating a new one. This allows multiple
                              rigs to share the same parent folder.
        
    Returns:
        PeripheralConfig with all settings populated
    """
    config_path = rig_config.get("config_path")
    if not config_path:
        config_path = Path(__file__).parent.parent / "config" / "rigs.yaml"
    
    with open(config_path) as f:
        full_config = yaml.safe_load(f)
    
    process_settings = full_config.get("processes", {})
    board_registry_path = Path(rig_config.get("board_registry_path", ""))
    
    rig_name = rig_config.get("name", "Rig 1")
    try:
        rig_number = int(rig_name.split()[-1])
    except (ValueError, IndexError):
        rig_number = 1
    
    # Use shared multi-session folder if provided, otherwise generate new timestamp
    if shared_multi_session:
        date_time = shared_multi_session
    else:
        date_time = datetime.now().strftime("%y%m%d_%H%M%S")
    
    multi_session_folder = os.path.join(save_directory, date_time)
    session_folder = os.path.join(multi_session_folder, f"{date_time}_{mouse_id}")
    
    # Load scales config
    scales_config = _load_scales_config(rig_config, rig_number)
    
    return PeripheralConfig(
        rig_name=rig_name,
        rig_number=rig_number,
        camera_serial=rig_config.get("camera_serial", ""),
        behaviour_board_tag=rig_config.get("board_name", ""),
        daq_board_tag=rig_config.get("daq_board_name", ""),
        board_registry_path=board_registry_path,
        mouse_id=mouse_id,
        session_folder=session_folder,
        multi_session_folder=multi_session_folder,
        date_time=date_time,
        camera_executable=process_settings.get("camera_executable", ""),
        daq_board_name=rig_config.get("daq_board_name", ""),
        connection_timeout=process_settings.get("connection_timeout", 30),
        camera_fps=process_settings.get("camera_fps", 30),
        camera_window_width=process_settings.get("camera_window_width", 640),
        camera_window_height=process_settings.get("camera_window_height", 512),
        scales=scales_config,
    )


class PeripheralManager:
    """
    Manages the startup and shutdown of peripheral processes (DAQ, camera, scales).
    
    Delegates to dedicated manager classes for each peripheral:
        - DAQManager (from DAQLink)
        - CameraManager (from core.camera_manager)
        - ScalesManager (from ScalesLink)
    """
    
    def __init__(
        self,
        config: PeripheralConfig,
        simulate: bool = False,
        virtual_rig_state=None,
    ):
        self.config = config
        self._simulate = simulate
        self._virtual_rig_state = virtual_rig_state

        self._listeners: dict[str, list[Callable]] = {}

        # Sub-managers (created during startup)
        self._daq_manager = None
        self._camera_manager = None
        self._scales_manager = None

        # Scales client (for protocols to use) — proxied from scales manager
        self.scales_client = None

        # State
        self.is_started = False
        self.session_folder_created = False
        self.last_error: Optional[str] = None

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a callback for a named event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def _emit(self, event_name: str, **kwargs) -> None:
        """Fire an event to registered listeners."""
        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception:
                pass

    def _log(self, message: str) -> None:
        """Internal log helper — emits a 'log' event."""
        self._emit("log", message=message)
    
    def start_daq(self) -> bool:
        """Start the Arduino DAQ process via DAQManager."""
        self._daq_manager = DAQManager(
            mouse_id=self.config.mouse_id,
            date_time=self.config.date_time,
            session_folder=self.config.session_folder,
            rig_number=self.config.rig_number,
            daq_board_name=self.config.daq_board_name,
            board_registry_path=str(self.config.board_registry_path),
            connection_timeout=self.config.connection_timeout,
            log_callback=self._log,
            simulate=self._simulate,
        )
        
        result = self._daq_manager.start()
        if not result:
            self.last_error = self._daq_manager.last_error
        return result
    
    def wait_for_daq_connection(self) -> bool:
        """Wait for the Arduino DAQ connection signal."""
        if self._daq_manager is None:
            raise RuntimeError("DAQ manager not initialised — call start_daq() first")
        
        result = self._daq_manager.wait_for_connection()
        if not result:
            self.last_error = self._daq_manager.last_error
        return result
    
    def start_camera(self) -> bool:
        """Start the camera process via CameraManager."""
        self._camera_manager = CameraManager(
            camera_executable=self.config.camera_executable,
            camera_serial=self.config.camera_serial,
            mouse_id=self.config.mouse_id,
            date_time=self.config.date_time,
            session_folder=self.config.session_folder,
            rig_number=self.config.rig_number,
            fps=self.config.camera_fps,
            window_width=self.config.camera_window_width,
            window_height=self.config.camera_window_height,
            simulate=self._simulate,
        )
        self._camera_manager.on("log", lambda message: self._log(message))
        
        result = self._camera_manager.start()
        if not result:
            self.last_error = self._camera_manager.last_error
        return result
    
    def start_scales(self) -> bool:
        """Start the scales server subprocess via ScalesManager."""
        scales_cfg = self.config.scales
        
        # In simulate mode, skip real hardware resolution
        if self._simulate:
            com_port = "MOCK"
        else:
            # Resolve board name (or raw COM port) via board registry
            try:
                registry = BoardRegistry(self.config.board_registry_path)
                com_port = registry.resolve_port(scales_cfg.board_name)
            except (FileNotFoundError, KeyError, RuntimeError) as e:
                self.last_error = f"Failed to resolve scales board '{scales_cfg.board_name}': {e}"
                self._log(self.last_error)
                return False
        
        self._scales_manager = ScalesManager(
            com_port=com_port,
            baud_rate=scales_cfg.baud_rate,
            tcp_port=scales_cfg.tcp_port,
            is_wired=scales_cfg.is_wired,
            calibration_scale=scales_cfg.calibration_scale,
            calibration_intercept=scales_cfg.calibration_intercept,
            session_folder=self.config.session_folder,
            date_time=self.config.date_time,
            mouse_id=self.config.mouse_id,
            log_callback=self._log,
            simulate=self._simulate,
            virtual_rig_state=self._virtual_rig_state,
        )
        
        result = self._scales_manager.start()
        if result:
            self.scales_client = self._scales_manager.client
        else:
            self.last_error = self._scales_manager.last_error
        return result
    
    def stop(self) -> None:
        """Stop all peripheral processes in the correct order."""
        self._log("Stopping peripherals...")
        
        # Stop scales first
        if self._scales_manager is not None:
            self._scales_manager.stop()
            self._scales_manager = None
            self.scales_client = None
        
        # Stop camera (creates stop signal, waits for exit)
        if self._camera_manager is not None:
            self._camera_manager.stop()
            self._camera_manager = None
        
        # Stop DAQ (creates camera-finished signal, waits for exit)
        if self._daq_manager is not None:
            self._daq_manager.stop()
            self._daq_manager = None
        
        self.is_started = False
        self._log("Peripherals stopped")
    
    def is_running(self) -> bool:
        """Check if peripheral processes are running."""
        if not self.is_started:
            return False
        
        if self._daq_manager is not None and not self._daq_manager.is_running:
            return False
        
        if self._camera_manager is not None and not self._camera_manager.is_running:
            return False
        
        return True
