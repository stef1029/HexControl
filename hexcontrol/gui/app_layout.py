"""
Application Layout — VSCode-style unified viewport.

Provides the root layout with:
    - Activity bar (icon buttons, far left)
    - Sidebar (toggleable panels, left)
    - Main content area (tabbed rig views, center/right)
    - Info bar (status, clock, bottom)

Replaces the old multi-window launcher architecture.
"""

from __future__ import annotations

import logging
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import serial

import dearpygui.dearpygui as dpg

from BehavLink import BehaviourRigLink, reset_arduino_via_dtr
from hexcontrol.core.board_registry import BoardRegistry

from .dpg_app import call_on_main_thread, frame_poller, call_later
from .dpg_dialogs import show_info, show_warning, show_error, ask_yes_no
from .icon_registry import IconRegistry
from .launcher_background import draw_background, _GENERATORS
from .theme import (
    Theme, apply_theme, hex_to_rgba, style_rig_button,
    _ensure_rig_button_themes, _rig_button_themes,
    PALETTES, BORING_PALETTE,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .rig_window import RigWindow


# ---------------------------------------------------------------------------
# Connection testing (runs in background threads)
# ---------------------------------------------------------------------------

def test_rig_connection(
    board_name: str,
    board_type: str = "giga",
    registry: BoardRegistry = None,
) -> tuple[bool, str]:
    """Test connection to a rig by resolving its board name via the registry."""
    ser = None
    link = None
    try:
        serial_port = registry.resolve_port(board_name)
        baud_rate = registry.resolve_baudrate(board_name)
        ser = serial.Serial(serial_port, baud_rate, timeout=0.1)
        reset_arduino_via_dtr(ser)
        link = BehaviourRigLink(ser, board_type=board_type)
        link.start()
        link.send_hello()
        link.wait_hello(timeout=3.0)
        link.stop()
        ser.close()
        return True, f"Connection successful on {serial_port}!"
    except KeyError as e:
        return False, f"Board not registered: {e}"
    except RuntimeError as e:
        return False, f"Board not found: {e}"
    except serial.SerialException as e:
        return False, f"Serial port error: {e}"
    except TimeoutError:
        return False, "No response from rig (timeout)"
    except Exception as e:
        return False, f"Connection failed: {e}"
    finally:
        if link:
            try:
                link.stop()
            except Exception:
                pass
        if ser and ser.is_open:
            try:
                ser.close()
            except Exception:
                pass


# ===========================================================================
# AppLayout
# ===========================================================================

class AppLayout:
    """Single-viewport layout: activity bar + sidebar + tabbed content + info bar."""

    def __init__(self, config_path: Path, board_registry_path: Path):
        from core.rig_config import RigsFile
        self._rigs_file = RigsFile.load(config_path)

        # Apply palette
        palette_name = self._rigs_file.global_config.palette
        if palette_name in PALETTES:
            Theme.set_palette(PALETTES[palette_name])
        else:
            logger.warning(f"Unknown palette '{palette_name}'. Falling back to 'boring'.")
            Theme.set_palette(BORING_PALETTE)

        self.rigs = list(self._rigs_file.rigs)
        self.baud_rate = self._rigs_file.global_config.baud_rate
        self.board_registry = BoardRegistry(board_registry_path)

        # Rig state
        self.open_rigs: dict[str, tuple[int, "RigWindow"]] = {}  # name -> (tab_id, rig_window)
        self.rig_buttons: dict[str, int] = {}
        self.rig_status_texts: dict[str, int] = {}

        from core.mouse_claims import MouseClaims
        self._mouse_claims = MouseClaims()
        self._shared_multi_session_folder: str | None = None
        self._active_panel: str | None = "rigs"

        # DPG IDs
        self._clock_text: int | None = None
        self._status_text: int | None = None
        self._tab_bar: int | None = None
        self._welcome_group: int | None = None
        self._sidebar: int | None = None
        self._sidebar_panels: dict[str, int] = {}

        # Icons
        self._icons = IconRegistry()
        self._icons.create_default_icons()

        # Apply theme (fonts + global theme)
        apply_theme()

        # Build layout
        self._build_layout()

        # Clock polling
        frame_poller.register(1000, self._update_clock)

    # =====================================================================
    # Layout construction
    # =====================================================================

    def _build_layout(self) -> None:
        palette = Theme.palette
        info_bar_height = 28

        with dpg.window(tag="primary", no_title_bar=True, no_move=True,
                        no_resize=True, no_scrollbar=True):

            # Main area: fills all space except info bar height
            # Use child_window with negative height to reserve space for info bar
            with dpg.child_window(height=-info_bar_height, border=False,
                                  no_scrollbar=True):
                with dpg.group(horizontal=True):
                    self._build_activity_bar()
                    self._build_sidebar()
                    self._build_main_content()

            # Info bar: pinned at bottom, always visible
            self._build_info_bar()

        dpg.set_primary_window("primary", True)

    def _build_activity_bar(self) -> None:
        with dpg.child_window(width=42, height=-1, no_scrollbar=True,
                              tag="activity_bar", border=False) as ab:
            dpg.add_spacer(height=4)
            for icon_name, panel_name in [
                ("rigs", "rigs"), ("tools", "tools"),
                ("postproc", "postproc"), ("docs", "docs"),
            ]:
                btn = dpg.add_image_button(
                    self._icons.get(icon_name), width=28, height=28,
                    callback=lambda s, a, u: self._toggle_panel(u),
                    user_data=panel_name,
                )
                if Theme.icon_button_theme:
                    dpg.bind_item_theme(btn, Theme.icon_button_theme)
                dpg.add_spacer(height=4)
        if Theme.activity_bar_theme:
            dpg.bind_item_theme(ab, Theme.activity_bar_theme)

    def _build_sidebar(self) -> None:
        with dpg.child_window(width=240, height=-1, tag="sidebar",
                              border=False, show=True) as sb:
            self._sidebar = sb
            self._build_rigs_panel()
            self._build_tools_panel()
            self._build_postproc_panel()
            self._build_docs_panel()
        if Theme.sidebar_theme:
            dpg.bind_item_theme(sb, Theme.sidebar_theme)
        # Show rigs panel by default
        self._show_panel("rigs")

    def _build_main_content(self) -> None:
        with dpg.child_window(width=-1, height=-1, border=False, tag="main_content"):
            self._tab_bar = dpg.add_tab_bar(tag="rig_tab_bar", reorderable=True)

            # Welcome view — full-area generative art with centered text overlay
            self._welcome_drawlist = dpg.add_drawlist(
                width=100, height=100, tag="welcome_view",
            )
            self._welcome_group = self._welcome_drawlist
            self._welcome_drawn = False
            self._welcome_last_size = (0, 0)

            import random as _rnd
            self._welcome_rng_seed = _rnd.randint(0, 999999)

            # Poll for resize every frame (cheap — only redraws when size changes)
            frame_poller.register(50, self._check_welcome_resize)

    def _build_info_bar(self) -> None:
        with dpg.child_window(height=28, no_scrollbar=True, border=False,
                              tag="info_bar") as ib:
            with dpg.group(horizontal=True):
                self._clock_text = dpg.add_text("--:--",
                    color=hex_to_rgba(Theme.palette.text_secondary))
                if Theme.font_small():
                    dpg.bind_item_font(self._clock_text, Theme.font_small())
                dpg.add_text("  |  ", color=hex_to_rgba(Theme.palette.border_medium))
                self._status_text = dpg.add_text("Ready",
                    color=hex_to_rgba(Theme.palette.text_secondary))
                if Theme.font_small():
                    dpg.bind_item_font(self._status_text, Theme.font_small())
        if Theme.info_bar_theme:
            dpg.bind_item_theme(ib, Theme.info_bar_theme)

    # =====================================================================
    # Welcome view
    # =====================================================================

    def _check_welcome_resize(self) -> None:
        """Periodic check — redraw welcome art if main_content size changed."""
        dl = self._welcome_drawlist
        if not dpg.does_item_exist(dl):
            return
        if not dpg.get_item_configuration(dl).get("show", True):
            return

        # Get actual rendered size of main_content; fall back to viewport
        w = dpg.get_item_width("main_content")
        h = dpg.get_item_height("main_content")
        if w < 50 or h < 50:
            # main_content may not be laid out yet — use viewport as estimate
            w = dpg.get_viewport_client_width() - 300  # minus sidebar + activity bar
            h = dpg.get_viewport_client_height() - 60   # minus info bar + padding
        if w < 50 or h < 50:
            return

        size = (w, h)
        if size == self._welcome_last_size and self._welcome_drawn:
            return

        self._welcome_last_size = size

        # Resize drawlist to fill
        dpg.configure_item(dl, width=w, height=h)

        # Clear and redraw with consistent seed
        import random as _rnd
        dpg.delete_item(dl, children_only=True)

        gen = _rnd.Random(self._welcome_rng_seed).choice(_GENERATORS)
        gen(dl, w, h, _rnd.Random(self._welcome_rng_seed))

        self._draw_welcome_overlay(dl, w, h)
        self._welcome_drawn = True

    @staticmethod
    def _draw_centered_text(dl, text: str, cx: float, y: float,
                            font_size: float, color: list[int]) -> None:
        """Draw text horizontally centered around *cx* at vertical position *y*."""
        text_w = len(text) * font_size * 0.55
        dpg.draw_text(
            pos=[cx - text_w / 2, y], text=text, size=font_size,
            color=color, parent=dl,
        )

    def _draw_welcome_overlay(self, dl: int, w: int, h: int) -> None:
        """Draw centered title text with a backdrop card on the drawlist."""
        palette = Theme.palette

        card_w = min(520, w - 60)
        card_h = 150
        card_x = (w - card_w) / 2
        card_y = (h - card_h) / 2 - 30
        card_cx = card_x + card_w / 2

        # Semi-transparent backdrop
        dpg.draw_rectangle(
            pmin=[card_x, card_y],
            pmax=[card_x + card_w, card_y + card_h],
            fill=hex_to_rgba(palette.bg_primary, alpha=200),
            color=[0, 0, 0, 0], rounding=10, parent=dl,
        )

        # Subtle border
        dpg.draw_rectangle(
            pmin=[card_x, card_y],
            pmax=[card_x + card_w, card_y + card_h],
            fill=[0, 0, 0, 0],
            color=hex_to_rgba(palette.border_medium, alpha=120),
            rounding=10, thickness=1, parent=dl,
        )

        # Title
        self._draw_centered_text(
            dl, "Hex Behaviour System", card_cx, card_y + 28,
            28, hex_to_rgba(palette.text_primary),
        )

        # Subtitle
        self._draw_centered_text(
            dl, "Select a rig from the sidebar to begin",
            card_cx, card_y + 75,
            15, hex_to_rgba(palette.text_secondary),
        )

        # Hint
        self._draw_centered_text(
            dl, "Use the activity bar on the left to navigate",
            card_cx, card_y + 110,
            12, hex_to_rgba(palette.text_disabled),
        )

    # =====================================================================
    # Sidebar panels
    # =====================================================================

    def _build_rigs_panel(self) -> None:
        palette = Theme.palette
        with dpg.group(tag="panel_rigs", show=True, parent="sidebar") as g:
            self._sidebar_panels["rigs"] = g
            t = dpg.add_text("Rigs", color=hex_to_rgba(palette.text_primary))
            if Theme.font_heading():
                dpg.bind_item_font(t, Theme.font_heading())
            dpg.add_separator()
            dpg.add_spacer(height=4)

            for rig in self.rigs[:4]:
                rig_name = rig.name
                enabled = rig.enabled

                with dpg.group(horizontal=True):
                    status_text = dpg.add_text("  o  ",
                        color=hex_to_rgba(palette.text_disabled))
                    self.rig_status_texts[rig_name] = status_text

                    btn = dpg.add_button(
                        label=rig_name, width=-1, height=32,
                        callback=lambda s, a, u: self._on_rig_click(u),
                        user_data=rig,
                    )
                    _ensure_rig_button_themes()
                    dpg.bind_item_theme(btn, _rig_button_themes["normal"])
                    self.rig_buttons[rig_name] = btn

                    if not enabled:
                        style_rig_button(btn, is_open=True)

            dpg.add_spacer(height=8)

    def _build_tools_panel(self) -> None:
        palette = Theme.palette
        with dpg.group(tag="panel_tools", show=False, parent="sidebar") as g:
            self._sidebar_panels["tools"] = g
            t = dpg.add_text("Tools", color=hex_to_rgba(palette.text_primary))
            if Theme.font_heading():
                dpg.bind_item_font(t, Theme.font_heading())
            dpg.add_separator()
            dpg.add_spacer(height=4)

            btn = dpg.add_button(label="Zero All Scales", width=-1,
                                 callback=lambda: self._on_zero_scales_click())
            if Theme.secondary_button_theme:
                dpg.bind_item_theme(btn, Theme.secondary_button_theme)

            dpg.add_spacer(height=4)
            btn = dpg.add_button(label="Mock Rig", width=-1,
                                 callback=lambda: self._on_mock_rig_click())
            if Theme.secondary_button_theme:
                dpg.bind_item_theme(btn, Theme.secondary_button_theme)

    def _build_postproc_panel(self) -> None:
        palette = Theme.palette
        with dpg.group(tag="panel_postproc", show=False, parent="sidebar") as g:
            self._sidebar_panels["postproc"] = g
            t = dpg.add_text("Post-Processing", color=hex_to_rgba(palette.text_primary))
            if Theme.font_heading():
                dpg.bind_item_font(t, Theme.font_heading())
            dpg.add_separator()
            dpg.add_spacer(height=4)

            btn = dpg.add_button(label="Open Post-Processing", width=-1,
                                 callback=lambda: self._on_post_processing_click())
            if Theme.primary_button_theme:
                dpg.bind_item_theme(btn, Theme.primary_button_theme)

    def _build_docs_panel(self) -> None:
        palette = Theme.palette
        with dpg.group(tag="panel_docs", show=False, parent="sidebar") as g:
            self._sidebar_panels["docs"] = g
            t = dpg.add_text("Documentation", color=hex_to_rgba(palette.text_primary))
            if Theme.font_heading():
                dpg.bind_item_font(t, Theme.font_heading())
            dpg.add_separator()
            dpg.add_spacer(height=4)

            btn = dpg.add_button(label="Open Docs", width=-1,
                                 callback=lambda: self._on_docs_click())
            if Theme.secondary_button_theme:
                dpg.bind_item_theme(btn, Theme.secondary_button_theme)

            dpg.add_spacer(height=8)
            dpg.add_text("Serves the mkdocs documentation\nsite locally and opens it\nin your browser.",
                         wrap=200, color=hex_to_rgba(palette.text_secondary))

    # =====================================================================
    # Sidebar toggle
    # =====================================================================

    def _toggle_panel(self, panel_name: str) -> None:
        """Toggle sidebar: re-click same icon = collapse, click different = switch."""
        if self._active_panel == panel_name:
            # Re-click: toggle sidebar visibility
            current_show = dpg.get_item_configuration("sidebar").get("show", True)
            dpg.configure_item("sidebar", show=not current_show)
            if current_show:
                self._active_panel = None
        else:
            dpg.configure_item("sidebar", show=True)
            self._show_panel(panel_name)
            self._active_panel = panel_name

    def _show_panel(self, panel_name: str) -> None:
        """Show one sidebar panel, hide all others."""
        for name, group_id in self._sidebar_panels.items():
            if dpg.does_item_exist(group_id):
                dpg.configure_item(group_id, show=(name == panel_name))

    # =====================================================================
    # Clock
    # =====================================================================

    def _update_clock(self) -> None:
        now = datetime.now()
        if self._clock_text and dpg.does_item_exist(self._clock_text):
            dpg.set_value(self._clock_text, now.strftime("%H:%M  %a %d %b"))

    # =====================================================================
    # Rig management
    # =====================================================================

    def _on_rig_click(self, rig) -> None:
        """Clicked a rig button — open it (test connection first) or switch to its tab."""
        rig_name = rig.name
        if rig_name in self.open_rigs:
            # Already open: switch to its tab
            tab_id, _ = self.open_rigs[rig_name]
            if dpg.does_item_exist(tab_id):
                dpg.set_value("rig_tab_bar", tab_id)
            return

        # Test connection in background, then open
        self._set_status(f"Testing {rig_name}...")

        def test_and_open():
            success, message = test_rig_connection(
                rig.board_name, rig.board_type, registry=self.board_registry
            )
            if success:
                call_on_main_thread(self._open_rig_tab, rig=rig)
            else:
                call_on_main_thread(
                    lambda: (
                        show_warning("Connection Failed", f"{rig_name}: {message}"),
                        self._set_status(f"{rig_name}: connection failed"),
                    )
                )

        threading.Thread(target=test_and_open, daemon=True).start()

    def _open_rig_tab(self, rig, simulate: bool = False) -> None:
        """Create a new tab for a rig and build RigWindow content inside it."""
        from .rig_window import RigWindow
        from core.rig_config import RigConfig

        if isinstance(rig, RigConfig):
            base_config = rig
        else:
            base_config = RigConfig.from_dict(rig, processes=self._rigs_file.processes)

        rig_config = RigConfig(
            name=base_config.name, board_name=base_config.board_name,
            board_type=base_config.board_type, enabled=base_config.enabled,
            description=base_config.description, camera_serial=base_config.camera_serial,
            daq_board_name=base_config.daq_board_name, scales=base_config.scales,
            reward_durations=base_config.reward_durations, processes=base_config.processes,
            board_registry_path=str(self.board_registry._path),
            simulate=simulate,
            shared_multi_session=self._shared_multi_session_folder or "",
        )

        rig_name = rig_config.name
        board_name = rig_config.board_name
        try:
            serial_port = self.board_registry.resolve_port(board_name) if board_name else ""
            baud_rate = self.board_registry.resolve_baudrate(board_name, self.baud_rate) if board_name else self.baud_rate
        except (KeyError, RuntimeError):
            serial_port = ""
            baud_rate = self.baud_rate

        # Create tab
        tab_id = dpg.add_tab(
            label=rig_name, parent="rig_tab_bar", closable=True,
            order_mode=dpg.mvTabOrder_Reorderable,
        )

        # Build rig window content inside the tab
        rig_window = RigWindow(
            parent_tab=tab_id,
            serial_port=serial_port,
            baud_rate=baud_rate,
            rig_config=rig_config,
            claim_mouse_fn=self.claim_mouse,
            release_mouse_fn=self.release_mouse,
            get_claimed_mice_fn=self.get_claimed_mice,
            cohort_folders=self._rigs_file.cohort_folders,
            mice=self._rigs_file.mice,
            on_tab_close=lambda name=rig_name: self._on_rig_tab_closed(name),
        )

        self.open_rigs[rig_name] = (tab_id, rig_window)

        # Hide welcome view
        if self._welcome_group and dpg.does_item_exist(self._welcome_group):
            dpg.configure_item(self._welcome_group, show=False)

        # Update sidebar status
        self._update_rig_status(rig_name, "IDLE")
        self._set_status(f"{rig_name} opened")

    def _on_rig_tab_closed(self, rig_name: str) -> None:
        """Called when a rig tab's X is clicked."""
        if rig_name not in self.open_rigs:
            return

        tab_id, rig_window = self.open_rigs[rig_name]

        # Block close if running
        from .rig_window import WindowMode
        if rig_window._current_mode == WindowMode.RUNNING:
            show_warning("Session Running",
                         f"A session is running on {rig_name}.\n"
                         "Stop the session before closing.")
            return

        # Cleanup
        self.release_mouse(rig_name)
        rig_window.controller.close()
        del self.open_rigs[rig_name]

        # Delete tab
        if dpg.does_item_exist(tab_id):
            dpg.delete_item(tab_id)

        # Update sidebar
        self._update_rig_status(rig_name, "OFFLINE")

        # Show welcome if no tabs left
        if not self.open_rigs and self._welcome_group and dpg.does_item_exist(self._welcome_group):
            dpg.configure_item(self._welcome_group, show=True)
            import random as _rnd
            self._welcome_rng_seed = _rnd.randint(0, 999999)  # fresh art
            self._welcome_drawn = False  # force redraw at current size

        self._set_status(f"{rig_name} closed")

    def _update_rig_status(self, rig_name: str, status: str) -> None:
        """Update the status indicator next to a rig button in the sidebar."""
        palette = Theme.palette
        text_id = self.rig_status_texts.get(rig_name)
        if not text_id or not dpg.does_item_exist(text_id):
            return

        status_map = {
            "OFFLINE": ("  o  ", palette.text_disabled),
            "IDLE": ("  o  ", palette.accent_primary),
            "RUNNING": ("  *  ", palette.success),
            "COMPLETE": ("  *  ", palette.info),
            "ERROR": ("  !  ", palette.error),
        }
        text, color = status_map.get(status, ("  ?  ", palette.text_disabled))
        dpg.set_value(text_id, text)
        dpg.configure_item(text_id, color=hex_to_rgba(color))

    # =====================================================================
    # Utility actions
    # =====================================================================

    def _on_zero_scales_click(self) -> None:
        from ScalesLink import zero_all_scales, get_summary
        self._set_status("Zeroing scales...")

        def do_zeroing():
            def progress_cb(rig_name, message):
                call_on_main_thread(self._set_status, message=f"{rig_name}: {message}")
            from dataclasses import asdict
            rig_dicts = [asdict(r) for r in self.rigs]
            results = zero_all_scales(rig_dicts, registry=self.board_registry, callback=progress_cb)
            summary = get_summary(results)
            call_on_main_thread(self._show_zero_results, summary=summary, results=results)

        threading.Thread(target=do_zeroing, daemon=True).start()

    def _show_zero_results(self, summary, results) -> None:
        successful = sum(1 for r in results if r.success)
        total = len([r for r in results if r.message != "No scales configured"])
        self._set_status(f"Zeroing complete: {successful}/{total} successful")
        show_info("Scales Zeroing Results", summary)

    def _on_mock_rig_click(self) -> None:
        mock_name = "Mock Rig"
        if mock_name in self.open_rigs:
            self._set_status("Mock Rig already open")
            return
        if not self.rigs:
            show_warning("No Rigs", "No rigs configured.")
            return
        from dataclasses import replace
        mock_config = replace(self.rigs[0], name=mock_name)
        self._open_rig_tab(mock_config, simulate=True)
        self._set_status("Mock Rig opened (simulated hardware)")

    def _on_docs_click(self) -> None:
        import subprocess as _sp
        project_root = Path(__file__).parent.parent.parent
        mkdocs_config = project_root / "mkdocs.yml"
        if not mkdocs_config.exists():
            show_info("Docs", f"mkdocs.yml not found at:\n{project_root}")
            return
        if getattr(self, "_docs_process", None) is not None and self._docs_process.poll() is None:
            webbrowser.open("http://127.0.0.1:8000")
            return
        try:
            self._docs_process = _sp.Popen(
                [sys.executable, "-m", "mkdocs", "serve", "--no-livereload"],
                cwd=str(project_root), stdout=_sp.DEVNULL, stderr=_sp.PIPE,
            )
            self._set_status("Docs server starting...")
            threading.Thread(target=self._wait_for_docs_server, daemon=True).start()
        except Exception as e:
            show_error("Docs Error", f"Failed to start mkdocs:\n{e}")

    def _wait_for_docs_server(self, timeout: int = 30) -> None:
        import time
        deadline = time.monotonic() + timeout
        proc = self._docs_process
        for line in proc.stderr:
            if b"Serving on" in line:
                call_on_main_thread(lambda: webbrowser.open("http://127.0.0.1:8000"))
                call_on_main_thread(self._set_status, message="Docs server started")
                return
            if time.monotonic() > deadline:
                break
        call_on_main_thread(self._set_status, message="Docs server failed to start")

    def _on_post_processing_click(self) -> None:
        if self.open_rigs:
            open_names = ", ".join(self.open_rigs.keys())
            show_warning("Rigs Open",
                         f"Cannot open post-processing while rigs are open.\n\n"
                         f"Currently open: {open_names}")
            return
        from .post_processing_window import open_post_processing_window
        self._set_status("Opening post-processing...")
        open_post_processing_window(self._rigs_file.cohort_folders)

    # =====================================================================
    # Mouse claims
    # =====================================================================

    def claim_mouse(self, mouse_id: str, rig_name: str) -> bool:
        return self._mouse_claims.try_claim(mouse_id, rig_name)

    def release_mouse(self, rig_name: str) -> None:
        self._mouse_claims.release_all(rig_name)

    def get_claimed_mice(self) -> dict[str, str]:
        return self._mouse_claims.get_all()

    # =====================================================================
    # Helpers
    # =====================================================================

    def _set_status(self, message: str) -> None:
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.set_value(self._status_text, message)

    def cleanup(self) -> None:
        """Called on shutdown — close all rigs, stop docs server."""
        for rig_name in list(self.open_rigs.keys()):
            _, rig_window = self.open_rigs[rig_name]
            try:
                rig_window.controller.close()
            except Exception as e:
                print(f"Warning: error closing {rig_name}: {e}")
        if getattr(self, "_docs_process", None) is not None:
            try:
                self._docs_process.terminate()
            except Exception:
                pass
