"""
Rig Window - Thin view layer for mode management (DearPyGui).

Builds its content inside a provided parent container (typically a tab)
and manages transitions between:
    - SetupMode: Configure and start session
    - RunningMode: Monitor active session
    - PostSessionMode: Review completed session

All business logic lives in SessionController. This class only:
    1. Creates and lays out widgets inside the parent
    2. Delegates user actions to the controller
    3. Marshals controller events onto the DPG main thread
"""

import logging
from enum import Enum, auto
from typing import Callable

import dearpygui.dearpygui as dpg

from hexcontrol.core.protocol_base import ProtocolStatus
from hexcontrol.core.session_controller import SessionController
from hexcontrol.core.session_state import SessionStatus
from hexcontrol.simulation.simulated_mouse import SimulatedMouse

from .dpg_app import call_on_main_thread, call_later
from .dpg_dialogs import show_warning, show_error
from .modes import SetupMode, RunningMode, PostSessionMode
from .startup_overlay import StartupOverlay
from .virtual_rig_window import VirtualRigWindow


logger = logging.getLogger(__name__)


class WindowMode(Enum):
    """The three modes of the rig window."""
    SETUP = auto()
    RUNNING = auto()
    POST_SESSION = auto()


class RigWindow:
    """
    Main view for a single behaviour rig.

    Thin view layer — delegates all business logic to SessionController
    and reacts to its events. Builds content inside a parent container
    (typically a DPG tab).
    """

    def __init__(
        self,
        parent_tab: int | str,
        serial_port: str = "",
        baud_rate: int = 115200,
        rig_config=None,
        claim_mouse_fn=None,
        release_mouse_fn=None,
        get_claimed_mice_fn=None,
        cohort_folders: tuple = (),
        mice: tuple = (),
        on_tab_close: Callable[[], None] | None = None,
    ):
        self._parent = parent_tab
        self.rig_config = rig_config
        self.claim_mouse_fn = claim_mouse_fn
        self.release_mouse_fn = release_mouse_fn
        self.get_claimed_mice_fn = get_claimed_mice_fn
        self.cohort_folders = cohort_folders
        self.mice = mice
        self._on_tab_close = on_tab_close

        self._virtual_rig_window: VirtualRigWindow | None = None
        self._simulated_mouse: SimulatedMouse | None = None
        self._pending_result = None
        self._current_mode = WindowMode.SETUP

        # Create the controller
        self.controller = SessionController(
            rig_config=rig_config,
            serial_port=serial_port,
            baud_rate=baud_rate,
            simulate=rig_config.simulate if rig_config else False,
        )

        self.rig_name = self.rig_config.name if self.rig_config else "Unknown"

        self._create_modes()
        self._create_startup_overlay()
        self._bind_controller_events()
        self._show_mode(WindowMode.SETUP)

    # =========================================================================
    # Mode Creation
    # =========================================================================

    def _create_modes(self) -> None:
        self.setup_mode = SetupMode(
            self._parent,
            rig_config=self.rig_config,
            on_start=self._start_session,
            claim_mouse_fn=self.claim_mouse_fn,
            get_claimed_mice_fn=self.get_claimed_mice_fn,
            cohort_folders=self.cohort_folders,
            mice=self.mice,
        )
        self.running_mode = RunningMode(
            self._parent,
            on_stop=self._stop_session,
        )
        self.post_session_mode = PostSessionMode(
            self._parent,
            on_new_session=self._new_session,
            on_close_window=self._close_tab,
        )

    def _create_startup_overlay(self) -> None:
        self.startup_overlay = StartupOverlay(
            self._parent,
            on_cancel=self._cancel_startup,
        )

    # =========================================================================
    # Controller Event Binding
    # =========================================================================

    def _bind_controller_events(self) -> None:
        """Wire controller events to GUI methods, with thread marshalling."""
        def on_main_thread(fn):
            def wrapper(**kwargs):
                call_on_main_thread(fn, **kwargs)
            return wrapper

        c = self.controller
        c.on("startup_complete",   on_main_thread(self._on_startup_complete))
        c.on("startup_error",      on_main_thread(self._on_startup_error))
        c.on("startup_cancelled",  on_main_thread(self._on_startup_cancelled))
        c.on("protocol_complete",  on_main_thread(self._on_protocol_complete))
        c.on("finalize_complete",  on_main_thread(self._on_finalize_complete))
        c.on("cleanup_complete",   on_main_thread(self._on_cleanup_complete))
        c.on("startup_status",     on_main_thread(self._on_startup_status))
        c.on("protocol_log",       on_main_thread(self._on_protocol_log))
        c.on("performance_update", on_main_thread(self._on_performance_update))
        c.on("stimulus",           on_main_thread(self._on_stimulus))
        c.on("cleanup_log",        on_main_thread(self._on_cleanup_log))
        c.on("status_changed",     on_main_thread(self._on_status_changed))
        c.on("peripheral_error",   on_main_thread(self._on_peripheral_error))

    # =========================================================================
    # Mode Management
    # =========================================================================

    def _show_mode(self, mode: WindowMode) -> None:
        if self._current_mode == WindowMode.RUNNING and mode != WindowMode.RUNNING:
            try:
                self.running_mode.deactivate()
            except Exception as e:
                print(f"Warning: error deactivating running mode: {e}")

        self.setup_mode.hide()
        self.running_mode.hide()
        self.post_session_mode.hide()
        self.startup_overlay.hide()

        self._current_mode = mode
        if mode == WindowMode.SETUP:
            self.setup_mode.show()
        elif mode == WindowMode.RUNNING:
            self.running_mode.show()
        elif mode == WindowMode.POST_SESSION:
            self.post_session_mode.show()

    # =========================================================================
    # User Actions -> Controller
    # =========================================================================

    def _start_session(self, session_config: dict) -> None:
        self.setup_mode.hide()
        self.startup_overlay.show()
        self.controller.start_session(session_config)

    def _stop_session(self) -> None:
        self.running_mode.set_stopping()
        self.running_mode.log_message("Requesting stop...")
        self.controller.stop_session()

    def _cancel_startup(self) -> None:
        self.controller.cancel_startup()

    def _new_session(self) -> None:
        self.controller.new_session()
        self._show_mode(WindowMode.SETUP)

    def _close_tab(self) -> None:
        """Close this rig's tab (called from post-session Close button)."""
        self.controller.close()
        if self._on_tab_close:
            self._on_tab_close()

    # =========================================================================
    # Controller Event Handlers
    # =========================================================================

    def _on_startup_status(self, message: str) -> None:
        self.startup_overlay.update_status(message)

    def _on_startup_complete(
        self, scales_client, virtual_rig_state, session_info: dict,
        mouse_params=None, clock=None, tracker_definitions=None,
    ) -> None:
        self.startup_overlay.hide()

        mouse_enabled = (
            mouse_params is not None and mouse_params.get("mouse_enabled", False)
        )
        mouse_headless = mouse_params.get("mouse_headless", False) if mouse_enabled else False

        if virtual_rig_state is not None and not mouse_headless:
            self._virtual_rig_window = VirtualRigWindow(None, virtual_rig_state)

        if scales_client is not None:
            self.running_mode.set_scales_client(scales_client)
            if self.rig_config and self.rig_config.simulate:
                self.running_mode.set_battery_detection(False)

        try:
            rig_number = int(self.rig_name.split()[-1])
        except (ValueError, IndexError):
            rig_number = 0
        self.running_mode.activate(
            session_info,
            tracker_definitions=tracker_definitions or [],
            rig_number=rig_number,
        )

        scales_threshold = session_info.get("scales_threshold")
        if scales_threshold is not None:
            self.running_mode.set_scales_threshold(scales_threshold)

        self.running_mode.set_status(ProtocolStatus.RUNNING)
        self._show_mode(WindowMode.RUNNING)
        self.running_mode.start_timer()
        self.running_mode.log_message("Session started!")
        self.running_mode.log_message(f"Running {session_info['protocol_name']}...")

        if mouse_enabled and virtual_rig_state is not None:
            self._simulated_mouse = SimulatedMouse(mouse_params, virtual_rig_state, clock=clock)
            self._simulated_mouse.on(
                "log", lambda message: call_on_main_thread(
                    self.running_mode.log_message, message=message
                )
            )
            self._simulated_mouse.start()

        self.controller.run_protocol()

    def _on_startup_error(self, message: str) -> None:
        self.startup_overlay.show_error(message, on_close=self._close_startup_error)

    def _on_startup_cancelled(self) -> None:
        self.startup_overlay.hide()
        self._show_mode(WindowMode.SETUP)

    def _on_protocol_log(self, message: str) -> None:
        self.running_mode.log_message(message)

    def _on_performance_update(self, trackers=None, updated="") -> None:
        self.running_mode.update_performance(trackers=trackers, updated=updated)

    def _on_stimulus(self, port: int) -> None:
        self.running_mode.log_stimulus(port)

    def _on_protocol_complete(self, final_status) -> None:
        self.running_mode.stop_timer()
        self.running_mode.stop_scales_plot()
        self.running_mode.set_status(final_status)
        self.running_mode.log_message(f"Session {final_status.name.lower()}")
        self.running_mode.log_message("Finalising results...")
        self.controller.finalize_protocol(final_status)

    def _on_finalize_complete(self, result) -> None:
        result.elapsed_time = self.running_mode.get_elapsed_time()
        self._pending_result = result
        self.running_mode.log_message("Cleaning up...")
        self.controller.cleanup_session()

    def _on_cleanup_log(self, message: str) -> None:
        self.running_mode.log_message(message)

    def _on_cleanup_complete(self) -> None:
        if self._simulated_mouse is not None:
            self._simulated_mouse.stop()
            self._simulated_mouse = None

        if self._virtual_rig_window is not None:
            self._virtual_rig_window.close()
            self._virtual_rig_window = None

        self.running_mode.log_message("Cleanup complete")
        call_later(500, self._transition_to_post_session)

    def _transition_to_post_session(self) -> None:
        if self._pending_result is not None:
            self.post_session_mode.activate({
                "status": self._pending_result.status,
                "protocol_name": self._pending_result.protocol_name,
                "mouse_id": self._pending_result.mouse_id,
                "elapsed_time": self._pending_result.elapsed_time,
                "save_path": self._pending_result.save_path,
                "performance_reports": self._pending_result.performance_reports,
            })
            self._show_mode(WindowMode.POST_SESSION)
            self._pending_result = None

    def _on_status_changed(self, status: SessionStatus) -> None:
        pass

    def _on_peripheral_error(self, message: str = "") -> None:
        self.running_mode.log_message(f"ERROR: {message}")
        logger.error(f"[Rig Window] {message}")
        show_error(
            "Peripheral Failure",
            f"{message}\n\n"
            "The session has been stopped.\n"
            "Data recorded before the failure has been saved.",
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _close_startup_error(self) -> None:
        self.startup_overlay.hide()
        self._show_mode(WindowMode.SETUP)
