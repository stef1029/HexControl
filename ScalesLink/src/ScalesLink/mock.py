"""
Mock Scales Client and Manager - Simulates scales without hardware.

Provides MockScalesClient (returns 0.0 for weight) and MockScalesManager
(skips subprocess launch, creates MockScalesClient directly).

Usage:
    from ScalesLink.mock import MockScalesManager

    manager = MockScalesManager(log_callback=print)
    if manager.start():
        weight = manager.client.get_weight()  # returns 0.0
    manager.stop()

    # Or use the client directly:
    from ScalesLink.mock import MockScalesClient
    client = MockScalesClient()
    client.get_weight()  # returns 0.0
"""

from typing import Callable, Optional


class MockScalesClient:
    """
    Mock scales client that returns 0.0 for all weight readings.

    Matches the public interface of ScalesClient so protocols can
    use it as a drop-in replacement.
    """

    def __init__(self, tcp_port: int = 5100, host: str = "localhost"):
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
        """Simulate connecting to the scales server."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Simulate disconnecting from the scales server."""
        self._connected = False

    def shutdown(self) -> bool:
        """Simulate sending shutdown command to the scales server."""
        self._connected = False
        return True

    def ping(self, timeout: float = 5.0) -> bool:
        """Simulate pinging the scales server."""
        return True

    def get_weight(self, timeout: float = 5.0) -> Optional[float]:
        """Return 0.0 as the mock weight."""
        return 0.0


class MockScalesManager:
    """
    Mock scales manager that simulates startup/shutdown without hardware.

    Matches the public interface of ScalesManager so PeripheralManager can
    use it as a drop-in replacement. Creates a MockScalesClient on start().
    """

    def __init__(
        self,
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
        self._log = log_callback or print
        self._started = False
        self.client: Optional[MockScalesClient] = None
        self.last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Report whether the mock scales server is 'running'."""
        return self._started

    def start(self) -> bool:
        """Simulate starting the scales server and creating a client."""
        self._log("MockScalesManager: simulating scales start")
        self.client = MockScalesClient()
        self.client.connect()
        self._started = True
        self._log("MockScalesManager: mock scales ready (weight=0.0g)")
        return True

    def stop(self) -> None:
        """Simulate stopping the scales server."""
        if self._started:
            self._log("MockScalesManager: simulating scales stop")
            if self.client is not None:
                self.client.disconnect()
                self.client = None
            self._started = False
