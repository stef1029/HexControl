"""
Simulated Scales Client & Manager — backed by VirtualRigState.

Drop-in replacements for MockScalesClient / MockScalesManager that read
platform weight from the shared VirtualRigState (controlled by the GUI
weight slider) instead of always returning 0.0.

Usage:
    from core.virtual_rig_state import VirtualRigState
    from ScalesLink.simulated import SimulatedScalesManager

    state   = VirtualRigState()
    manager = SimulatedScalesManager(virtual_rig_state=state, log_callback=print)
    manager.start()
    weight  = manager.client.get_weight()   # returns state.get_weight()
    manager.stop()
"""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.virtual_rig_state import VirtualRigState


class SimulatedScalesClient:
    """
    Scales client that reads weight from VirtualRigState.

    Matches the public interface of ScalesClient / MockScalesClient.
    """

    def __init__(self, state: "VirtualRigState", tcp_port: int = 5100, host: str = "localhost"):
        self._state = state
        self._tcp_port = tcp_port
        self._host = host
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def tcp_port(self) -> int:
        return self._tcp_port

    def connect(self, timeout: float = 10.0) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def shutdown(self) -> bool:
        self._connected = False
        return True

    def ping(self, timeout: float = 5.0) -> bool:
        return True

    def get_weight(self, timeout: float = 5.0) -> Optional[float]:
        """Return the current platform weight from VirtualRigState."""
        return self._state.get_weight()


class SimulatedScalesManager:
    """
    Scales manager that creates a SimulatedScalesClient backed by VirtualRigState.

    Matches the public interface of ScalesManager / MockScalesManager.
    """

    def __init__(
        self,
        virtual_rig_state: "VirtualRigState",
        com_port: str = "",
        baud_rate: int = 115200,
        tcp_port: int = 5100,
        is_wired: bool = False,
        calibration_scale: float = 1.0,
        calibration_intercept: float = 0.0,
        session_folder: str = "",
        date_time: str = "",
        mouse_id: str = "",
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self._state = virtual_rig_state
        self._log = log_callback or print
        self._started = False
        self.client: Optional[SimulatedScalesClient] = None
        self.last_error: Optional[str] = None
        self._tcp_port = tcp_port

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> bool:
        """Create a SimulatedScalesClient backed by VirtualRigState."""
        self._log("SimulatedScalesManager: starting virtual scales")
        self.client = SimulatedScalesClient(self._state, tcp_port=self._tcp_port)
        self.client.connect()
        self._started = True
        self._log("SimulatedScalesManager: virtual scales ready (weight from GUI slider)")
        return True

    def stop(self) -> None:
        """Stop the simulated scales."""
        if self._started:
            self._log("SimulatedScalesManager: stopping virtual scales")
            if self.client is not None:
                self.client.disconnect()
                self.client = None
            self._started = False
