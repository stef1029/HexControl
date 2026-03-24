"""
Rig Window - Thin view layer for mode management.

This is the main window for a single rig, managing transitions between:
    - SetupMode: Configure and start session
    - RunningMode: Monitor active session
    - PostSessionMode: Review completed session

All business logic lives in SessionController. This class only:
    1. Creates and lays out widgets
    2. Delegates user actions to the controller
    3. Marshals controller events onto the tkinter main thread
"""

import tkinter as tk
from enum import Enum, auto
from tkinter import messagebox, ttk

from core.protocol_base import ProtocolStatus
from core.session_controller import SessionController
from core.session_state import SessionStatus

from simulation.simulated_mouse import SimulatedMouse

from .modes import SetupMode, RunningMode, PostSessionMode
from .startup_overlay import StartupOverlay
from .theme import apply_theme
from .virtual_rig_window import VirtualRigWindow


class WindowMode(Enum):
    """The three modes of the rig window."""
    SETUP = auto()
    RUNNING = auto()
    POST_SESSION = auto()


class RigWindow:
    """
    Main window for a single behaviour rig.

    Thin view layer — delegates all business logic to SessionController
    and reacts to its events.
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

        self.parent = parent
        self.rig_config = rig_config

        # Make simulate flag visible to SetupMode via rig_config
        if simulate:
            self.rig_config["simulate"] = True

        # Virtual rig window (GUI-only, managed here not in controller)
        self._virtual_rig_window: VirtualRigWindow | None = None

        # Simulated mouse (created on startup_complete if enabled)
        self._simulated_mouse: SimulatedMouse | None = None

        # Pending result for post-session (set by protocol_complete, used by cleanup_complete)
        self._pending_result = None

        self._current_mode = WindowMode.SETUP

        # Create the controller (all business logic)
        self.controller = SessionController(
            rig_config=rig_config,
            serial_port=serial_port,
            baud_rate=baud_rate,
            simulate=simulate,
        )

        self._setup_window()
        self._create_modes()
        self._create_startup_overlay()
        self._bind_controller_events()
        self._show_mode(WindowMode.SETUP)

    # =========================================================================
    # Window Setup
    # =========================================================================

    def _setup_window(self) -> None:
        """Configure the main window."""
        self.root = self.parent
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
            on_start=self._start_session,
        )
        self.running_mode = RunningMode(
            self.root,
            on_stop=self._stop_session,
        )
        self.post_session_mode = PostSessionMode(
            self.root,
            on_new_session=self._new_session,
        )

    def _create_startup_overlay(self) -> None:
        """Create the overlay shown during startup sequence."""
        self.startup_overlay = StartupOverlay(
            self.root,
            on_cancel=self._cancel_startup,
        )

    # =========================================================================
    # Controller Event Binding
    # =========================================================================

    def _bind_controller_events(self) -> None:
        """Wire controller events to GUI methods, with thread marshalling."""
        def on_main_thread(fn):
            """Wrap fn so it runs on the tkinter main thread."""
            def wrapper(**kwargs):
                self.root.after(0, lambda: fn(**kwargs))
            return wrapper

        c = self.controller
        c.on("startup_status",     on_main_thread(self._on_startup_status))
        c.on("startup_complete",   on_main_thread(self._on_startup_complete))
        c.on("startup_error",      on_main_thread(self._on_startup_error))
        c.on("startup_cancelled",  on_main_thread(self._on_startup_cancelled))
        c.on("protocol_log",       on_main_thread(self._on_protocol_log))
        c.on("performance_update", on_main_thread(self._on_performance_update))
        c.on("stimulus",           on_main_thread(self._on_stimulus))
        c.on("protocol_complete",  on_main_thread(self._on_protocol_complete))
        c.on("cleanup_log",        on_main_thread(self._on_cleanup_log))
        c.on("cleanup_complete",   on_main_thread(self._on_cleanup_complete))
        c.on("status_changed",     on_main_thread(self._on_status_changed))

    # =========================================================================
    # Mode Management
    # =========================================================================

    def _show_mode(self, mode: WindowMode) -> None:
        """Switch to the specified mode."""
        if self._current_mode == WindowMode.RUNNING and mode != WindowMode.RUNNING:
            try:
                self.running_mode.deactivate()
            except Exception:
                pass

        self.setup_mode.pack_forget()
        self.running_mode.pack_forget()
        self.post_session_mode.pack_forget()
        self.startup_overlay.pack_forget()

        self._current_mode = mode
        if mode == WindowMode.SETUP:
            self.setup_mode.pack(fill="both", expand=True)
        elif mode == WindowMode.RUNNING:
            self.running_mode.pack(fill="both", expand=True)
        elif mode == WindowMode.POST_SESSION:
            self.post_session_mode.pack(fill="both", expand=True)

    # =========================================================================
    # User Actions → Controller
    # =========================================================================

    def _start_session(self, session_config: dict) -> None:
        """Called by SetupMode when user clicks Start."""
        self.setup_mode.pack_forget()
        self.startup_overlay.show()
        self.controller.start_session(session_config)

    def _stop_session(self) -> None:
        """Called by RunningMode when user clicks Stop."""
        self.running_mode.set_stopping()
        self.running_mode.log_message("Requesting stop...")
        self.controller.stop_session()

    def _cancel_startup(self) -> None:
        """Called by StartupOverlay when user clicks Cancel."""
        self.controller.cancel_startup()

    def _new_session(self) -> None:
        """Called by PostSessionMode when user clicks New Session."""
        self.controller.new_session()
        self._show_mode(WindowMode.SETUP)

    # =========================================================================
    # Controller Event Handlers (all run on main thread)
    # =========================================================================

    def _on_startup_status(self, message: str) -> None:
        self.startup_overlay.update_status(message)

    def _on_startup_complete(
        self, scales_client, virtual_rig_state, session_info: dict,
        mouse_params=None, clock=None,
    ) -> None:
        self.startup_overlay.hide()

        # Determine if mouse is enabled and headless
        mouse_enabled = (
            mouse_params is not None and mouse_params.get("mouse_enabled", False)
        )
        mouse_headless = mouse_params.get("mouse_headless", False) if mouse_enabled else False

        # Open VirtualRigWindow unless headless mouse is active
        if virtual_rig_state is not None and not mouse_headless:
            self._virtual_rig_window = VirtualRigWindow(self.root, virtual_rig_state)

        if scales_client is not None:
            self.running_mode.set_scales_client(scales_client)

        self.running_mode.activate(session_info)
        self.running_mode.set_status(ProtocolStatus.RUNNING)
        self._show_mode(WindowMode.RUNNING)
        self.running_mode.start_timer()
        self.running_mode.log_message("Session started!")
        self.running_mode.log_message(f"Running {session_info['protocol_name']}...")

        # Create and start simulated mouse if enabled
        if mouse_enabled and virtual_rig_state is not None:
            self._simulated_mouse = SimulatedMouse(mouse_params, virtual_rig_state, clock=clock)

            # Wire mouse events to GUI via main thread
            def on_main_thread(fn):
                def wrapper(**kwargs):
                    self.root.after(0, lambda: fn(**kwargs))
                return wrapper

            self._simulated_mouse.on(
                "log", on_main_thread(lambda message: self.running_mode.log_message(message))
            )
            self._simulated_mouse.start()

        # Start protocol execution
        self.controller.run_protocol()

    def _on_startup_error(self, message: str) -> None:
        self.startup_overlay.show_error(message, on_close=self._close_startup_error)

    def _on_startup_cancelled(self) -> None:
        self.startup_overlay.hide()
        self._show_mode(WindowMode.SETUP)

    def _on_protocol_log(self, message: str) -> None:
        self.running_mode.log_message(message)

    def _on_performance_update(self, tracker) -> None:
        self.running_mode.update_performance(tracker)

    def _on_stimulus(self, port: int) -> None:
        self.running_mode.log_stimulus(port)

    def _on_protocol_complete(self, result, final_status) -> None:
        self.running_mode.stop_timer()
        self.running_mode.stop_scales_plot()
        self.running_mode.set_status(final_status)

        # Fill in elapsed time from the GUI timer
        result.elapsed_time = self.running_mode.get_elapsed_time()

        self.running_mode.log_message(f"Session {result.status.lower()}")
        self.running_mode.log_message("Cleaning up...")
        self._pending_result = result

    def _on_cleanup_log(self, message: str) -> None:
        self.running_mode.log_message(message)

    def _on_cleanup_complete(self) -> None:
        # Stop simulated mouse
        if self._simulated_mouse is not None:
            self._simulated_mouse.stop()
            self._simulated_mouse = None

        # Close virtual rig window
        if self._virtual_rig_window is not None:
            self._virtual_rig_window.close()
            self._virtual_rig_window = None

        if self._pending_result is not None:
            self.post_session_mode.activate({
                "status": self._pending_result.status,
                "protocol_name": self._pending_result.protocol_name,
                "mouse_id": self._pending_result.mouse_id,
                "elapsed_time": self._pending_result.elapsed_time,
                "save_path": self._pending_result.save_path,
                "performance_report": self._pending_result.performance_report,
            })
            self._show_mode(WindowMode.POST_SESSION)
            self._pending_result = None

    def _on_status_changed(self, status: SessionStatus) -> None:
        pass  # Available for future use (e.g. disabling buttons based on status)

    # =========================================================================
    # Window Management
    # =========================================================================

    def _close_startup_error(self) -> None:
        """Close the startup error overlay and return to setup mode."""
        self.startup_overlay.hide()
        self._show_mode(WindowMode.SETUP)

    def _on_close(self) -> None:
        """Handle window close event."""
        if self.controller.is_running:
            messagebox.showwarning(
                "Session Running",
                "A session is currently running.\n\nPlease stop the session before closing the window."
            )
            return
        self.controller.close()
