"""
Main Window for Behaviour Rig System.

This module provides the main application window that allows users to:
    - Select and configure behaviour protocols
    - Start and stop protocol execution
    - Monitor protocol status and events in real-time

The window is organised with a tabbed interface where each protocol
has its own tab containing its parameter configuration form.
"""

import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Optional

import serial
from BehavLink import BehaviourRigLink, reset_arduino_via_dtr

from core.parameter_types import convert_parameters
from core.protocol_base import BaseProtocol, ProtocolEvent, ProtocolStatus
from core.session import SessionManager, SessionConfig, load_session_config
from protocols import get_available_protocols

from .parameter_widget import ParameterFormBuilder


class StatusPanel(ttk.Frame):
    """
    Panel displaying protocol execution status and event log.

    Shows:
        - Current protocol status
        - Start/stop buttons
        - Real-time event log

    Attributes:
        on_start: Callback invoked when start button is clicked.
        on_stop: Callback invoked when stop button is clicked.
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialise the status panel.

        Args:
            parent: Parent tkinter widget.
        """
        super().__init__(parent)

        self.on_start: Callable[[], None] | None = None
        self.on_stop: Callable[[], None] | None = None

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create the panel widgets."""
        # Status display
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(status_frame, text="Status:").pack(side="left")
        self.status_label = ttk.Label(
            status_frame,
            text="IDLE",
            font=("TkDefaultFont", 10, "bold"),
            foreground="gray",
        )
        self.status_label.pack(side="left", padx=10)

        # Elapsed time
        ttk.Label(status_frame, text="Elapsed:").pack(side="left", padx=(20, 0))
        self.elapsed_label = ttk.Label(
            status_frame, text="00:00", font=("TkDefaultFont", 10)
        )
        self.elapsed_label.pack(side="left", padx=5)

        # Control buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=5)

        self.start_button = ttk.Button(
            button_frame,
            text="Start Protocol",
            command=self._on_start_clicked,
        )
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop",
            command=self._on_stop_clicked,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=5)

        self.clear_log_button = ttk.Button(
            button_frame,
            text="Clear Log",
            command=self._clear_log,
        )
        self.clear_log_button.pack(side="right", padx=5)

        # Event log
        log_frame = ttk.LabelFrame(self, text="Event Log", padding=(5, 5))
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            width=60,
            font=("Consolas", 9),
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        if self.on_start is not None:
            self.on_start()

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self.on_stop is not None:
            self.on_stop()

    def _clear_log(self) -> None:
        """Clear the event log."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def set_status(self, status: ProtocolStatus) -> None:
        """Update the displayed status."""
        status_colors = {
            ProtocolStatus.IDLE: "gray",
            ProtocolStatus.RUNNING: "green",
            ProtocolStatus.COMPLETED: "darkgreen",
            ProtocolStatus.ABORTED: "darkorange",
            ProtocolStatus.ERROR: "red",
        }

        self.status_label.config(
            text=status.name,
            foreground=status_colors.get(status, "black"),
        )

    def set_elapsed_time(self, seconds: float) -> None:
        """
        Update the elapsed time display.

        Args:
            seconds: Elapsed time in seconds.
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        self.elapsed_label.config(text=f"{minutes:02d}:{secs:02d}")

    def log_event(self, event: ProtocolEvent) -> None:
        """
        Add an event to the log.

        Args:
            event: The protocol event to log.
        """
        timestamp = event.timestamp.strftime("%H:%M:%S")
        message = event.data.get("message", event.event_type)

        log_line = f"[{timestamp}] {message}\n"

        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, log_line)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def log_message(self, message: str) -> None:
        """
        Add a simple message to the log.

        Args:
            message: The message to log.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"

        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, log_line)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def set_running_state(self, is_running: bool) -> None:
        """
        Update button states based on whether a protocol is running.

        Args:
            is_running: True if a protocol is currently running.
        """
        if is_running:
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
        else:
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")


