"""
Base Protocol Class for Behaviour Experiments.

Simplified protocol system. A protocol must:
    1. Inherit from BaseProtocol
    2. Implement: get_name(), get_description(), get_parameters(), _run_protocol()
    3. Optionally implement: _setup(), _cleanup(), _on_abort()

The protocol lifecycle:
    _setup() -> _run_protocol() -> _cleanup()

Key things to know:
    - Access parameters via: self.parameters["name"]
    - Control rig via: self.link.led_set(), self.link.valve_pulse(), etc.
    - Check for abort: if self._check_abort(): return
    - Log to GUI: self._emit_event(ProtocolEvent("status_update", data={"message": "..."}))
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable

from .parameter_types import Parameter


# =============================================================================
# Protocol Status - Simplified to 4 core states
# =============================================================================

class ProtocolStatus(Enum):
    """Protocol states: IDLE -> RUNNING -> COMPLETED/ABORTED/ERROR"""
    IDLE = auto()       # Not started
    RUNNING = auto()    # Currently executing
    COMPLETED = auto()  # Finished successfully
    ABORTED = auto()    # User stopped it
    ERROR = auto()      # Something went wrong


# =============================================================================
# Protocol Event - For logging to GUI
# =============================================================================

@dataclass
class ProtocolEvent:
    """
    Event sent to GUI for logging.
    
    Usage:
        self._emit_event(ProtocolEvent("status_update", data={"message": "Hello"}))
    """
    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


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
        _cleanup() - Called after (always runs, even on error)
        _on_abort() - Called when user clicks Stop
    """

    def __init__(
        self,
        parameters: dict[str, Any],
        link: "BehaviourRigLink | None" = None,
    ):
        self.parameters = parameters  # Dict of parameter values
        self.link = link              # BehaviourRigLink (direct hardware access)
        self.status = ProtocolStatus.IDLE
        
        self._abort_requested = False
        self._event_listeners: list[Callable[[ProtocolEvent], None]] = []
        self._start_time: datetime | None = None

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

    @abstractmethod
    def _run_protocol(self) -> None:
        """
        Main protocol loop. This is where your experiment runs!
        
        Important:
            - Check self._check_abort() regularly and return early if True
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
        """Called after _run_protocol. Always runs! Turn off outputs here."""
        pass

    def _on_abort(self) -> None:
        """Called when user clicks Stop. Turn off outputs immediately."""
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

        try:
            self.status = ProtocolStatus.RUNNING
            self._emit_event(ProtocolEvent("protocol_started"))
            
            self._setup()
            self._run_protocol()
            
            # Set final status
            if self._abort_requested:
                self.status = ProtocolStatus.ABORTED
            else:
                self.status = ProtocolStatus.COMPLETED

        except Exception as e:
            self.status = ProtocolStatus.ERROR
            self._emit_event(ProtocolEvent("error", data={"error": str(e)}))
            error = e

        finally:
            try:
                self._cleanup()
            except Exception:
                pass  # Don't mask original error

        if error is not None:
            raise error

    def request_abort(self) -> None:
        """Called when user clicks Stop."""
        self._abort_requested = True
        try:
            self._on_abort()
        except Exception:
            pass  # Ignore errors during abort (serial may be disconnected)

    def add_event_listener(self, listener: Callable[[ProtocolEvent], None]) -> None:
        """Register a callback to receive events (used by GUI)."""
        self._event_listeners.append(listener)

    # =========================================================================
    # Protected Methods - Use these in your protocol
    # =========================================================================

    def _emit_event(self, event: ProtocolEvent) -> None:
        """
        Send an event to the GUI log.
        
        Usage:
            self._emit_event(ProtocolEvent(
                "status_update", 
                data={"message": "Starting trial 1"}
            ))
        """
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception:
                pass

    def _check_abort(self) -> bool:
        """
        Check if user wants to stop.
        
        Call this regularly in your loop:
            if self._check_abort():
                return
        """
        return self._abort_requested

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
