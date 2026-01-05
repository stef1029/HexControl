"""
Base Protocol Class for Behaviour Experiments.

This module defines the abstract base class that all behaviour protocols must
inherit from. It establishes the contract between protocols and the system,
ensuring consistent structure across different experiment types.

A protocol is responsible for:
    - Declaring its configurable parameters
    - Implementing the main behaviour loop
    - Reporting events and outcomes to the monitoring system
    - Cleaning up resources when complete

The base class provides:
    - Standard lifecycle methods (setup, run, cleanup)
    - Event publishing for the live monitoring system
    - Access to hardware through the HardwareInterface
    - Status tracking and abort handling
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable

from .parameter_types import Parameter


class ProtocolStatus(Enum):
    """
    Enumeration of possible protocol states.

    The protocol progresses through these states during execution:
        IDLE -> INITIALISING -> RUNNING -> COMPLETED/ABORTED/ERROR
    """

    IDLE = auto()           # Protocol created but not started
    INITIALISING = auto()   # Setup phase in progress
    RUNNING = auto()        # Main behaviour loop executing
    PAUSED = auto()         # Temporarily paused (if supported)
    COMPLETED = auto()      # Finished successfully
    ABORTED = auto()        # User requested abort
    ERROR = auto()          # Terminated due to error


@dataclass
class ProtocolEvent:
    """
    Represents an event emitted by a protocol during execution.

    Events are used for:
        - Live monitoring display updates
        - Logging and data analysis
        - Synchronisation with external systems (DAQ, cameras)

    Attributes:
        event_type: Category of event (e.g., 'trial_start', 'reward').
        timestamp: When the event occurred.
        data: Optional dictionary of event-specific data.
    """

    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


class BaseProtocol(ABC):
    """
    Abstract base class for all behaviour protocols.

    Subclasses must implement:
        - get_name(): Return the protocol's display name
        - get_description(): Return a description for the GUI
        - get_parameters(): Return list of configurable parameters
        - _run_protocol(): The main behaviour loop implementation

    Subclasses may optionally override:
        - _setup(): Initialisation before the main loop
        - _cleanup(): Resource cleanup after completion
        - _on_abort(): Handle abort request gracefully

    Attributes:
        parameters: Dictionary of validated parameter values.
        hardware: Interface to the behaviour rig hardware.
        status: Current protocol status.
    """

    def __init__(
        self,
        parameters: dict[str, Any],
        hardware: "HardwareInterface | None" = None,
    ):
        """
        Initialise the protocol with validated parameters.

        Args:
            parameters: Dictionary of parameter values, already validated
                and converted to appropriate types.
            hardware: Hardware interface for rig communication. May be None
                for testing or simulation modes.
        """
        self.parameters = parameters
        self.hardware = hardware
        self.status = ProtocolStatus.IDLE

        self._abort_requested = False
        self._event_listeners: list[Callable[[ProtocolEvent], None]] = []
        self._start_time: datetime | None = None
        self._end_time: datetime | None = None

    # =========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =========================================================================

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """
        Return the display name of this protocol.

        This name is shown in the GUI protocol selector.

        Returns:
            A human-readable protocol name.
        """
        pass

    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        """
        Return a description of this protocol.

        This description is shown in the GUI to help users understand
        what the protocol does.

        Returns:
            A brief description of the protocol's purpose.
        """
        pass

    @classmethod
    @abstractmethod
    def get_parameters(cls) -> list[Parameter]:
        """
        Return the list of configurable parameters for this protocol.

        The GUI uses this list to generate input widgets. Parameters
        are displayed in order, grouped by their 'group' attribute.

        Returns:
            List of Parameter objects defining the protocol's settings.
        """
        pass

    @abstractmethod
    def _run_protocol(self) -> None:
        """
        Execute the main behaviour loop.

        This method contains the core logic of the protocol. It should:
            - Check self._abort_requested periodically
            - Emit events using self._emit_event()
            - Use self.hardware to interact with the rig
            - Access parameters via self.parameters dict

        The method should return normally when complete, or raise an
        exception if an error occurs. Abort handling is done by checking
        _abort_requested and returning early.
        """
        pass

    # =========================================================================
    # Optional Override Methods
    # =========================================================================

    def _setup(self) -> None:
        """
        Perform any initialisation before the main loop.

        Override this method to perform setup tasks such as:
            - Configuring hardware settings
            - Initialising data structures
            - Preparing output files

        Called automatically by run() before _run_protocol().
        """
        pass

    def _cleanup(self) -> None:
        """
        Perform cleanup after protocol completion.

        Override this method to perform cleanup tasks such as:
            - Resetting hardware to safe state
            - Closing files
            - Releasing resources

        Called automatically by run() after _run_protocol() completes,
        regardless of how it completed (success, abort, or error).
        """
        pass

    def _on_abort(self) -> None:
        """
        Handle an abort request.

        Override this method to perform any immediate actions needed
        when the user requests an abort, such as:
            - Stopping ongoing hardware operations
            - Saving partial data

        Called when request_abort() is invoked. The protocol should
        also check _abort_requested in its main loop and exit cleanly.
        """
        pass

    # =========================================================================
    # Public Methods
    # =========================================================================

    def run(self) -> None:
        """
        Execute the full protocol lifecycle.

        This method handles the complete execution sequence:
            1. Initialisation (_setup)
            2. Main loop (_run_protocol)
            3. Cleanup (_cleanup)

        Status is updated throughout and cleanup is guaranteed to run
        even if an error occurs.

        Raises:
            RuntimeError: If protocol is not in IDLE state.
            Exception: Re-raises any exception from _run_protocol after
                cleanup has completed.
        """
        if self.status != ProtocolStatus.IDLE:
            raise RuntimeError(
                f"Cannot start protocol in state {self.status.name}. "
                "Protocol must be in IDLE state."
            )

        self._start_time = datetime.now()
        error: Exception | None = None

        try:
            # Initialisation phase
            self.status = ProtocolStatus.INITIALISING
            self._emit_event(ProtocolEvent("protocol_initialising"))
            self._setup()

            # Main execution phase
            self.status = ProtocolStatus.RUNNING
            self._emit_event(ProtocolEvent("protocol_started"))
            self._run_protocol()

            # Determine final status
            if self._abort_requested:
                self.status = ProtocolStatus.ABORTED
                self._emit_event(ProtocolEvent("protocol_aborted"))
            else:
                self.status = ProtocolStatus.COMPLETED
                self._emit_event(ProtocolEvent("protocol_completed"))

        except Exception as e:
            self.status = ProtocolStatus.ERROR
            self._emit_event(
                ProtocolEvent("protocol_error", data={"error": str(e)})
            )
            error = e

        finally:
            # Cleanup always runs
            self._end_time = datetime.now()
            try:
                self._cleanup()
            except Exception as cleanup_error:
                # Log cleanup errors but don't mask original error
                self._emit_event(
                    ProtocolEvent(
                        "cleanup_error",
                        data={"error": str(cleanup_error)},
                    )
                )

        # Re-raise original error after cleanup
        if error is not None:
            raise error

    def request_abort(self) -> None:
        """
        Request that the protocol abort at the next safe point.

        This sets the _abort_requested flag and calls _on_abort().
        The protocol's main loop should check _abort_requested
        periodically and exit cleanly when it becomes True.

        This method is thread-safe and can be called from the GUI thread.
        """
        self._abort_requested = True
        self._on_abort()

    def add_event_listener(
        self, listener: Callable[[ProtocolEvent], None]
    ) -> None:
        """
        Register a callback to receive protocol events.

        Args:
            listener: A callable that accepts a ProtocolEvent. Called
                synchronously when events are emitted.
        """
        self._event_listeners.append(listener)

    def remove_event_listener(
        self, listener: Callable[[ProtocolEvent], None]
    ) -> None:
        """
        Remove a previously registered event listener.

        Args:
            listener: The listener to remove.
        """
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    # =========================================================================
    # Protected Methods - For use by subclasses
    # =========================================================================

    def _emit_event(self, event: ProtocolEvent) -> None:
        """
        Emit an event to all registered listeners.

        Args:
            event: The event to emit.
        """
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception:
                # Don't let listener errors crash the protocol
                pass

    def _check_abort(self) -> bool:
        """
        Check if an abort has been requested.

        Convenience method for use in the main loop.

        Returns:
            True if abort has been requested, False otherwise.
        """
        return self._abort_requested

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def elapsed_time(self) -> float | None:
        """
        Return the elapsed time in seconds since the protocol started.

        Returns:
            Elapsed time in seconds, or None if not started.
        """
        if self._start_time is None:
            return None

        end = self._end_time or datetime.now()
        return (end - self._start_time).total_seconds()

    @property
    def is_running(self) -> bool:
        """
        Check if the protocol is currently executing.

        Returns:
            True if status is INITIALISING or RUNNING.
        """
        return self.status in (
            ProtocolStatus.INITIALISING,
            ProtocolStatus.RUNNING,
        )

    @classmethod
    def get_default_parameters(cls) -> dict[str, Any]:
        """
        Return a dictionary of default parameter values.

        Useful for initialising the GUI with default values.

        Returns:
            Dictionary mapping parameter names to their default values.
        """
        return {param.name: param.default for param in cls.get_parameters()}
