"""
Mock Camera Manager - Simulates the camera subprocess lifecycle without hardware.

Provides the same interface as CameraManager but skips subprocess launch.
Used for virtual rig testing.

Usage:
    from behaviour_rig_system.core.mock_camera_manager import MockCameraManager

    manager = MockCameraManager(log_callback=print)

    if manager.start():
        # Camera is "recording"
        ...

    manager.stop()
"""

from typing import Callable, Optional


class MockCameraManager:
    """
    Mock camera manager that simulates startup/shutdown without hardware.

    Matches the public interface of CameraManager so PeripheralManager can
    use it as a drop-in replacement.
    """

    def __init__(
        self,
        camera_executable: str = "",
        camera_serial: str = "",
        mouse_id: str = "",
        date_time: str = "",
        session_folder: str = "",
        rig_number: int = 1,
        fps: int = 30,
        window_width: int = 640,
        window_height: int = 512,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self._log = log_callback or print
        self._started = False
        self.last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Report whether the mock camera is 'running'."""
        return self._started

    def start(self) -> bool:
        """Simulate starting the camera subprocess."""
        self._log("MockCameraManager: simulating camera start")
        self._started = True
        return True

    def stop(self) -> None:
        """Simulate stopping the camera subprocess."""
        if self._started:
            self._log("MockCameraManager: simulating camera stop")
            self._started = False
