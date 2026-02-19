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


@dataclass
class ScalesProcessConfig:
    """Configuration for scales subprocess."""
    enabled: bool = False
    com_port: str = ""
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
    
    # Session info
    mouse_id: str
    session_folder: str
    multi_session_folder: str  # Parent folder containing all sessions from this run
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
    
    # Scales subprocess config
    scales: Optional[ScalesProcessConfig] = None


def _load_scales_config(rig_config: dict, rig_number: int) -> Optional[ScalesProcessConfig]:
    """
    Load scales configuration from rig config.
    
    Args:
        rig_config: Dict with rig-specific settings (including scales sub-dict)
        rig_number: Rig number for TCP port assignment
        
    Returns:
        ScalesProcessConfig if scales are configured, None otherwise
    """
    scales_yaml = rig_config.get("scales")
    if not scales_yaml:
        return None
    
    com_port = scales_yaml.get("com_port", "")
    if not com_port:
        return None
    
    # Assign unique TCP port per rig (5100 + rig_number)
    tcp_port = 5100 + rig_number
    
    return ScalesProcessConfig(
        enabled=True,
        com_port=com_port,
        baud_rate=scales_yaml.get("baud_rate", 115200),
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
        mouse_id=mouse_id,
        session_folder=session_folder,
        multi_session_folder=multi_session_folder,
        date_time=date_time,
        python_path=process_settings.get("python_path", "python"),
        serial_listen_script=process_settings.get("serial_listen_script", ""),
        camera_executable=process_settings.get("camera_executable", ""),
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
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self._log = log_callback or print
        
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
    
    def start_daq(self) -> bool:
        """Start the Arduino DAQ process via DAQManager."""
        from DAQLink.manager import DAQManager
        
        self._daq_manager = DAQManager(
            python_path=self.config.python_path,
            serial_listen_script=self.config.serial_listen_script,
            mouse_id=self.config.mouse_id,
            date_time=self.config.date_time,
            session_folder=self.config.session_folder,
            rig_number=self.config.rig_number,
            connection_timeout=self.config.connection_timeout,
            log_callback=self._log,
        )
        
        result = self._daq_manager.start()
        if not result:
            self.last_error = self._daq_manager.last_error
        return result
    
    def wait_for_connection(self) -> bool:
        """Wait for the Arduino DAQ connection signal."""
        if self._daq_manager is None:
            return True
        
        result = self._daq_manager.wait_for_connection()
        if not result:
            self.last_error = self._daq_manager.last_error
        return result
    
    def start_camera(self) -> bool:
        """Start the camera process via CameraManager."""
        from .camera_manager import CameraManager
        
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
            log_callback=self._log,
        )
        
        result = self._camera_manager.start()
        if not result:
            self.last_error = self._camera_manager.last_error
        return result
    
    def start_scales(self) -> bool:
        """Start the scales server subprocess via ScalesManager."""
        scales_cfg = self.config.scales
        if scales_cfg is None or not scales_cfg.enabled:
            self._log("No scales configured for this rig")
            return True  # Not an error, just no scales
        
        from ScalesLink.manager import ScalesManager
        
        self._scales_manager = ScalesManager(
            com_port=scales_cfg.com_port,
            baud_rate=scales_cfg.baud_rate,
            tcp_port=scales_cfg.tcp_port,
            is_wired=scales_cfg.is_wired,
            calibration_scale=scales_cfg.calibration_scale,
            calibration_intercept=scales_cfg.calibration_intercept,
            session_folder=self.config.session_folder,
            date_time=self.config.date_time,
            mouse_id=self.config.mouse_id,
            log_callback=self._log,
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
