"""
Session Controller - Business logic for session lifecycle.

Manages the full session lifecycle with no tkinter dependency. Emits
named events so the GUI layer can react without the controller knowing
about widgets.

The lifecycle is split into four phases. Each phase is a small public
method that spawns one short-lived worker thread, does its job, emits a
single `*_complete` message, and exits. The GUI listens for each
`*_complete` message and triggers the next phase by calling the next
method on this controller.

Lifecycle chain:
    start_session       -> emits "startup_complete" / "startup_error" / "startup_cancelled"
    run_protocol        -> emits "protocol_complete"
    finalize_protocol   -> emits "finalize_complete"
    cleanup_session     -> emits "cleanup_complete"

Lifecycle events:
    "startup_complete"    (scales_client, virtual_rig_state, session_info: dict, mouse_params, clock, tracker_definitions)
    "startup_error"       (message: str)
    "startup_cancelled"   ()
    "protocol_complete"   (final_status: ProtocolStatus)
    "finalize_complete"   (result: SessionResult)
    "cleanup_complete"    ()

Streaming events (fire repeatedly during a phase):
    "status_changed"      (status: SessionStatus)
    "startup_status"      (message: str)
    "protocol_log"        (message: str)
    "performance_update"  (trackers: dict[str, Tracker], updated: str)
    "stimulus"            (port: int)
    "cleanup_log"         (message: str)
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable

import serial
from BehavLink import BehaviourRigLink, reset_arduino_via_dtr
from BehavLink import SimulatedRig, VirtualRigState
from simulation import BehaviourClock
from BehavLink.mock import MockSerial, mock_reset_arduino_via_dtr

from .tracker import Tracker, TrackerDefinition, save_merged_trials
from .peripheral_manager import PeripheralManager, load_peripheral_config
from .protocol_base import BaseProtocol, ProtocolStatus
from .session_state import SessionStatus, SessionConfig, SessionResult

logger = logging.getLogger(__name__)


class SessionController:
    """
    Manages the session lifecycle: startup, protocol execution, cleanup.

    No tkinter dependency — communicates purely through named events.
    The GUI layer subscribes via .on() and marshals to the main thread.
    """

    def __init__(
        self,
        rig_config: dict,
        serial_port: str,
        baud_rate: int,
        simulate: bool = False,
    ):
        self._rig_config = rig_config
        self._serial_port = serial_port
        self._baud_rate = baud_rate
        self._simulate = simulate

        self._listeners: dict[str, list[Callable]] = {}

        # Session phase
        self._status = SessionStatus.IDLE

        # Hardware resources
        self._serial: serial.Serial | None = None
        self._link: BehaviourRigLink | None = None
        self._peripheral_manager: PeripheralManager | None = None
        self._current_protocol: BaseProtocol | None = None
        self._trackers: dict[str, Tracker] = {}
        self._tracker_definitions: list = []
        self._virtual_rig_state: VirtualRigState | None = None

        # Session metadata
        self._session_protocol_name: str = ""
        self._session_mouse_id: str = ""
        self._session_save_path: str = ""

        # Threads
        self._startup_thread: threading.Thread | None = None
        self._protocol_thread: threading.Thread | None = None
        self._startup_cancelled = False

    @property
    def _rig_label(self) -> str:
        """Short label for log messages, e.g. '[Rig 1]' or '[Rig 1 / mouse_001]'."""
        name = self._rig_config.name if self._rig_config else "Rig"
        if self._session_mouse_id:
            return f"[{name} / {self._session_mouse_id}]"
        return f"[{name}]"

    # =========================================================================
    # Event pattern
    # =========================================================================

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a callback for a named event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def _emit(self, event_name: str, **kwargs) -> None:
        """Fire an event to registered listeners.

        Events that carry a ``message`` kwarg are also written to the
        infrastructure logger so they appear in the log file and stderr.
        The rig name is prepended for multi-rig clarity.
        """
        # Log message-bearing events to the infrastructure logger
        message = kwargs.get("message")
        if message is not None:
            _LOGGED_EVENTS = {
                "startup_status", "protocol_log", "cleanup_log",
                "startup_error",
            }
            if event_name in _LOGGED_EVENTS:
                logger.info(f"{self._rig_label} {message}")

        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception as e:
                logger.warning(f"listener error in '{event_name}': {e}")

    # =========================================================================
    # Phase management
    # =========================================================================

    def _set_status(self, status: SessionStatus) -> None:
        self._status = status
        self._emit("status_changed", status=status)

    @property
    def status(self) -> SessionStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status in (
            SessionStatus.STARTING,
            SessionStatus.RUNNING,
            SessionStatus.STOPPING,
            SessionStatus.CLEANING_UP,
        )

    @property
    def virtual_rig_state(self) -> VirtualRigState | None:
        return self._virtual_rig_state

    # =========================================================================
    # Public API (called by RigWindow)
    # =========================================================================

    def start_session(self, session_config: dict) -> None:
        """Start a new session. Called by the GUI with validated config."""
        self._session_mouse_id = session_config["mouse_id"]
        self._session_protocol_name = session_config["protocol_class"].get_name()
        self._startup_cancelled = False

        self._set_status(SessionStatus.STARTING)

        self._startup_thread = threading.Thread(
            target=self._startup_sequence,
            args=(session_config,),
            daemon=True,
        )
        self._startup_thread.start()

    def cancel_startup(self) -> None:
        """Cancel an in-progress startup sequence."""
        self._startup_cancelled = True
        self._emit("startup_status", message="Cancelling...")

    def stop_session(self) -> None:
        """Request the running protocol to stop."""
        if self._current_protocol is not None:
            self._set_status(SessionStatus.STOPPING)
            self._current_protocol.request_stop()

    def new_session(self) -> None:
        """Reset state for a new session."""
        self._set_status(SessionStatus.IDLE)

    def close(self) -> None:
        """Clean up all resources (window closing)."""
        self.cleanup_session()

    # =========================================================================
    # Startup sequence (runs on background thread)
    # =========================================================================

    def _startup_sequence(self, config: dict) -> None:
        """Run the full startup sequence in a background thread."""
        try:
            self._emit("startup_status", message="Creating peripheral config...")

            if self._startup_cancelled:
                self._on_startup_cancelled()
                return

            # Check for shared multi-session folder from linked rig launch
            shared_multi_session = self._rig_config.shared_multi_session if self._rig_config else ""

            peripheral_config = load_peripheral_config(
                self._rig_config,
                mouse_id=config["mouse_id"],
                save_directory=config["save_directory"],
                shared_multi_session=shared_multi_session,
            )

            self._session_save_path = peripheral_config.session_folder
            self._emit("startup_status", message=f"Session folder: {peripheral_config.session_folder}")

            # Create BehaviourClock for accelerated simulation (only when mouse enabled)
            mouse_params = config.get("mouse_params")
            clock = None
            if mouse_params and mouse_params.get("mouse_enabled", False):
                speed = mouse_params.get("sim_speed", 1.0)
                if speed > 1.0:
                    clock = BehaviourClock(speed=speed)

            # Create VirtualRigState for interactive simulation
            if self._simulate:
                self._virtual_rig_state = VirtualRigState(clock=clock)

            self._peripheral_manager = PeripheralManager(
                peripheral_config,
                simulate=self._simulate,
                virtual_rig_state=self._virtual_rig_state,
            )
            self._peripheral_manager.on(
                "log", lambda message: self._emit("startup_status", message=message)
            )

            # Start DAQ
            self._emit("startup_status", message="Starting DAQ...")
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return

            if not self._peripheral_manager.start_daq():
                error_msg = self._peripheral_manager.last_error or "Failed to start DAQ"
                self._emit("startup_error", message=error_msg)
                return

            # Wait for connection
            self._emit("startup_status", message="Waiting for DAQ connection...")
            if not self._peripheral_manager.wait_for_daq_connection():
                if self._startup_cancelled:
                    self._on_startup_cancelled()
                else:
                    error_msg = self._peripheral_manager.last_error or "Connection timed out"
                    self._emit("startup_error", message=error_msg)
                return

            if self._startup_cancelled:
                self._on_startup_cancelled()
                return

            # Start camera
            self._emit("startup_status", message="Starting camera...")
            if not self._peripheral_manager.start_camera():
                error_msg = self._peripheral_manager.last_error or "Failed to start camera"
                self._emit("startup_error", message=error_msg)
                return

            if self._startup_cancelled:
                self._on_startup_cancelled()
                return

            # Start scales
            self._emit("startup_status", message="Starting scales...")
            if not self._peripheral_manager.start_scales():
                error_msg = self._peripheral_manager.last_error or "Failed to start scales"
                self._emit("startup_error", message=error_msg)
                return

            if self._startup_cancelled:
                self._on_startup_cancelled()
                return

            # Connect to rig
            self._emit("startup_status", message="Connecting to behaviour rig...")
            if self._simulate:
                self._serial = MockSerial()
            else:
                self._serial = serial.Serial(self._serial_port, self._baud_rate, timeout=0.1)

            self._emit("startup_status", message="Resetting Arduino...")
            if self._simulate:
                mock_reset_arduino_via_dtr(self._serial)
            else:
                reset_arduino_via_dtr(self._serial)

            self._emit("startup_status", message="Creating BehaviourRigLink...")
            board_type = self._rig_config.board_type if self._rig_config else "giga"
            if self._simulate:
                self._link = SimulatedRig(self._serial, self._virtual_rig_state, clock=clock)
            else:
                self._link = BehaviourRigLink(self._serial, board_type=board_type)
            self._link.start()

            self._emit("startup_status", message="Handshaking...")
            self._link.send_hello()
            self._link.wait_hello(timeout=5.0)

            if self._startup_cancelled:
                self._on_startup_cancelled()
                return

            self._peripheral_manager.is_started = True

            # Persist session metadata
            self._emit("startup_status", message="Writing session metadata...")
            self._write_session_metadata(config, peripheral_config)

            # Extract rig number
            rig_number = self._rig_config.rig_number if self._rig_config else 1

            # Create protocol
            self._emit("startup_status", message="Creating protocol...")
            self._current_protocol = config["protocol_class"](
                parameters=config["parameters"],
                link=self._link,
            )

            # Build trackers via the protocol so the protocol owns construction.
            # self._trackers is stage-keyed (protocol looks up by stage name).
            # self._trackers_by_name is tracker-name-keyed (GUI looks up by name).
            tracker_defs = config["protocol_class"].get_tracker_definitions()
            self._tracker_definitions = tracker_defs
            self._trackers = self._current_protocol.build_trackers(clock=clock)

            # Build a name-keyed dict of unique trackers for the GUI.
            self._trackers_by_name: dict[str, Tracker] = {}
            wired: set[int] = set()
            for tracker in self._trackers.values():
                tid = id(tracker)
                if tid in wired:
                    continue
                wired.add(tid)
                self._trackers_by_name[tracker.name] = tracker
                _name = tracker.name
                tracker.on(
                    "update",
                    lambda tracker=None, sub=None, _n=_name: self._emit(
                        "performance_update",
                        trackers=self._trackers_by_name,
                        updated=_n,
                    ),
                )
                tracker.on(
                    "stimulus",
                    lambda tracker=None, port=None, modality=None, t_offset=None, details=None:
                        self._emit("stimulus", port=port),
                )

            scales_client = None
            if self._peripheral_manager.scales_client is not None:
                scales_client = self._peripheral_manager.scales_client

            # Read per-port reward durations from rig config
            reward_durations = list(self._rig_config.reward_durations) if self._rig_config else [500] * 6

            self._current_protocol.set_runtime_context(
                scales=scales_client,
                trackers=self._trackers,
                rig_number=rig_number,
                clock=clock,
                reward_durations=reward_durations,
            )

            # Wire protocol events
            self._current_protocol.on(
                "log", lambda message: self._emit("protocol_log", message=message)
            )
            self._current_protocol.on(
                "error", lambda error: self._emit("protocol_log", message=f"ERROR: {error}")
            )
            self._current_protocol.on(
                "started", lambda: self._emit("protocol_log", message="Protocol started")
            )

            self._emit("startup_status", message="Startup complete!")

            # Compute scales threshold if mouse_weight is available
            params = config.get("parameters", {})
            scales_threshold = None
            if "mouse_weight" in params:
                try:
                    weight_offset = float(params.get("weight_offset", 3.0))
                    scales_threshold = float(params["mouse_weight"]) - weight_offset
                except (TypeError, ValueError) as e:
                    logger.warning(f"could not compute scales threshold: {e}")

            # Build session info for the GUI
            session_info = {
                "protocol_name": self._session_protocol_name,
                "mouse_id": self._session_mouse_id,
                "save_path": self._session_save_path,
                "scales_threshold": scales_threshold,
            }

            self._emit(
                "startup_complete",
                scales_client=scales_client,
                virtual_rig_state=self._virtual_rig_state,
                session_info=session_info,
                mouse_params=mouse_params,
                clock=clock,
                tracker_definitions=tracker_defs,
            )

        except Exception as e:
            import traceback
            self._emit("startup_status", message=f"EXCEPTION: {e}")
            self._emit("startup_status", message=traceback.format_exc())
            self._emit("startup_error", message=str(e))

    def _on_startup_cancelled(self) -> None:
        """Handle startup cancellation — clean up and notify."""
        self._cleanup_hardware_async()
        self._set_status(SessionStatus.IDLE)
        self._emit("startup_cancelled")

    # =========================================================================
    # Protocol execution
    # =========================================================================

    def run_protocol(self) -> None:
        """Public entry: spawn protocol worker, return immediately."""
        self._set_status(SessionStatus.RUNNING)
        self._protocol_thread = threading.Thread(
            target=self._protocol_worker, daemon=True
        )
        self._protocol_thread.start()

    def _protocol_worker(self) -> None:
        """Run the protocol, emit protocol_complete, exit."""
        try:
            if self._current_protocol:
                self._current_protocol.run()
        except Exception as e:
            self._emit("protocol_log", message=f"ERROR: {e}")

        final_status = ProtocolStatus.COMPLETED
        if self._current_protocol is not None:
            final_status = self._current_protocol.status

        self._emit("protocol_complete", final_status=final_status)

    # =========================================================================
    # Finalize phase
    # =========================================================================

    def finalize_protocol(self, final_status) -> None:
        """Public entry: spawn finalize worker, return immediately."""
        self._set_status(SessionStatus.CLEANING_UP)
        threading.Thread(
            target=self._finalize_worker,
            args=(final_status,),
            daemon=True,
        ).start()

    def _finalize_worker(self, final_status) -> None:
        """Build SessionResult, save trial data, emit finalize_complete, exit."""
        status_map = {
            ProtocolStatus.COMPLETED: "Completed",
            ProtocolStatus.STOPPED: "Stopped",
            ProtocolStatus.ERROR: "Error",
        }
        status_str = status_map.get(final_status, "Unknown")

        # Get performance reports (raw trial data) and save merged trial data.
        # Use _trackers_by_name (unique trackers keyed by tracker.name) to
        # avoid duplicating reports when multiple stages share a tracker.
        trackers_by_name = getattr(self, "_trackers_by_name", {})
        performance_reports: dict[str, dict] | None = None
        if trackers_by_name:
            performance_reports = {}
            for name, tracker in trackers_by_name.items():
                all_trials = tracker.get_all_trials()
                start_ts, last_ts = tracker.get_time_span()

                performance_reports[name] = {
                    "trials": [
                        {
                            "time_since_start": t.time_since_start,
                            "outcome": t.outcome.value,
                            "correct_port": t.correct_port,
                            "chosen_port": t.chosen_port,
                            "trial_duration": t.trial_duration,
                            "trial_type": t.trial_type,
                            "stimuli": list(t.stimuli),
                        }
                        for t in all_trials
                    ],
                    "session_duration": (
                        (last_ts - start_ts) if start_ts and last_ts else 0.0
                    ),
                    "sub_trackers": tracker.sub_tracker_names,
                    "is_simple": tracker.is_simple,
                }

            # Save merged trial data to file
            if self._session_save_path:
                try:
                    session_id = Path(self._session_save_path).name
                    saved_path = save_merged_trials(
                        trackers_by_name,
                        self._session_save_path,
                        session_id=session_id,
                    )
                    if saved_path:
                        self._emit("protocol_log", message=f"Trial data saved: {saved_path.name}")
                except Exception as e:
                    self._emit("protocol_log", message=f"Failed to save trial data: {e}")

        result = SessionResult(
            status=status_str,
            protocol_name=self._session_protocol_name,
            mouse_id=self._session_mouse_id,
            elapsed_time=0.0,  # GUI owns the timer, will be filled by RigWindow
            save_path=self._session_save_path,
            performance_reports=performance_reports,
        )

        self._emit("finalize_complete", result=result)

    # =========================================================================
    # Cleanup phase
    # =========================================================================

    def cleanup_session(self) -> None:
        """Public entry: spawn cleanup worker, return immediately."""
        self._current_protocol = None
        self._protocol_thread = None
        self._virtual_rig_state = None

        # Capture hardware references, then clear
        link = self._link
        ser = self._serial
        pm = self._peripheral_manager
        self._link = None
        self._serial = None
        self._peripheral_manager = None

        if link or ser or pm:
            # Re-wire peripheral manager logs to cleanup_log during cleanup
            if pm is not None:
                pm.on("log", lambda message: self._emit("cleanup_log", message=message))

            def _cleanup_worker():
                self._cleanup_hardware_blocking(pm, ser, link)
                self._emit("cleanup_complete")

            threading.Thread(target=_cleanup_worker, daemon=True).start()
        else:
            self._emit("cleanup_complete")

    def _cleanup_hardware_async(self) -> None:
        """Quick async cleanup for cancellation/error paths."""
        pm = self._peripheral_manager
        ser = self._serial
        link = self._link
        self._peripheral_manager = None
        self._serial = None
        self._link = None

        if pm or ser or link:
            threading.Thread(
                target=self._cleanup_hardware_blocking,
                args=(pm, ser, link),
                daemon=True,
            ).start()

    def _cleanup_hardware_blocking(self, pm, ser, link) -> None:
        """
        Blocking hardware cleanup — runs on a background thread.

        Shuts down the BehaviourRigLink, closes the serial port, and stops
        peripheral processes.
        """
        if link is not None:
            try:
                self._emit("cleanup_log", message="Shutting down rig link...")
                link.shutdown()
            except Exception as e:
                logger.warning(f"error shutting down rig link: {e}")
            try:
                link.stop()
            except Exception as e:
                logger.warning(f"error stopping rig link: {e}")

        if ser is not None:
            try:
                ser.close()
            except Exception as e:
                logger.warning(f"error closing serial port: {e}")

        if pm is not None:
            try:
                pm.stop()
            except Exception as e:
                logger.warning(f"error stopping peripherals: {e}")

    # =========================================================================
    # Metadata
    # =========================================================================

    def _write_session_metadata(self, session_config: dict, peripheral_config) -> None:
        """Save session setup details to a metadata JSON in the session folder."""
        try:
            multi_session_folder = Path(peripheral_config.multi_session_folder)
            multi_session_folder.mkdir(parents=True, exist_ok=True)

            session_folder = Path(peripheral_config.session_folder)
            session_folder.mkdir(parents=True, exist_ok=True)
            session_id = session_folder.name

            metadata_path = session_folder / f"{session_id}-metadata.json"

            protocol_params = session_config.get("parameters", {})
            if "phase" not in protocol_params:
                protocol_params["phase"] = "0"

            mouse_weight = protocol_params.get("mouse_weight")
            num_trials = protocol_params.get("num_trials")

            metadata = {
                "session_id": session_id,
                "mouse_id": session_config.get("mouse_id", ""),
                "mouse_weight": mouse_weight,
                "num_trials": num_trials,
                "protocol_name": session_config.get("protocol_name", ""),
                "protocol_parameters": protocol_params,
                "save_directory": session_config.get("save_directory", ""),
                "multi_session_folder": str(multi_session_folder),
                "session_folder": str(session_folder),
                "start_timestamp": peripheral_config.date_time,
                "rig": {
                    "name": peripheral_config.rig_name,
                    "number": peripheral_config.rig_number,
                    "camera_serial": peripheral_config.camera_serial,
                },
                "peripherals": {
                    "camera_fps": peripheral_config.camera_fps,
                    "camera_window": {
                        "width": peripheral_config.camera_window_width,
                        "height": peripheral_config.camera_window_height,
                    },
                    "scales_enabled": peripheral_config.scales is not None,
                },
            }

            def _json_default(obj):
                """Fallback serialiser for Path, Enum, and other non-JSON types."""
                if isinstance(obj, Path):
                    return str(obj)
                if hasattr(obj, "value"):  # Enum-like
                    return obj.value
                return str(obj)

            with metadata_path.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, default=_json_default)

            self._emit("startup_status", message=f"Metadata saved: {metadata_path.name}")
        except Exception as e:
            self._emit("startup_status", message=f"Failed to write metadata: {e}")
