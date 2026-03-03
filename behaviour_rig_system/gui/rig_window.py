"""
Rig Window - Thin orchestrator for mode management.

This is the main window for a single rig, managing transitions between:
    - SetupMode: Configure and start session
    - RunningMode: Monitor active session
    - PostSessionMode: Review completed session
"""

import json
import threading
import tkinter as tk
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from tkinter import messagebox, ttk

import serial
from BehavLink import BehaviourRigLink, reset_arduino_via_dtr
from BehavLink import SimulatedRig, VirtualRigState
from BehavLink.mock import MockSerial, mock_reset_arduino_via_dtr

from core.peripheral_manager import PeripheralManager, load_peripheral_config
from core.performance_tracker import PerformanceTracker
from core.protocol_base import BaseProtocol, ProtocolEvent, ProtocolStatus

from .modes import SetupMode, RunningMode, PostSessionMode
from .startup_overlay import StartupOverlay
from .theme import apply_theme, Theme
from .virtual_rig_window import VirtualRigWindow


class WindowMode(Enum):
    """The three modes of the rig window."""
    SETUP = auto()
    RUNNING = auto()
    POST_SESSION = auto()


class RigWindow:
    """
    Main window for a single behaviour rig.
    
    Manages mode transitions and coordinates session lifecycle.
    """
    
    def __init__(
        self,
        serial_port: str = "",
        baud_rate: int = 115200,
        parent: tk.Toplevel = None,
        rig_config: dict | None = None,
        simulate: bool = False,
    ):
        if parent is None:
            raise ValueError("RigWindow requires a parent window")

        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.parent = parent
        self.rig_config = rig_config
        self._simulate = simulate
        
        # Hardware/protocol state
        self._serial: serial.Serial | None = None
        self.link: BehaviourRigLink | None = None
        self.current_protocol: BaseProtocol | None = None
        self.protocol_thread: threading.Thread | None = None
        self.peripheral_manager: PeripheralManager | None = None
        self.startup_thread: threading.Thread | None = None
        
        # Virtual rig (simulate mode only)
        self._virtual_rig_state: VirtualRigState | None = None
        self._virtual_rig_window: VirtualRigWindow | None = None
        
        # Session info for summary
        self._session_protocol_name: str = ""
        self._session_mouse_id: str = ""
        self._session_save_path: str = ""
        
        self._current_mode = WindowMode.SETUP
        self._startup_cancelled = False
        
        # Pending startup data
        self._pending_session_config: dict | None = None
        
        self._setup_window()
        self._create_modes()
        self._create_startup_overlay()
        self._show_mode(WindowMode.SETUP)
    
    # =========================================================================
    # Window Setup
    # =========================================================================
    
    def _setup_window(self) -> None:
        """Configure the main window."""
        self.root = self.parent
        
        # Apply modern theme
        apply_theme(self.root)

        self.rig_name = self.rig_config.get("name", "Unknown")
        
        title = f"Behaviour Rig - {self.rig_name}" if self.rig_name else "Behaviour Rig System"
        self.root.title(title)
        self.root.geometry("680x1000")
        self.root.minsize(580, 580)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_modes(self) -> None:
        """Create the three mode frames."""
        self.setup_mode = SetupMode(
            self.root,
            rig_config=self.rig_config,
            on_start=self._start_session
        )
        
        self.running_mode = RunningMode(
            self.root,
            on_stop=self._stop_session
        )
        
        self.post_session_mode = PostSessionMode(
            self.root,
            on_new_session=self._new_session
        )
    
    def _create_startup_overlay(self) -> None:
        """Create the overlay shown during startup sequence."""
        self.startup_overlay = StartupOverlay(
            self.root,
            on_cancel=self._cancel_startup,
        )
    
    # =========================================================================
    # Mode Management
    # =========================================================================
    
    def _show_mode(self, mode: WindowMode) -> None:
        """Switch to the specified mode."""
        # Deactivate running mode when leaving it (stops scales poll, timer)
        if self._current_mode == WindowMode.RUNNING and mode != WindowMode.RUNNING:
            try:
                self.running_mode.deactivate()
            except Exception:
                pass

        # Hide all frames
        self.setup_mode.pack_forget()
        self.running_mode.pack_forget()
        self.post_session_mode.pack_forget()
        self.startup_overlay.pack_forget()
        
        # Show the requested frame
        self._current_mode = mode
        if mode == WindowMode.SETUP:
            self.setup_mode.pack(fill="both", expand=True)
        elif mode == WindowMode.RUNNING:
            self.running_mode.pack(fill="both", expand=True)
        elif mode == WindowMode.POST_SESSION:
            self.post_session_mode.pack(fill="both", expand=True)
    
    # =========================================================================
    # Startup Overlay
    # =========================================================================
    
    def _update_startup_status(self, message: str) -> None:
        """Update startup status (thread-safe)."""
        self.root.after(0, lambda: self.startup_overlay.update_status(message))
    
    def _cancel_startup(self) -> None:
        """Cancel the startup sequence."""
        self._startup_cancelled = True
        self._update_startup_status("Cancelling...")
    
    # =========================================================================
    # Session Lifecycle
    # =========================================================================
    
    def _start_session(self, session_config: dict) -> None:
        """
        Start a new session.
        
        Called by SetupMode with validated config containing:
            protocol_class, parameters, mouse_id, save_directory
        """
        self._pending_session_config = session_config
        self._session_mouse_id = session_config["mouse_id"]
        self._session_protocol_name = session_config["protocol_class"].get_name()
        
        # Show startup overlay
        self._startup_cancelled = False
        self.setup_mode.pack_forget()
        self.startup_overlay.show()
        
        # Run startup in background thread
        self.startup_thread = threading.Thread(target=self._startup_sequence, daemon=True)
        self.startup_thread.start()
    
    def _startup_sequence(self) -> None:
        """Run the startup sequence in background thread."""
        config = self._pending_session_config
        if config is None:
            return
        
        try:
            self._update_startup_status("Creating peripheral config...")
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            # Check for shared multi-session folder from linked rig launch
            shared_multi_session = self.rig_config.get("shared_multi_session")
            
            peripheral_config = load_peripheral_config(
                self.rig_config,
                mouse_id=config["mouse_id"],
                save_directory=config["save_directory"],
                shared_multi_session=shared_multi_session
            )
            
            self._session_save_path = peripheral_config.session_folder
            self._update_startup_status(f"Session folder: {peripheral_config.session_folder}")
            
            # Create VirtualRigState for interactive simulation
            if self._simulate:
                self._virtual_rig_state = VirtualRigState()
            
            self.peripheral_manager = PeripheralManager(
                peripheral_config,
                log_callback=self._update_startup_status,
                simulate=self._simulate,
                virtual_rig_state=self._virtual_rig_state,
            )
            
            # Start DAQ
            self._update_startup_status("Starting DAQ...")
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            if not self.peripheral_manager.start_daq():
                error_msg = self.peripheral_manager.last_error or "Failed to start DAQ"
                self.root.after(0, lambda msg=error_msg: self._on_startup_error(msg))
                return
            
            # Wait for connection
            self._update_startup_status("Waiting for DAQ connection...")
            if not self.peripheral_manager.wait_for_daq_connection():
                if self._startup_cancelled:
                    self._on_startup_cancelled()
                else:
                    error_msg = self.peripheral_manager.last_error or "Connection timed out"
                    self.root.after(0, lambda msg=error_msg: self._on_startup_error(msg))
                return
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            # Start camera
            self._update_startup_status("Starting camera...")
            if not self.peripheral_manager.start_camera():
                error_msg = self.peripheral_manager.last_error or "Failed to start camera"
                self.root.after(0, lambda msg=error_msg: self._on_startup_error(msg))
                return
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            # Start scales (always)
            self._update_startup_status("Starting scales...")
            if not self.peripheral_manager.start_scales():
                error_msg = self.peripheral_manager.last_error or "Failed to start scales"
                self.root.after(0, lambda msg=error_msg: self._on_startup_error(msg))
                return
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            # Connect to rig
            self._update_startup_status("Connecting to behaviour rig...")
            if self._simulate:
                self._serial = MockSerial()
            else:
                self._serial = serial.Serial(self.serial_port, self.baud_rate, timeout=0.1)
            
            self._update_startup_status("Resetting Arduino...")
            if self._simulate:
                mock_reset_arduino_via_dtr(self._serial)
            else:
                reset_arduino_via_dtr(self._serial)
            
            self._update_startup_status("Creating BehaviourRigLink...")
            board_type = self.rig_config.get("board_type", "giga")
            if self._simulate:
                self.link = SimulatedRig(self._serial, self._virtual_rig_state)
            else:
                self.link = BehaviourRigLink(self._serial, board_type=board_type)
            self.link.start()
            
            self._update_startup_status("Handshaking...")
            self.link.send_hello()
            self.link.wait_hello(timeout=5.0)
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            self.peripheral_manager.is_started = True

            # Persist session metadata (parameters, selections, rig info)
            self._update_startup_status("Writing session metadata...")
            self._write_session_metadata(config, peripheral_config)
            
            # Extract rig number from rig name
            try:
                rig_number = int(self.rig_name.split()[-1])
            except (ValueError, IndexError):
                rig_number = 1
            
            # Create protocol
            self._update_startup_status("Creating protocol...")
            self.current_protocol = config["protocol_class"](
                parameters=config["parameters"],
                link=self.link,
            )
            # Set rig number so protocol can access it
            self.current_protocol.rig_number = rig_number
            
            # Pass scales client to protocol (always available)
            if self.peripheral_manager.scales_client is not None:
                self.current_protocol._scales_client = self.peripheral_manager.scales_client
            
            # Create and pass performance tracker
            self._perf_tracker = PerformanceTracker(
                on_update=lambda t: self.running_mode.update_performance(t),
                on_stimulus=lambda port: self.running_mode.log_stimulus(port),
            )
            self.current_protocol._perf_tracker = self._perf_tracker
            
            self.current_protocol.add_event_listener(self._on_protocol_event)
            
            self._update_startup_status("Startup complete!")
            self.root.after(0, self._on_startup_complete)
            
        except Exception as e:
            import traceback
            self._update_startup_status(f"EXCEPTION: {e}")
            self._update_startup_status(traceback.format_exc())
            self.root.after(0, lambda: self._on_startup_error(str(e)))
    
    def _on_startup_complete(self) -> None:
        """Called when startup completes successfully."""
        self.startup_overlay.hide()
        
        # Open virtual rig window in simulate mode
        if self._simulate and self._virtual_rig_state is not None:
            self._virtual_rig_window = VirtualRigWindow(self.root, self._virtual_rig_state)
        
        # Pass scales client to running mode for live plot
        if self.peripheral_manager and self.peripheral_manager.scales_client is not None:
            self.running_mode.set_scales_client(self.peripheral_manager.scales_client)
        
        # Activate running mode
        self.running_mode.activate({
            "protocol_name": self._session_protocol_name,
            "mouse_id": self._session_mouse_id,
            "save_path": self._session_save_path,
        })
        self.running_mode.set_status(ProtocolStatus.RUNNING)
        
        # Switch to running mode
        self._show_mode(WindowMode.RUNNING)
        
        # Start timer and protocol
        self.running_mode.start_timer()
        self.running_mode.log_message("Session started!")
        self.running_mode.log_message(f"Running {self._session_protocol_name}...")
        
        self.protocol_thread = threading.Thread(target=self._run_protocol_thread, daemon=True)
        self.protocol_thread.start()
    
    def _on_startup_error(self, error_msg: str) -> None:
        """Called when startup fails. Keeps the overlay visible so the user can read the log."""
        # Capture references for background cleanup, then clear them
        pm = self.peripheral_manager
        ser = self._serial
        link = self.link
        self.peripheral_manager = None
        self._serial = None
        self.link = None

        # Clean up peripherals in a background thread to avoid blocking the GUI
        if pm or ser or link:
            threading.Thread(
                target=self._cleanup_hardware_blocking,
                args=(pm, ser, link),
                daemon=True,
            ).start()

        # Switch overlay to error state
        self.startup_overlay.show_error(error_msg, on_close=self._close_startup_error)
    
    def _close_startup_error(self) -> None:
        """Close the startup error overlay and return to setup mode."""
        self.startup_overlay.hide()
        self._show_mode(WindowMode.SETUP)
    
    def _on_startup_cancelled(self) -> None:
        """Called when startup is cancelled."""
        self.root.after(0, self._cleanup_startup_cancelled)
    
    def _cleanup_startup_cancelled(self) -> None:
        """Clean up after cancelled startup."""
        self.startup_overlay.hide()
        
        # Capture references for background cleanup, then clear them
        pm = self.peripheral_manager
        ser = self._serial
        link = self.link
        self.peripheral_manager = None
        self._serial = None
        self.link = None
        
        if pm or ser or link:
            threading.Thread(
                target=self._cleanup_hardware_blocking,
                args=(pm, ser, link),
                daemon=True,
            ).start()
        
        self._show_mode(WindowMode.SETUP)
    
    # =========================================================================
    # Protocol Execution
    # =========================================================================
    
    def _run_protocol_thread(self) -> None:
        """Run the protocol in a background thread."""
        try:
            if self.current_protocol:
                self.current_protocol.run()
        except Exception as e:
            self.root.after(0, lambda err=e: self._on_protocol_error(err))
        finally:
            self.root.after(0, self._on_protocol_complete)
    
    def _on_protocol_event(self, event: ProtocolEvent) -> None:
        """Handle protocol events (called from protocol thread)."""
        self.root.after(0, lambda: self._handle_event(event))
    
    def _handle_event(self, event: ProtocolEvent) -> None:
        """Handle a protocol event on the main thread."""
        if self.current_protocol is not None:
            self.running_mode.set_status(self.current_protocol.status)
        self.running_mode.log_event(event)
    
    def _on_protocol_error(self, error: Exception) -> None:
        """Handle protocol errors."""
        self.running_mode.log_message(f"ERROR: {error}")
    
    def _on_protocol_complete(self) -> None:
        """Handle protocol completion - clean up then show post-session."""
        self.running_mode.stop_timer()
        self.running_mode.stop_scales_plot()
        
        # Get final status and duration before cleanup
        final_status = ProtocolStatus.COMPLETED
        if self.current_protocol is not None:
            final_status = self.current_protocol.status
            self.running_mode.set_status(final_status)
        
        elapsed = self.running_mode.get_elapsed_time()
        
        status_map = {
            ProtocolStatus.COMPLETED: "Completed",
            ProtocolStatus.ABORTED: "Stopped",
            ProtocolStatus.ERROR: "Error",
        }
        status_str = status_map.get(final_status, "Unknown")
        
        self.running_mode.log_message(f"Session {status_str.lower()}")
        self.running_mode.log_message("Cleaning up...")
        
        # Get performance report before cleanup (tracker is cleaned up with protocol)
        performance_report = None
        if hasattr(self, '_perf_tracker') and self._perf_tracker is not None:
            performance_report = self._perf_tracker.get_report()
            
            # Save trial data to file
            if self._session_save_path:
                try:
                    session_id = Path(self._session_save_path).name
                    saved_path = self._perf_tracker.save_trials_to_file(
                        self._session_save_path,
                        session_id=session_id
                    )
                    if saved_path:
                        self.running_mode.log_message(f"Trial data saved: {saved_path.name}")
                except Exception as e:
                    self.running_mode.log_message(f"Failed to save trial data: {e}")
        
        # Prepare post-session data before cleanup clears references
        post_session_data = {
            "status": status_str,
            "protocol_name": self._session_protocol_name,
            "mouse_id": self._session_mouse_id,
            "elapsed_time": elapsed,
            "save_path": self._session_save_path,
            "performance_report": performance_report,
        }
        
        # Clean up resources (non-blocking: hardware shutdown on background thread)
        self._cleanup_session(on_done=lambda: self._finish_post_session(post_session_data))
    
    def _finish_post_session(self, post_session_data: dict) -> None:
        """Called (on main thread) after hardware cleanup completes."""
        self.post_session_mode.activate(post_session_data)
        self._show_mode(WindowMode.POST_SESSION)
    
    def _stop_session(self) -> None:
        """Request the current session to stop."""
        if self.current_protocol is not None:
            self.running_mode.set_stopping()
            self.running_mode.log_message("Requesting stop...")
            self.current_protocol.request_abort()
    
    def _cleanup_session(self, on_done=None) -> None:
        """
        Clean up all session resources.
        
        Quick GUI cleanup (virtual rig window) happens immediately on the
        main thread.  Slow hardware shutdown (peripheral stop, serial close,
        link shutdown) is offloaded to a background thread so the GUI stays
        responsive.
        
        Args:
            on_done: Optional callback to invoke on the main thread once
                     hardware cleanup finishes.
        """
        self.current_protocol = None
        self.protocol_thread = None
        
        # Close virtual rig window (GUI-only, fast)
        if self._virtual_rig_window is not None:
            self._virtual_rig_window.close()
            self._virtual_rig_window = None
        self._virtual_rig_state = None
        
        # Capture hardware references, then clear them so no other code
        # touches them while the background thread is shutting them down.
        link = self.link
        ser = self._serial
        pm = self.peripheral_manager
        self.link = None
        self._serial = None
        self.peripheral_manager = None
        
        # Helper to log both to console and (thread-safe) the running mode log
        def _log_cleanup(msg: str) -> None:
            print(f"[cleanup] {msg}")
            try:
                self.root.after(0, lambda m=msg: self.running_mode.log_message(m))
            except Exception:
                pass

        if link or ser or pm:
            def _bg_cleanup():
                self._cleanup_hardware_blocking(pm, ser, link, _log_cleanup)
                if on_done is not None:
                    self.root.after(0, on_done)
            
            threading.Thread(target=_bg_cleanup, daemon=True).start()
        elif on_done is not None:
            on_done()
    
    @staticmethod
    def _cleanup_hardware_blocking(pm, ser, link, log=None) -> None:
        """
        Blocking hardware cleanup — runs on a background thread.
        
        Shuts down the BehaviourRigLink, closes the serial port, and stops
        peripheral processes.  Each step may block for several seconds
        (e.g. waiting for a subprocess to exit).
        """
        import time as _time

        def _log(msg: str) -> None:
            if log is not None:
                log(msg)
            else:
                print(f"[cleanup] {msg}")

        _log("Starting hardware cleanup...")

        if link is not None:
            # Only send shutdown if the receive thread is still alive
            # (protocol cleanup already calls link.shutdown(), which resets
            # the Arduino — a second call would just produce a write error)
            thread_alive = (
                hasattr(link, '_receive_thread')
                and link._receive_thread is not None
                and link._receive_thread.is_alive()
            )
            if thread_alive:
                try:
                    _log("Sending shutdown command to rig...")
                    link.shutdown()
                    _log("Shutdown command sent")
                except Exception as e:
                    _log(f"Link shutdown error (non-fatal): {e}")
            else:
                _log("Rig already shut down by protocol cleanup, skipping")
            try:
                _log("Stopping link receive thread...")
                link.stop()
                _log("Link receive thread stopped")
            except Exception as e:
                _log(f"Link stop error (non-fatal): {e}")
        
        if ser is not None:
            try:
                _log("Closing serial port...")
                ser.close()
                _log("Serial port closed")
            except Exception as e:
                _log(f"Serial close error (non-fatal): {e}")
        
        if pm is not None:
            try:
                _log("Stopping peripherals (camera, DAQ, scales)...")
                t0 = _time.perf_counter()
                pm.stop()
                elapsed = _time.perf_counter() - t0
                _log(f"Peripherals stopped ({elapsed:.1f}s)")
            except Exception as e:
                _log(f"Peripheral stop error (non-fatal): {e}")

        _log("Hardware cleanup complete")
    
    def _new_session(self) -> None:
        """Start a new session - return to setup mode."""
        self._show_mode(WindowMode.SETUP)
    
    # =========================================================================
    # Window Management
    # =========================================================================
    
    def _on_close(self) -> None:
        """Handle window close event."""
        if self.current_protocol is not None and self.current_protocol.is_running:
            messagebox.showwarning(
                "Session Running",
                "A session is currently running.\n\nPlease stop the session before closing the window."
            )
            return
        
        self._force_close()
    
    def _force_close(self) -> None:
        """Force close the rig window."""
        self._cleanup_session()

    # =========================================================================
    # Metadata
    # =========================================================================

    def _write_session_metadata(self, session_config: dict, peripheral_config) -> None:
        """Save session setup details to a metadata JSON in the session folder."""
        try:
            # Create multi-session folder first (parent folder with just datetime)
            multi_session_folder = Path(peripheral_config.multi_session_folder)
            multi_session_folder.mkdir(parents=True, exist_ok=True)
            
            # Create individual session folder inside multi-session folder
            session_folder = Path(peripheral_config.session_folder)
            session_folder.mkdir(parents=True, exist_ok=True)
            session_id = session_folder.name

            metadata_path = session_folder / f"{session_id}-metadata.json"

            # Ensure protocol_parameters has required values
            protocol_params = session_config.get("parameters", {})
            if "phase" not in protocol_params:
                protocol_params["phase"] = "0"
            
            # Extract session-level values for top-level metadata
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
                    "scales_enabled": bool(peripheral_config.scales and peripheral_config.scales.enabled),
                },
            }

            with metadata_path.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            self._update_startup_status(f"Metadata saved: {metadata_path.name}")
        except Exception as e:
            self._update_startup_status(f"Failed to write metadata: {e}")

