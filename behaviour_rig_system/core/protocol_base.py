"""
Base Protocol Class for Behaviour Experiments.

Simplified protocol system. A protocol must:
    1. Inherit from BaseProtocol
    2. Implement: get_name(), get_description(), get_parameters(), _run_protocol()
    3. Optionally implement: _setup(), _cleanup()

The protocol lifecycle:
    _setup() -> _run_protocol() -> _cleanup()

Key things to know:
    - Access parameters via: self.parameters["name"]
    - Control rig via: self.link.led_set(), self.link.valve_pulse(), etc.
    - Check for stop: if self.check_stop(): return
    - Log to GUI: self.log("message")
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum, auto
import threading
import time as _time
from typing import Any, Callable

from .parameter_types import Parameter


# =============================================================================
# Protocol Status - Simplified to 4 core states
# =============================================================================

class ProtocolStatus(Enum):
    """Protocol states: IDLE -> RUNNING -> COMPLETED/STOPPED/ERROR"""
    IDLE = auto()       # Not started
    RUNNING = auto()    # Currently executing
    COMPLETED = auto()  # Finished successfully
    STOPPED = auto()    # User stopped it
    ERROR = auto()      # Something went wrong


# =============================================================================
# Base Protocol Class
# =============================================================================

class BaseProtocol(ABC):
    """
    Base class for all behaviour protocols.
    
    MUST implement:
        get_name() - Display name for GUI tab
        get_description() - Description shown in GUI
        get_parameters() - List of configurable parameters
        _run_protocol() - Main behaviour loop
    
    CAN implement:
        _setup() - Called before _run_protocol
        _cleanup() - Called after (always runs, even on error/stop)
    """

    def __init__(
        self,
        parameters: dict[str, Any],
        link: Any | None = None,
    ):
        self.parameters = parameters  # Dict of parameter values
        self.link = link              # BehaviourRigLink (direct hardware access)
        self.status = ProtocolStatus.IDLE
        self.scales = None
        self.perf_trackers: dict[str, Any] = {}  # TrackerGroups (or legacy PerformanceTrackers)
        self.tracker_groups: dict[str, Any] = {}  # Same reference as perf_trackers (new name)
        self.rig_number: int | None = None
        self.reward_durations: list[int] = [500] * 6  # Per-port reward durations (ms)

        self._stop_requested = False
        self._duration_exceeded = False
        self._duration_timer: threading.Timer | None = None
        self._listeners: dict[str, list[Callable]] = {}
        self._start_time: datetime | None = None
        self._clock = None  # Optional BehaviourClock for accelerated simulation

    # =========================================================================
    # Abstract Methods - YOU MUST IMPLEMENT THESE
    # =========================================================================

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """Return protocol name for GUI."""
        pass

    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        """Return description for GUI."""
        pass

    @classmethod
    @abstractmethod
    def get_parameters(cls) -> list[Parameter]:
        """Return list of configurable parameters."""
        pass

    @classmethod
    def get_tracker_definitions(cls) -> list:
        """Optional: declare named performance trackers for this protocol.

        Returns a list of TrackerDefinition. If empty, no trackers are created
        and the GUI shows a placeholder message.
        """
        return []

    @abstractmethod
    def _run_protocol(self) -> None:
        """
        Main protocol loop. This is where your experiment runs!
        
        Important:
            - Check self.check_stop() regularly and return early if True
            - Use self.link to control the rig (BehavLink functions)
            - Use self.parameters["name"] to access parameter values
        """
        pass

    # =========================================================================
    # Optional Override Methods
    # =========================================================================

    def _setup(self) -> None:
        """Called before _run_protocol. Override for initialization."""
        pass

    def _cleanup(self) -> None:
        """Called after _run_protocol (always runs, even on error/stop).
        Override for any protocol-specific teardown. Hardware shutdown
        is handled by the session controller."""
        pass

    # =========================================================================
    # Public Methods
    # =========================================================================

    def run(self) -> None:
        """
        Execute the protocol lifecycle: setup -> run -> cleanup.

        Called by the GUI when Start is clicked.
        """
        if self.status != ProtocolStatus.IDLE:
            raise RuntimeError(f"Protocol already in state {self.status.name}")

        self._start_time = datetime.now()
        error: Exception | None = None

        # Start max-duration timer if configured
        max_minutes = self.parameters.get("max_duration_minutes", 0)
        if max_minutes and max_minutes > 0:
            def _duration_timeout():
                self._duration_exceeded = True
                self._stop_requested = True
                self.log(f"Max session duration reached ({max_minutes} min) — finishing current trial...")

            self._duration_timer = threading.Timer(float(max_minutes) * 60, _duration_timeout)
            self._duration_timer.daemon = True
            self._duration_timer.start()

        try:
            self.status = ProtocolStatus.RUNNING
            self._emit("started")

            # Configure all DAQ link pins and GPIO pins as outputs (driven LOW).
            # This prevents floating pins from picking up noise on the DAQ.
            # Individual protocols can reconfigure specific GPIO pins in
            # _setup() if they need a different mode (e.g. GPIOMode.INPUT).
            self._init_outputs()

            self._setup()
            self._run_protocol()

            # Set final status: duration limit is a normal completion
            if self._duration_exceeded:
                self.status = ProtocolStatus.COMPLETED
            elif self._stop_requested:
                self.status = ProtocolStatus.STOPPED
            else:
                self.status = ProtocolStatus.COMPLETED

        except Exception as e:
            self.status = ProtocolStatus.ERROR
            self._emit("error", error=str(e))
            error = e

        finally:
            # Cancel duration timer if still pending
            if self._duration_timer is not None:
                self._duration_timer.cancel()
                self._duration_timer = None
            try:
                self._cleanup()
            except Exception as e:
                print(f"Warning: cleanup error: {e}")

        if error is not None:
            raise error

    def request_stop(self) -> None:
        """Called when user clicks Stop. Hardware shutdown is handled
        by the session controller after the protocol exits."""
        self._stop_requested = True

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a callback for a named event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def set_runtime_context(
        self,
        *,
        scales=None,
        perf_trackers: dict | None = None,
        rig_number: int | None = None,
        clock=None,
        reward_durations: list[int] | None = None,
    ) -> None:
        """Attach runtime services provided by the GUI/orchestrator."""
        self.scales = scales
        self.perf_trackers = perf_trackers or {}
        self.tracker_groups = self.perf_trackers  # Alias for new code
        self.rig_number = rig_number
        self._clock = clock
        if reward_durations is not None:
            self.reward_durations = reward_durations

    # =========================================================================
    # Protected Methods - Use these in your protocol
    # =========================================================================

    def _init_outputs(self) -> None:
        """Configure all DAQ link pins and GPIO pins as outputs driven LOW.

        Runs automatically before _setup() so that every pin has a defined
        state from the start of the session. If a protocol needs a GPIO pin
        as an input, it can call
        ``self.link.gpio_configure(pin, GPIOMode.INPUT)`` in its own _setup().
        """
        if self.link is None:
            return
        try:
            # Initialise DAQ link pins LOW
            for i in range(self.link.NUM_DAQ_LINK_PINS):
                self.link.daq_link_set(i, False)
            # Initialise GPIO pins as outputs driven LOW
            from BehavLink import GPIOMode
            for pin in range(self.link.NUM_GPIO_PINS):
                self.link.gpio_configure(pin, GPIOMode.OUTPUT)
        except Exception as e:
            print(f"Warning: GPIO init failed: {e}")

    def _emit(self, event_name: str, **kwargs) -> None:
        """Fire an event to registered listeners."""
        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception as e:
                print(f"Warning: listener error in '{event_name}': {e}")

    def check_stop(self) -> bool:
        """
        Check if user wants to stop.

        Call this regularly in your loop:
            if self.check_stop():
                return
        """
        return self._stop_requested

    def log(self, message: str) -> None:
        """Convenience helper for status messages in the GUI log."""
        self._emit("log", message=message)

    def sleep(self, seconds: float) -> None:
        """Sleep for *seconds* (virtual time if a BehaviourClock is set)."""
        if self._clock is not None:
            self._clock.sleep(seconds)
        else:
            _time.sleep(seconds)

    def now(self) -> float:
        """Current time (virtual if a BehaviourClock is set, else wall clock)."""
        if self._clock is not None:
            return self._clock.time()
        return _time.time()

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def elapsed_time(self) -> float | None:
        """Seconds since protocol started."""
        if self._start_time is None:
            return None
        return (datetime.now() - self._start_time).total_seconds()

    @property
    def is_running(self) -> bool:
        """True if protocol is currently running."""
        return self.status == ProtocolStatus.RUNNING

    @classmethod
    def get_default_parameters(cls) -> dict[str, Any]:
        """Get dict of default parameter values."""
        return {p.name: p.default for p in cls.get_parameters()}