class ProtocolTab(ttk.Frame):
    """
    Tab content for a single protocol.

    Contains the protocol description and parameter form.

    Attributes:
        protocol_class: The protocol class this tab configures.
        form_builder: The parameter form builder.
    """

    def __init__(self, parent: tk.Widget, protocol_class: type[BaseProtocol]):
        """
        Initialise the protocol tab.

        Args:
            parent: Parent tkinter widget.
            protocol_class: The protocol class to configure.
        """
        super().__init__(parent)

        self.protocol_class = protocol_class
        self.form_builder: ParameterFormBuilder | None = None

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create the tab widgets."""
        # Protocol description
        desc_frame = ttk.Frame(self)
        desc_frame.pack(fill="x", padx=10, pady=10)

        description = self.protocol_class.get_description()
        desc_label = ttk.Label(
            desc_frame,
            text=description,
            wraplength=500,
            justify="left",
        )
        desc_label.pack(anchor="w")

        # Separator
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # Parameter form in a scrollable frame
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Build parameter form
        parameters = self.protocol_class.get_parameters()
        self.form_builder = ParameterFormBuilder(scrollable_frame, parameters)
        self.form_builder.build()
        self.form_builder.pack(fill="both", expand=True)

        # Pack scrollable components
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        # Reset button at bottom
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=10)

        reset_button = ttk.Button(
            button_frame,
            text="Reset to Defaults",
            command=self._reset_to_defaults,
        )
        reset_button.pack(side="right")

    def _reset_to_defaults(self) -> None:
        """Reset all parameters to their default values."""
        if self.form_builder is not None:
            self.form_builder.reset_to_defaults()

    def get_parameters(self) -> dict:
        """
        Get the current parameter values.

        Returns:
            Dictionary of parameter values.

        Raises:
            ValueError: If validation fails.
        """
        if self.form_builder is None:
            return {}
        return self.form_builder.get_converted_values()

    def validate(self) -> tuple[bool, dict[str, str]]:
        """
        Validate the current parameter values.

        Returns:
            Tuple of (is_valid, errors).
        """
        if self.form_builder is None:
            return True, {}
        return self.form_builder.validate()


class MainWindow:
    """
    Main application window for the Behaviour Rig System.

    Provides the complete user interface for:
        - Selecting protocols via tabs
        - Configuring protocol parameters
        - Starting and stopping protocol execution
        - Monitoring protocol events

    Attributes:
        root: The tkinter root window.
        link: The BehaviourRigLink (may be None if not connected).
        current_protocol: The currently running protocol (if any).
    """

    def __init__(
        self,
        serial_port: str = "COM7",
        baud_rate: int = 115200,
        parent: tk.Toplevel | None = None,
        rig_name: str | None = None,
        rig_config: dict | None = None,
    ):
        """
        Initialise the main window.

        Args:
            serial_port: Serial port for hardware connection.
            baud_rate: Serial communication baud rate.
            parent: Optional parent Toplevel window (for multi-rig launcher).
            rig_name: Optional rig name to display in title.
            rig_config: Full rig configuration dict from rigs.yaml.
        """
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.parent = parent
        self.rig_name = rig_name
        self.rig_config = rig_config or {"name": rig_name, "serial_port": serial_port}

        self._serial: serial.Serial | None = None
        self.link: BehaviourRigLink | None = None
        self.current_protocol: BaseProtocol | None = None
        self.protocol_thread: threading.Thread | None = None
        self.session_manager: SessionManager | None = None
        self.startup_thread: threading.Thread | None = None

        self._setup_window()
        self._create_widgets()

        # Timer for updating elapsed time
        self._elapsed_timer_id: str | None = None

    def _setup_window(self) -> None:
        """Configure the main window."""
        # Use parent if provided, otherwise create new root
        if self.parent is not None:
            self.root = self.parent
        else:
            self.root = tk.Tk()
        
        # Set title
        if self.rig_name:
            self.root.title(f"Behaviour Rig System - {self.rig_name}")
        else:
            self.root.title("Behaviour Rig System")
        
        self.root.geometry("700x800")
        self.root.minsize(600, 600)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self) -> None:
        """Create the main window widgets."""
        # Main content frame (can be disabled during startup)
        self.content_frame = ttk.Frame(self.root)
        self.content_frame.pack(fill="both", expand=True)
        
        # Session info panel at top
        session_frame = ttk.LabelFrame(
            self.content_frame, text="Session Info", padding=(10, 5)
        )
        session_frame.pack(fill="x", padx=10, pady=5)
        
        # Mouse ID entry
        ttk.Label(session_frame, text="Mouse ID:").grid(
            row=0, column=0, sticky="w", padx=5
        )
        self.mouse_id_var = tk.StringVar(value="test")
        mouse_id_entry = ttk.Entry(
            session_frame, textvariable=self.mouse_id_var, width=20
        )
        mouse_id_entry.grid(row=0, column=1, sticky="w", padx=5)
        
        # Protocol tabs
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Create a tab for each available protocol
        self.protocol_tabs: dict[str, ProtocolTab] = {}
        for protocol_class in get_available_protocols():
            tab = ProtocolTab(self.notebook, protocol_class)
            protocol_name = protocol_class.get_name()
            self.notebook.add(tab, text=protocol_name)
            self.protocol_tabs[protocol_name] = tab

        # Status panel at bottom
        self.status_panel = StatusPanel(self.content_frame)
        self.status_panel.pack(fill="both", padx=10, pady=5)
        self.status_panel.on_start = self._start_protocol
        self.status_panel.on_stop = self._stop_protocol
        
        # Startup overlay (hidden by default)
        self._create_startup_overlay()
    
    def _create_startup_overlay(self) -> None:
        """Create the overlay shown during startup sequence."""
        self.startup_frame = ttk.Frame(self.root)
        # Don't pack yet - will be shown when starting
        
        # Center the content
        inner_frame = ttk.Frame(self.startup_frame)
        inner_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Startup title
        self.startup_title = ttk.Label(
            inner_frame,
            text="Starting Session...",
            font=("Helvetica", 16, "bold")
        )
        self.startup_title.pack(pady=(10, 5))
        
        # Progress text
        self.startup_status_var = tk.StringVar(value="Initializing...")
        self.startup_status = ttk.Label(
            inner_frame,
            textvariable=self.startup_status_var,
            font=("Helvetica", 11)
        )
        self.startup_status.pack(pady=5)
        
        # Progress bar
        self.startup_progress = ttk.Progressbar(
            inner_frame,
            mode="indeterminate",
            length=400
        )
        self.startup_progress.pack(pady=10)
        
        # Detailed log area
        log_label = ttk.Label(inner_frame, text="Startup Log:", font=("Helvetica", 10, "bold"))
        log_label.pack(anchor="w", pady=(10, 2))
        
        self.startup_log = scrolledtext.ScrolledText(
            inner_frame,
            height=20,
            width=80,
            font=("Consolas", 9),
            state="disabled",
            wrap="word"
        )
        self.startup_log.pack(fill="both", expand=True, pady=5)
        
        # Cancel button
        self.startup_cancel_btn = ttk.Button(
            inner_frame,
            text="Cancel",
            command=self._cancel_startup
        )
        self.startup_cancel_btn.pack(pady=10)
        
        self._startup_cancelled = False
    
    def _show_startup_overlay(self) -> None:
        """Show the startup overlay and disable main content."""
        self._startup_cancelled = False
        # Clear the startup log
        self.startup_log.config(state="normal")
        self.startup_log.delete("1.0", tk.END)
        self.startup_log.config(state="disabled")
        self.startup_status_var.set("Initializing...")
        
        self.content_frame.pack_forget()
        self.startup_frame.pack(fill="both", expand=True)
        self.startup_progress.start(10)
    
    def _hide_startup_overlay(self) -> None:
        """Hide the startup overlay and show main content."""
        self.startup_progress.stop()
        self.startup_frame.pack_forget()
        self.content_frame.pack(fill="both", expand=True)
    
    def _update_startup_status(self, message: str) -> None:
        """Update the startup status message and log (thread-safe)."""
        self.root.after(0, lambda: self._do_update_startup_status(message))
    
    def _do_update_startup_status(self, message: str) -> None:
        """Actually update the startup status (must be called from main thread)."""
        # Update the main status label with a shortened version
        short_msg = message
        if message.startswith("["):
            # Extract just the key part for the status label
            short_msg = message.split("]", 1)[-1].strip() if "]" in message else message
        self.startup_status_var.set(short_msg[:60] + "..." if len(short_msg) > 60 else short_msg)
        
        # Add full message to log with timestamp
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

    def _get_current_tab(self) -> ProtocolTab | None:
        """Get the currently selected protocol tab."""
        selection = self.notebook.select()
        if not selection:
            return None

        tab_text = self.notebook.tab(selection, "text")
        return self.protocol_tabs.get(tab_text)

    def _start_protocol(self) -> None:
        """Start the currently selected protocol."""
        tab = self._get_current_tab()
        if tab is None:
            messagebox.showerror("Error", "No protocol selected")
            return

        # Validate parameters
        is_valid, errors = tab.validate()
        if not is_valid:
            error_msg = "\n".join(f"- {k}: {v}" for k, v in errors.items())
            messagebox.showerror(
                "Validation Error",
                f"Please correct the following errors:\n{error_msg}",
            )
            return
        
        # Validate mouse ID
        mouse_id = self.mouse_id_var.get().strip()
        if not mouse_id:
            messagebox.showerror("Error", "Please enter a Mouse ID")
            return
        
        # Store tab and parameters for startup thread
        self._pending_tab = tab
        self._pending_parameters = tab.get_parameters()
        self._pending_mouse_id = mouse_id
        
        # Show startup overlay
        self._show_startup_overlay()
        
        # Run startup sequence in background thread
        self.startup_thread = threading.Thread(
            target=self._startup_sequence,
            daemon=True
        )
        self.startup_thread.start()
    
    def _startup_sequence(self) -> None:
        """Run the startup sequence in a background thread."""
        try:
            # Step 1: Create session config and manager
            self._update_startup_status("[GUI] Creating session config...")
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            session_config = load_session_config(
                self.rig_config,
                mouse_id=self._pending_mouse_id
            )
            
            self._update_startup_status("[GUI] Session config created")
            self._update_startup_status(f"[GUI] Python: {session_config.python_path}")
            self._update_startup_status(f"[GUI] DAQ script: {session_config.serial_listen_script}")
            self._update_startup_status(f"[GUI] Session folder: {session_config.session_folder}")
            
            self.session_manager = SessionManager(
                session_config,
                log_callback=self._update_startup_status
            )
            
            # Step 2: Start DAQ process
            self._update_startup_status("[GUI] Calling _start_daq()...")
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            if not self.session_manager._start_daq():
                error_msg = self.session_manager.last_error or "Failed to start Arduino DAQ"
                self._update_startup_status(f"[GUI] DAQ start failed: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self._on_startup_error(msg))
                return
            
            self._update_startup_status("[GUI] _start_daq() returned True")
            
            # Step 3: Wait for Arduino connection
            self._update_startup_status("[GUI] Calling _wait_for_connection()...")
            
            if not self.session_manager._wait_for_connection():
                if self._startup_cancelled:
                    self._on_startup_cancelled()
                else:
                    error_msg = self.session_manager.last_error or "Arduino connection timed out"
                    self._update_startup_status(f"[GUI] Connection wait failed: {error_msg}")
                    self.root.after(0, lambda msg=error_msg: self._on_startup_error(msg))
                return
            
            self._update_startup_status("[GUI] _wait_for_connection() returned True")
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            # Step 4: Start camera
            self._update_startup_status("[GUI] Calling _start_camera()...")
            
            if not self.session_manager._start_camera():
                error_msg = self.session_manager.last_error or "Failed to start camera"
                self._update_startup_status(f"[GUI] Camera start failed: {error_msg}")
                self.root.after(0, lambda msg=error_msg: self._on_startup_error(msg))
                return
            
            self._update_startup_status("[GUI] _start_camera() returned True")
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            # Step 5: Connect to rig
            self._update_startup_status("[GUI] Step 5: Connecting to behaviour rig serial...")
            self._update_startup_status(f"[GUI] Serial port: {self.serial_port}, baud: {self.baud_rate}")
            
            self._serial = serial.Serial(
                self.serial_port, self.baud_rate, timeout=0.1
            )
            self._update_startup_status("[GUI] Serial port opened ✓")
            
            self._update_startup_status("[GUI] Resetting Arduino via DTR...")
            reset_arduino_via_dtr(self._serial)
            self._update_startup_status("[GUI] Arduino reset complete ✓")
            
            self._update_startup_status("[GUI] Creating BehaviourRigLink...")
            self.link = BehaviourRigLink(self._serial)
            self.link.start()
            self._update_startup_status("[GUI] BehaviourRigLink started ✓")
            
            self._update_startup_status("[GUI] Sending hello handshake...")
            self.link.send_hello()
            self.link.wait_hello(timeout=5.0)
            self._update_startup_status("[GUI] Handshake complete ✓")
            
            if self._startup_cancelled:
                self._on_startup_cancelled()
                return
            
            self.session_manager.is_started = True
            
            # Step 6: Create protocol and start
            self._update_startup_status("[GUI] Step 6: Creating protocol instance...")
            
            self.current_protocol = self._pending_tab.protocol_class(
                parameters=self._pending_parameters,
                link=self.link,
            )
            self.current_protocol.add_event_listener(self._on_protocol_event)
            self._update_startup_status("[GUI] Protocol created ✓")
            
            self._update_startup_status("[GUI] ========== STARTUP COMPLETE ==========")
            
            # Success - switch to running state on main thread
            self.root.after(0, self._on_startup_complete)
            
        except Exception as e:
            import traceback
            error_detail = f"{e}\n\nTraceback:\n{traceback.format_exc()}"
            self._update_startup_status(f"[GUI] EXCEPTION: {e}")
            self._update_startup_status(f"[GUI] {traceback.format_exc()}")
            self.root.after(0, lambda: self._on_startup_error(str(e)))
    
    def _on_startup_complete(self) -> None:
        """Called when startup sequence completes successfully."""
        self._hide_startup_overlay()
        
        # Update UI
        self.status_panel.set_running_state(True)
        self.status_panel.log_message("Session started!")
        self.status_panel.log_message(
            f"Starting {self._pending_tab.protocol_class.get_name()}..."
        )
        
        # Start protocol in background thread
        self.protocol_thread = threading.Thread(
            target=self._run_protocol_thread,
            daemon=True,
        )
        self.protocol_thread.start()
        
        # Start elapsed time updates
        self._start_elapsed_timer()
    
    def _on_startup_error(self, error_msg: str) -> None:
        """Called when startup sequence fails."""
        self._hide_startup_overlay()
        
        # Clean up any started processes
        if self.session_manager:
            self.session_manager.stop_session()
            self.session_manager = None
        
        if self._serial:
            try:
                self._serial.close()
            except:
                pass
            self._serial = None
        
        self.link = None
        
        messagebox.showerror("Startup Failed", f"Failed to start session:\n\n{error_msg}")
    
    def _on_startup_cancelled(self) -> None:
        """Called when startup is cancelled by user."""
        # Clean up on main thread
        self.root.after(0, self._cleanup_startup_cancelled)
    
    def _cleanup_startup_cancelled(self) -> None:
        """Clean up after cancelled startup."""
        self._hide_startup_overlay()
        
        if self.session_manager:
            self.session_manager.stop_session()
            self.session_manager = None
        
        if self._serial:
            try:
                self._serial.close()
            except:
                pass
            self._serial = None
        
        self.link = None
        self.status_panel.log_message("Startup cancelled")

    def _run_protocol_thread(self) -> None:
        """Run the protocol in a background thread."""
        try:
            self.current_protocol.run()
        except Exception as e:
            # Schedule error handling on main thread
            self.root.after(0, lambda: self._on_protocol_error(e))
        finally:
            # Schedule cleanup on main thread
            self.root.after(0, self._on_protocol_complete)

    def _thread_safe_log(self, message: str) -> None:
        """
        Log a message from any thread safely.

        This method schedules the log message to be displayed on the main
        GUI thread, making it safe to call from hardware callbacks or
        protocol threads.

        Args:
            message: The message to log.
        """
        self.root.after(0, lambda: self.status_panel.log_message(message))

    def _on_protocol_event(self, event: ProtocolEvent) -> None:
        """
        Handle protocol events.

        Called from the protocol thread, so we schedule UI updates on the
        main thread.
        """
        # Schedule update on main thread
        self.root.after(0, lambda: self._handle_event(event))

    def _handle_event(self, event: ProtocolEvent) -> None:
        """Handle a protocol event on the main thread."""
        # Update status if this is a status-changing event
        if self.current_protocol is not None:
            self.status_panel.set_status(self.current_protocol.status)

        # Log the event
        self.status_panel.log_event(event)

    def _on_protocol_error(self, error: Exception) -> None:
        """Handle protocol errors."""
        self.status_panel.log_message(f"ERROR: {error}")
        messagebox.showerror("Protocol Error", str(error))

    def _on_protocol_complete(self) -> None:
        """Handle protocol completion."""
        self._stop_elapsed_timer()

        if self.current_protocol is not None:
            final_status = self.current_protocol.status
            self.status_panel.set_status(final_status)

            if final_status == ProtocolStatus.COMPLETED:
                self.status_panel.log_message("Protocol completed successfully")
            elif final_status == ProtocolStatus.ABORTED:
                self.status_panel.log_message("Protocol aborted by user")
            elif final_status == ProtocolStatus.ERROR:
                self.status_panel.log_message("Protocol terminated with error")

        self._cleanup_protocol()
        self.status_panel.set_running_state(False)

    def _stop_protocol(self) -> None:
        """Request the current protocol to stop."""
        if self.current_protocol is not None:
            self.status_panel.log_message("Requesting abort...")
            self.current_protocol.request_abort()

    def _cleanup_protocol(self) -> None:
        """Clean up protocol, link, and session resources."""
        # Stop the protocol first
        self.current_protocol = None
        self.protocol_thread = None
        
        # Shutdown BehavLink
        if self.link is not None:
            try:
                self.link.shutdown()
                self.link.stop()
            except Exception:
                pass
            self.link = None

        # Close serial connection
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        
        # Stop session manager (DAQ and camera processes)
        if self.session_manager is not None:
            try:
                self.status_panel.log_message("Stopping DAQ and camera...")
                self.session_manager.stop_session()
            except Exception as e:
                self.status_panel.log_message(f"Error stopping session: {e}")
            self.session_manager = None

    def _start_elapsed_timer(self) -> None:
        """Start the elapsed time update timer."""
        self._update_elapsed_time()

    def _stop_elapsed_timer(self) -> None:
        """Stop the elapsed time update timer."""
        if self._elapsed_timer_id is not None:
            self.root.after_cancel(self._elapsed_timer_id)
            self._elapsed_timer_id = None

    def _update_elapsed_time(self) -> None:
        """Update the elapsed time display."""
        if self.current_protocol is not None:
            elapsed = self.current_protocol.elapsed_time
            if elapsed is not None:
                self.status_panel.set_elapsed_time(elapsed)

            # Schedule next update
            if self.current_protocol.is_running:
                self._elapsed_timer_id = self.root.after(
                    1000, self._update_elapsed_time
                )

    def _on_close(self) -> None:
        """Handle window close event."""
        # Stop any running protocol
        if self.current_protocol is not None and self.current_protocol.is_running:
            if messagebox.askyesno(
                "Confirm Exit",
                "A protocol is currently running. Stop it and exit?",
            ):
                self._stop_protocol()
                # Wait briefly for protocol to stop
                self.root.after(500, self._force_close)
            return

        self._force_close()

    def _force_close(self) -> None:
        """Force close the application."""
        self._cleanup_protocol()
        # Only destroy if standalone (not embedded in launcher)
        if self.parent is None:
            self.root.destroy()

    def run(self) -> None:
        """Start the application main loop (only for standalone mode)."""
        if self.parent is None:
            self.root.mainloop()


def launch_gui(
    serial_port: str = "COM7",
    baud_rate: int = 115200,
) -> None:
    """
    Launch the Behaviour Rig System GUI.

    Args:
        serial_port: Serial port for hardware connection.
        baud_rate: Serial communication baud rate.
    """
    app = MainWindow(
        serial_port=serial_port,
        baud_rate=baud_rate,
    )
    app.run()
