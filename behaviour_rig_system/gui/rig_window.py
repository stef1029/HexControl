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
from tkinter import messagebox, scrolledtext, ttk
from typing import Optional

import serial
from BehavLink import BehaviourRigLink, reset_arduino_via_dtr
from BehavLink.mock import MockBehaviourRigLink, MockSerial, mock_reset_arduino_via_dtr

from core.peripheral_manager import PeripheralManager, load_peripheral_config
from core.performance_tracker import PerformanceTracker
from core.protocol_base import BaseProtocol, ProtocolEvent, ProtocolStatus

from .modes import SetupMode, RunningMode, PostSessionMode
from .theme import apply_theme, Theme, style_scrolled_text


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
        parent: Optional[tk.Tk] = None,
        rig_name: str = "",
        rig_config: Optional[dict] = None,
        simulate: bool = False,
    ):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.parent = parent
        self.rig_name = rig_name
        self.rig_config = rig_config or {"name": rig_name}
        self._simulate = simulate
        
        # Hardware/protocol state
        self._serial: Optional[serial.Serial] = None
        self.link: Optional[BehaviourRigLink] = None
        self.current_protocol: Optional[BaseProtocol] = None
        self.protocol_thread: Optional[threading.Thread] = None
        self.peripheral_manager: Optional[PeripheralManager] = None
        self.startup_thread: Optional[threading.Thread] = None
        
        # Session info for summary
        self._session_protocol_name: str = ""
        self._session_mouse_id: str = ""
        self._session_save_path: str = ""
        
        self._current_mode = WindowMode.SETUP
        self._startup_cancelled = False
        
        # Pending startup data
        self._pending_session_config: Optional[dict] = None
        
        self._setup_window()
        self._create_modes()
        self._create_startup_overlay()
        self._show_mode(WindowMode.SETUP)
    
    # =========================================================================
    # Window Setup
    # =========================================================================
    
    def _setup_window(self) -> None:
        """Configure the main window."""
        if self.parent is not None:
            self.root = self.parent
        else:
            self.root = tk.Tk()
        
        # Apply modern theme
        apply_theme(self.root)
        
        title = f"Behaviour Rig - {self.rig_name}" if self.rig_name else "Behaviour Rig System"
        self.root.title(title)
        self.root.geometry("680x680")
        self.root.minsize(580, 480)
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
        palette = Theme.palette
        
        self.startup_frame = ttk.Frame(self.root)
        
        inner_frame = ttk.Frame(self.startup_frame, padding=(18, 12))
        inner_frame.pack(fill="both", expand=True)
        
        self.startup_title = ttk.Label(
            inner_frame, text="Starting Session...",
            style="Heading.TLabel"
        )
        self.startup_title.pack(pady=(6, 3))
        
        self.startup_status_var = tk.StringVar(value="Initializing...")
        self.startup_status = ttk.Label(
            inner_frame, textvariable=self.startup_status_var,
            foreground=palette.accent_primary,
            font=Theme.font(size=10)
        )
        self.startup_status.pack(pady=3)
        
        self.startup_progress = ttk.Progressbar(
            inner_frame, mode="indeterminate", length=400
        )
        self.startup_progress.pack(pady=10)
        
        log_label = ttk.Label(inner_frame, text="Startup Log:", style="Subheading.TLabel")
        log_label.pack(anchor="w", pady=(6, 3))
        
        self.startup_log = scrolledtext.ScrolledText(
            inner_frame, height=14, width=70,
            state="disabled", wrap="word"
        )
        style_scrolled_text(self.startup_log, log_style=True)
        self.startup_log.pack(fill="both", expand=True, pady=3)
        
        self.startup_cancel_btn = ttk.Button(
            inner_frame, text="Cancel",
            command=self._cancel_startup,
            style="Danger.TButton"
        )
        self.startup_cancel_btn.pack(pady=10)
    
    # =========================================================================
    # Mode Management
    # =========================================================================
    
    def _show_mode(self, mode: WindowMode) -> None:
        """Switch to the specified mode."""
        # Hide all frames
        self.setup_mode.pack_forget()
        self.running_mode.pack_forget()
        self.post_session_mode.pack_forget()
        self.startup_frame.pack_forget()
        
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
    
    def _show_startup_overlay(self) -> None:
        """Show the startup overlay."""
        self._startup_cancelled = False
        self.startup_log.config(state="normal")
        self.startup_log.delete("1.0", tk.END)
        self.startup_log.config(state="disabled")
        self.startup_status_var.set("Initializing...")
        
        self.setup_mode.pack_forget()
        self.startup_frame.pack(fill="both", expand=True)
        self.startup_progress.start(10)
    
    def _hide_startup_overlay(self) -> None:
        """Hide the startup overlay."""
        self.startup_progress.stop()
        self.startup_frame.pack_forget()
    
    def _update_startup_status(self, message: str) -> None:
        """Update startup status (thread-safe)."""
        self.root.after(0, lambda: self._do_update_startup_status(message))
    
    def _do_update_startup_status(self, message: str) -> None:
        """Actually update the startup status."""
        short_msg = message.split("]", 1)[-1].strip() if "]" in message else message
        self.startup_status_var.set(short_msg[:60] + "..." if len(short_msg) > 60 else short_msg)
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] {message}\n"
        
        self.startup_log.config(state="normal")
        self.startup_log.insert(tk.END, log_line)
        self.startup_log.see(tk.END)
        self.startup_log.config(state="disabled")
    
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
        self._show_startup_overlay()
        
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
            
            self.peripheral_manager = PeripheralManager(
                peripheral_config,
                log_callback=self._update_startup_status,
                simulate=self._simulate,
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
                self.link = MockBehaviourRigLink(self._serial)
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
        self._hide_startup_overlay()
        
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
        # Clean up peripherals in the background
        if self.peripheral_manager:
            self.peripheral_manager.stop()
            self.peripheral_manager = None
        
        if self._serial:
            try:
                self._serial.close()
            except:
                pass
            self._serial = None
        
        self.link = None

        # Stop the progress bar and update the overlay to show the error
        self.startup_progress.stop()
        self.startup_title.config(text="Startup Failed", foreground="red")
        self.startup_status_var.set(error_msg[:80])

        # Log the error into the overlay's scrolled text
        self._do_update_startup_status(f"ERROR: {error_msg}")

        # Change the Cancel button to a Close button that returns to setup
        self.startup_cancel_btn.config(
            text="Close",
            command=self._close_startup_error,
        )
    
    def _close_startup_error(self) -> None:
        """Close the startup error overlay and return to setup mode."""
        # Reset overlay state for next attempt
        self.startup_title.config(text="Starting Session...", foreground="")
        self.startup_cancel_btn.config(text="Cancel", command=self._cancel_startup)
        self._hide_startup_overlay()
        self._show_mode(WindowMode.SETUP)
    
    def _on_startup_cancelled(self) -> None:
        """Called when startup is cancelled."""
        self.root.after(0, self._cleanup_startup_cancelled)
    
    def _cleanup_startup_cancelled(self) -> None:
        """Clean up after cancelled startup."""
        self._hide_startup_overlay()
        
        if self.peripheral_manager:
            self.peripheral_manager.stop()
            self.peripheral_manager = None
        
        if self._serial:
            try:
                self._serial.close()
            except:
                pass
            self._serial = None
        
        self.link = None
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
            self.root.after(0, lambda: self._on_protocol_error(e))
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
        
        # Clean up resources
        self._cleanup_session()
        
        # Activate post-session mode
        self.post_session_mode.activate({
            "status": status_str,
            "protocol_name": self._session_protocol_name,
            "mouse_id": self._session_mouse_id,
            "elapsed_time": elapsed,
            "save_path": self._session_save_path,
            "performance_report": performance_report,
        })
        
        # Switch to post-session mode
        self._show_mode(WindowMode.POST_SESSION)
    
    def _stop_session(self) -> None:
        """Request the current session to stop."""
        if self.current_protocol is not None:
            self.running_mode.set_stopping()
            self.running_mode.log_message("Requesting stop...")
            self.current_protocol.request_abort()
    
    def _cleanup_session(self) -> None:
        """Clean up all session resources."""
        self.current_protocol = None
        self.protocol_thread = None
        
        # Shutdown BehavLink
        if self.link is not None:
            try:
                self.link.shutdown()
            except Exception:
                pass
            try:
                self.link.stop()
            except Exception:
                pass
            self.link = None
        
        # Close serial
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        
        # Stop peripherals
        if self.peripheral_manager is not None:
            try:
                self.peripheral_manager.stop()
            except Exception:
                pass
            self.peripheral_manager = None
    
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
        """Force close the application."""
        self._cleanup_session()
        if self.parent is None:
            self.root.destroy()
    
    def run(self) -> None:
        """Start the application main loop."""
        if self.parent is None:
            self.root.mainloop()

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


def launch_rig_window(serial_port: str = "", baud_rate: int = 115200) -> None:
    """Launch the Behaviour Rig System GUI for a single rig."""
    app = RigWindow(serial_port=serial_port, baud_rate=baud_rate)
    app.run()
