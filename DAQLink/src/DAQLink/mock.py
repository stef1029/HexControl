"""
Mock DAQ Manager - Simulates the DAQ subprocess lifecycle without hardware.

Provides the same interface as DAQManager but skips subprocess launch and
signal file coordination. Used for virtual rig testing.

Usage:
    from DAQLink.mock import MockDAQManager

    manager = MockDAQManager(log_callback=print)

    if manager.start():
        manager.wait_for_connection()
        ...

    manager.stop()
"""

import time
from typing import Callable, Optional


class MockDAQManager:
    """
    Mock DAQ manager that simulates startup/shutdown without hardware.

    Matches the public interface of DAQManager so PeripheralManager can
    use it as a drop-in replacement.
    """

    def __init__(
        self,
        mouse_id: str = "",
        date_time: str = "",
        session_folder: str = "",
        rig_number: int = 1,
        daq_board_name: str = "",
        connection_timeout: int = 30,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self._log = log_callback or print
        self._started = False
        self.last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Report whether the mock DAQ is 'running'."""
        return self._started

    def start(self) -> bool:
        """Simulate starting the DAQ subprocess."""
        self._log("MockDAQManager: simulating DAQ start")
        self._started = True
        return True

    def wait_for_connection(self) -> bool:
        """Simulate waiting for Arduino connection signal."""
        if not self._started:
            raise RuntimeError("DAQ process not started — call start() first")
        self._log("MockDAQManager: simulating DAQ connection (instant)")
        return True

    def stop(self) -> None:
        """Simulate stopping the DAQ subprocess."""
        if self._started:
            self._log("MockDAQManager: simulating DAQ stop")
            self._started = False
