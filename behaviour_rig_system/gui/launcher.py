"""
Rig Launcher Window.

Provides a simple launcher interface for selecting and connecting to
multiple behaviour rigs. Each rig gets its own control window.

Supports linked sessions where multiple rigs share a common multi-session folder.
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

import serial
import yaml
from pathlib import Path

from BehavLink import BehaviourRigLink, reset_arduino_via_dtr
from core.board_registry import BoardRegistry
from .launcher_background import draw_background
from .theme import apply_theme, Theme, style_rig_button, create_rig_button

if TYPE_CHECKING:
    from .rig_window import RigWindow


def test_rig_connection(
    board_name: str,
    board_type: str = "giga",
    registry: BoardRegistry = None,
) -> tuple[bool, str]:
    """
    Test connection to a rig by resolving its board name via the registry.
    
    Args:
        board_name: Human-readable board key (e.g. "rig_1_behaviour")
        board_type: Board type string ("mega" or "giga")
        registry: Pre-loaded BoardRegistry instance.
        
    Returns:
        Tuple of (success, message)
    """
   
    ser = None
    link = None
    
    try:
        # Resolve board name (or raw COM port) to a port string
        serial_port = registry.resolve_port(board_name)
        baud_rate = registry.resolve_baudrate(board_name)
        
        # Try to open serial port
        ser = serial.Serial(serial_port, baud_rate, timeout=0.1)
        
        # Reset Arduino
        reset_arduino_via_dtr(ser)
        
        # Create link and test handshake
        link = BehaviourRigLink(ser, board_type=board_type)
        link.start()
        
        link.send_hello()
        link.wait_hello(timeout=3.0)
        
        # Success - clean up
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
        # Clean up on failure
        if link:
            try:
                link.stop()
            except:
                pass
        if ser and ser.is_open:
            try:
                ser.close()
            except:
                pass


class RigLauncher:
    """
    Launcher window for selecting and connecting to behaviour rigs.
    
    Shows buttons for each configured rig. Clicking a button tests the
    connection and opens the rig's control window if successful.
    """
    
    def __init__(self, config_path: Path, board_registry_path: Path):
        # Store config path for passing to child windows
        self.config_path = config_path

        # Load configuration first (needed for theme)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Rig configuration file not found: {config_path}"
            )

        with open(config_path) as f:
            config = yaml.safe_load(f)

        if "rigs" not in config:
            raise KeyError("'rigs' section missing from config file")
        if "global" not in config or "baud_rate" not in config["global"]:
            raise KeyError("'global.baud_rate' missing from config file")
        if "processes" not in config:
            raise KeyError("'processes' section missing from config file")

        # Apply palette from config before creating any widgets
        from .theme import PALETTES, BORING_PALETTE
        palette_name = config.get("global", {}).get("palette", "boring")
        if palette_name in PALETTES:
            Theme.set_palette(PALETTES[palette_name])
        else:
            available = ", ".join(sorted(PALETTES.keys()))
            print(f"WARNING: Unknown palette '{palette_name}'. Available palettes: {available}")
            print("  Falling back to 'boring' palette.")
            Theme.set_palette(BORING_PALETTE)

        self.root = tk.Tk()
        self.root.title("Behaviour Rig Launcher")
        self.root.geometry("440x480")
        self.root.resizable(False, False)

        # Apply theme
        apply_theme(self.root)

        self.rigs = config["rigs"]
        self.baud_rate = config["global"]["baud_rate"]
        self.processes = config["processes"]
        
        # Load board registry for resolving board names to COM ports
        self.board_registry = BoardRegistry(board_registry_path)
        
        # Track open rig windows: {rig_name: (window, button, rig_window)}
        self.open_windows: dict[str, tuple[tk.Toplevel, tk.Button, "RigWindow"]] = {}
        
        # Track buttons for enabling/disabling
        self.rig_buttons: dict[str, tk.Button] = {}
        
        # Track selection state for each rig
        self.rig_selected: dict[str, bool] = {}

        # Clock update ID
        self._clock_update_id: str | None = None
        
        # Shared multi-session folder for linked sessions
        self._shared_multi_session_folder: str | None = None

        # Track which mice are claimed by which rigs: {mouse_id: rig_name}
        self._claimed_mice: dict[str, str] = {}

        self._create_widgets()
        self._update_clock()
        
        # Handle main window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _update_clock(self) -> None:
        """Update the clock display."""
        from datetime import datetime
        now = datetime.now()
        self._clock_var.set(now.strftime("%H:%M"))
        self._date_var.set(now.strftime("%A, %d %B %Y"))
        self._clock_update_id = self.root.after(1000, self._update_clock)
    
    def _create_widgets(self) -> None:
        """Create the launcher widgets."""
        palette = Theme.palette
        
        # Background canvas with daily generative art — also acts as
        # the main layout container so art is visible between widgets.
        self._bg_canvas = tk.Canvas(
            self.root, highlightthickness=0, bg=palette.bg_primary
        )
        self._bg_canvas.pack(fill="both", expand=True)
        draw_background(self._bg_canvas, 440, 480)
        
        # Header section with clock
        header_frame = ttk.Frame(self._bg_canvas)
        header_frame.pack(pady=(10, 6))
        
        # Clock and date
        clock_frame = ttk.Frame(header_frame)
        clock_frame.pack()
        
        self._clock_var = tk.StringVar(value="--:--")
        clock_label = ttk.Label(
            clock_frame,
            textvariable=self._clock_var,
            font=Theme.font(size=26, weight="bold"),
            foreground=palette.accent_primary
        )
        clock_label.pack()
        
        self._date_var = tk.StringVar(value="")
        date_label = ttk.Label(
            clock_frame,
            textvariable=self._date_var,
            style="Muted.TLabel"
        )
        date_label.pack()
        
        # Separator
        ttk.Separator(self._bg_canvas, orient="horizontal").pack(fill="x", pady=6)
        
        # Title
        title_label = ttk.Label(
            self._bg_canvas,
            text="Hex Behaviour Launcher",
            style="Heading.TLabel",
            font=Theme.font_special(24)
        )
        title_label.pack(pady=(3, 2))
        
        # Instructions
        instructions = ttk.Label(
            self._bg_canvas,
            text="Select rigs to launch:",
            style="Muted.TLabel"
        )
        instructions.pack(pady=(0, 8))
        
        # Use canvas as the main container so art shows between widgets
        self._main_container = self._bg_canvas
        
        # Rig selection frame (toggle buttons in 2x2 grid)
        button_frame = ttk.Frame(self._main_container)
        button_frame.pack(pady=(10, 10), padx=40)
        
        # Create a toggle button for each rig (2x2 grid)
        for i, rig in enumerate(self.rigs[:4]):  # Max 4 rigs
            row = i // 2
            col = i % 2
            
            rig_name = rig.get("name", f"Rig {i+1}")
            enabled = rig.get("enabled", True)
            
            # Selection state
            self.rig_selected[rig_name] = False
            
            # Create toggle button using themed rig button
            btn = create_rig_button(
                button_frame,
                text=rig_name,
                command=lambda r=rig: self._on_rig_toggle(r),
            )
            btn.grid(row=row, column=col, padx=10, pady=8, sticky="nsew")
            
            # Store reference
            self.rig_buttons[rig_name] = btn
            
            # Disable if not enabled in config
            if not enabled:
                style_rig_button(btn, is_open=True)
                btn.configure(state="disabled")
        
        # Configure grid weights for even distribution
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.rowconfigure(0, weight=1)
        button_frame.rowconfigure(1, weight=1)
        
        # Separator before buttons
        ttk.Separator(self._main_container, orient="horizontal").pack(fill="x", pady=6)
        
        # Launch Selected button
        launch_frame = ttk.Frame(self._main_container)
        launch_frame.pack(pady=(3, 6))
        
        self._launch_selected_btn = ttk.Button(
            launch_frame,
            text="Launch Selected Rigs",
            command=self._on_launch_selected_click,
            style="Primary.TButton",
            state="disabled",  # Disabled until rigs are selected
        )
        self._launch_selected_btn.pack(pady=3)

        # Utility buttons frame
        utility_frame = ttk.Frame(self._main_container)
        utility_frame.pack(pady=(3, 6))

        # Zero Scales button
        zero_btn = ttk.Button(
            utility_frame,
            text="Zero All Scales",
            command=self._on_zero_scales_click,
            style="Secondary.TButton",
        )
        zero_btn.pack(side="left", padx=5)
        self._zero_btn = zero_btn

        # Post Processing button
        post_process_btn = ttk.Button(
            utility_frame,
            text="Post Processing",
            command=self._on_post_processing_click,
            style="Secondary.TButton",
        )
        post_process_btn.pack(side="left", padx=5)
        self._post_process_btn = post_process_btn

        # Mock Rig button
        mock_btn = ttk.Button(
            utility_frame,
            text="Mock Rig",
            command=self._on_mock_rig_click,
            style="Secondary.TButton",
        )
        mock_btn.pack(side="left", padx=5)
        self._mock_btn = mock_btn

        # Docs button
        docs_btn = ttk.Button(
            utility_frame,
            text="Docs",
            command=self._on_docs_click,
            style="Secondary.TButton",
        )
        docs_btn.pack(side="left", padx=5)
        
        # Status bar at bottom
        status_frame = ttk.Frame(self._main_container)
        status_frame.pack(fill="x", pady=(8, 0))
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            style="Muted.TLabel"
        )
        status_label.pack()
    
    def _on_zero_scales_click(self) -> None:
        """Handle zero scales button click."""
        from ScalesLink import zero_all_scales, get_summary
        
        # Disable button
        self._zero_btn.configure(state="disabled")
        self.status_var.set("Zeroing scales...")
        self.root.update_idletasks()
        
        def do_zeroing():
            def progress_callback(rig_name: str, message: str):
                # Update status in main thread
                self.root.after(0, lambda: self.status_var.set(f"{rig_name}: {message}"))
            
            results = zero_all_scales(self.rigs, registry=self.board_registry, callback=progress_callback)
            summary = get_summary(results)
            
            # Show results in main thread
            self.root.after(0, lambda: self._show_zero_results(summary, results))
        
        thread = threading.Thread(target=do_zeroing, daemon=True)
        thread.start()
    
    def _show_zero_results(self, summary: str, results) -> None:
        """Show zeroing results and re-enable button."""
        self._zero_btn.configure(state="normal")

        successful = sum(1 for r in results if r.success)
        total = len([r for r in results if r.message != "No scales configured"])

        self.status_var.set(f"Zeroing complete: {successful}/{total} successful")

        messagebox.showinfo("Scales Zeroing Results", summary)

    def _on_rig_toggle(self, rig: dict) -> None:
        """Handle rig button toggle for selection."""
        rig_name = rig.get("name", "Unknown")
        
        # Don't allow selection if rig is already open
        if rig_name in self.open_windows:
            return
        
        # Toggle selection state
        self.rig_selected[rig_name] = not self.rig_selected.get(rig_name, False)
        
        # Update button appearance
        self._style_rig_button_state(rig_name)
        
        # Update launch button state
        self._update_launch_button()

    def _on_mock_rig_click(self) -> None:
        """Open a mock rig window using the first rig's config (no hardware required)."""
        mock_name = "Mock Rig"

        # Don't open twice
        if mock_name in self.open_windows:
            self.status_var.set("Mock Rig already open")
            return

        # Use the first rig's config as a template
        if not self.rigs:
            messagebox.showwarning("No Rigs", "No rigs configured in rigs.yaml")
            return

        rig = dict(self.rigs[0])  # shallow copy
        rig["name"] = mock_name

        self._open_rig_window(rig, simulate=True)
        self.status_var.set("Mock Rig opened (simulated hardware)")

    def _on_docs_click(self) -> None:
        """Serve the documentation site locally and open it in the browser."""
        import subprocess as _sp
        import webbrowser

        project_root = Path(__file__).parent.parent.parent
        mkdocs_config = project_root / "mkdocs.yml"

        if not mkdocs_config.exists():
            messagebox.showinfo("Docs", f"mkdocs.yml not found at:\n{project_root}")
            return

        # Check if mkdocs server is already running
        if getattr(self, "_docs_process", None) is not None and self._docs_process.poll() is None:
            webbrowser.open("http://127.0.0.1:8000")
            return

        try:
            self._docs_process = _sp.Popen(
                [sys.executable, "-m", "mkdocs", "serve", "--no-livereload"],
                cwd=str(project_root),
                stdout=_sp.DEVNULL,
                stderr=_sp.PIPE,
            )
            self.status_var.set("Docs server starting...")
            import threading
            threading.Thread(target=self._wait_for_docs_server, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Docs Error", f"Failed to start mkdocs:\n{e}")

    def _wait_for_docs_server(self, timeout: int = 30) -> None:
        """Wait for mkdocs to print its 'Serving on' line, then open the browser."""
        import time
        import webbrowser
        deadline = time.monotonic() + timeout
        proc = self._docs_process
        for line in proc.stderr:
            if b"Serving on" in line:
                self.root.after(0, lambda: webbrowser.open("http://127.0.0.1:8000"))
                self.root.after(0, lambda: self.status_var.set("Docs server started at http://127.0.0.1:8000"))
                return
            if time.monotonic() > deadline:
                break
        self.root.after(0, lambda: self.status_var.set("Docs server failed to start within 30s."))

    def _style_rig_button_state(self, rig_name: str) -> None:
        """Style a rig button to reflect its current selection and open state."""
        btn = self.rig_buttons.get(rig_name)
        if not btn:
            return
        
        is_open = rig_name in self.open_windows
        is_selected = self.rig_selected.get(rig_name, False)
        
        style_rig_button(btn, is_selected=is_selected, is_open=is_open)

    def _update_launch_button(self) -> None:
        """Update launch button state based on selections."""
        selected_count = sum(1 for selected in self.rig_selected.values() if selected)
        
        if selected_count > 0:
            self._launch_selected_btn.configure(state="normal", style="Primary.TButton")
            self._launch_selected_btn.configure(text=f"Launch {selected_count} Rig{'s' if selected_count > 1 else ''}")
        else:
            self._launch_selected_btn.configure(state="disabled")
            self._launch_selected_btn.configure(text="Launch Selected Rigs")

    def _on_launch_selected_click(self) -> None:
        """Handle launch selected rigs button click."""
        # Get selected rigs
        selected_rigs = []
        for rig in self.rigs:
            rig_name = rig.get("name", "Unknown")
            if self.rig_selected.get(rig_name, False):
                # Check if already open
                if rig_name in self.open_windows:
                    continue
                selected_rigs.append(rig)
        
        # Create shared multi-session folder timestamp
        date_time = datetime.now().strftime("%y%m%d_%H%M%S")
        self._shared_multi_session_folder = date_time
        
        # Disable launch button during connection tests
        self._launch_selected_btn.configure(state="disabled")
        
        self.status_var.set(f"Testing connections to {len(selected_rigs)} rig(s)...")
        self.root.update_idletasks()
        
        # Test connections and open windows sequentially
        def test_and_open_all():
            successful_rigs = []
            failed_rigs = []
            
            for rig in selected_rigs:
                rig_name = rig.get("name", "Unknown")
                board_name = rig.get("board_name", "")
                board_type = rig.get("board_type", "giga")
                
                self.root.after(0, lambda n=rig_name: self.status_var.set(f"Testing {n}..."))
                
                success, message = test_rig_connection(
                    board_name, board_type, registry=self.board_registry
                )
                
                if success:
                    successful_rigs.append(rig)
                else:
                    failed_rigs.append((rig, message))
            
            # Open windows in main thread
            self.root.after(0, lambda: self._handle_multi_connection_result(
                successful_rigs, failed_rigs
            ))
        
        thread = threading.Thread(target=test_and_open_all, daemon=True)
        thread.start()

    def _handle_multi_connection_result(
        self, successful_rigs: list, failed_rigs: list
    ) -> None:
        """Handle the result of multiple connection tests."""
        # Clear selections and update button appearances
        for rig_name in self.rig_selected:
            self.rig_selected[rig_name] = False
            self._style_rig_button_state(rig_name)
        self._update_launch_button()
        
        # Report failures
        if failed_rigs:
            failure_msgs = "\n".join([
                f"  • {rig.get('name', 'Unknown')}: {msg}"
                for rig, msg in failed_rigs
            ])
            messagebox.showwarning(
                "Some Connections Failed",
                f"Could not connect to the following rigs:\n\n{failure_msgs}"
            )
        
        # Open successful rigs
        if successful_rigs:
            for rig in successful_rigs:
                self._open_rig_window(rig, shared_multi_session=self._shared_multi_session_folder)
            
            rig_names = ", ".join([r.get("name", "Unknown") for r in successful_rigs])
            self.status_var.set(f"Opened: {rig_names}")
        else:
            self.status_var.set("No rigs connected")
            self._shared_multi_session_folder = None

    def _on_post_processing_click(self) -> None:
        """Handle post processing button click."""
        # Check if any rig windows are open
        if self.open_windows:
            open_rigs = ", ".join(self.open_windows.keys())
            messagebox.showwarning(
                "Rigs Open",
                f"Cannot open post-processing while rig windows are open.\n\n"
                f"Currently open rigs: {open_rigs}\n\n"
                f"Please close all rig windows before opening post-processing."
            )
            return

        from .post_processing_window import open_post_processing_window

        self.status_var.set("Opening post-processing window...")
        self.root.update_idletasks()

        # Disable launcher while post-processing is open
        self._disable_launcher()

        # Open the post-processing window (modal)
        open_post_processing_window(self.root, self.config_path)

        # Re-enable launcher when post-processing closes
        self._enable_launcher()

        self.status_var.set("Ready")

    def _disable_launcher(self) -> None:
        """Disable launcher controls while post-processing is open."""
        # Disable all rig buttons (these are tk.Button, use style_rig_button)
        for btn in self.rig_buttons.values():
            style_rig_button(btn, is_open=True)
            btn.configure(state="disabled")

        # Disable utility buttons (these are ttk.Button, just disable them)
        self._zero_btn.configure(state="disabled")
        self._post_process_btn.configure(state="disabled")
        
        # Disable launch button
        self._launch_selected_btn.configure(state="disabled")

    def _enable_launcher(self) -> None:
        """Re-enable launcher controls after post-processing closes."""
        # Re-enable rig buttons (if they were originally enabled)
        for rig in self.rigs:
            rig_name = rig.get("name", f"Rig {self.rigs.index(rig)+1}")
            enabled = rig.get("enabled", True)
            if enabled:
                # Update button appearance based on current state
                self._style_rig_button_state(rig_name)

        # Re-enable utility buttons
        self._zero_btn.configure(state="normal")
        self._post_process_btn.configure(state="normal")
        
        # Update launch button state
        self._update_launch_button()
    
    def _open_rig_window(self, rig: dict, shared_multi_session: str | None = None, simulate: bool = False) -> None:
        """
        Open a control window for the specified rig.
        
        Args:
            rig: Rig configuration dictionary
            shared_multi_session: Optional shared multi-session folder timestamp.
                                  If provided, all rigs with the same value will
                                  save to the same parent folder.
            simulate: If True, use mock peripherals instead of real hardware.
        """
        from .rig_window import RigWindow
        
        rig_name = rig.get("name", "Unknown")
        board_name = rig.get("board_name", "")
        
        # Create new window
        window = tk.Toplevel(self.root)
        
        # Combine rig config with processes config and config path for RigWindow
        rig_config = {
            **rig,
            "processes": self.processes,
            "config_path": self.config_path,
            "board_registry_path": self.board_registry._path,
            "shared_multi_session": shared_multi_session,
            "claim_mouse_fn": self.claim_mouse,
            "release_mouse_fn": self.release_mouse,
            "get_claimed_mice_fn": self.get_claimed_mice,
        }
        
        # Resolve board name (or raw COM port) via registry
        try:
            serial_port = self.board_registry.resolve_port(board_name) if board_name else ""
            baud_rate = self.board_registry.resolve_baudrate(board_name, self.baud_rate) if board_name else self.baud_rate
        except (KeyError, RuntimeError):
            serial_port = ""
            baud_rate = self.baud_rate
        
        # Create RigWindow content in the toplevel
        rig_window = RigWindow(
            serial_port=serial_port,
            baud_rate=baud_rate,
            parent=window,
            rig_config=rig_config,
            simulate=simulate,
        )
        
        # Track this window (including rig_window for session checking)
        btn = self.rig_buttons.get(rig_name)
        self.open_windows[rig_name] = (window, btn, rig_window)
        
        # Update button appearance to show it's open (grayed out)
        self._style_rig_button_state(rig_name)
        
        # Handle window close (via X button)
        def on_window_close():
            self._on_rig_window_close(rig_name)

        window.protocol("WM_DELETE_WINDOW", on_window_close)

        # Handle programmatic destroy (e.g. from post-session close button)
        def on_window_destroyed(event):
            if event.widget is window and rig_name in self.open_windows:
                self.release_mouse(rig_name)
                del self.open_windows[rig_name]
                self.rig_selected[rig_name] = False
                self._style_rig_button_state(rig_name)
                self.status_var.set(f"{rig_name} closed")

        window.bind("<Destroy>", on_window_destroyed)
        
        self.status_var.set(f"{rig_name} opened")
    
    def claim_mouse(self, mouse_id: str, rig_name: str) -> bool:
        """Claim a mouse for a rig. Returns False if already claimed by another rig."""
        if mouse_id in self._claimed_mice and self._claimed_mice[mouse_id] != rig_name:
            return False
        self._claimed_mice[mouse_id] = rig_name
        return True

    def release_mouse(self, rig_name: str) -> None:
        """Release all mice claimed by a rig."""
        self._claimed_mice = {m: r for m, r in self._claimed_mice.items() if r != rig_name}

    def get_claimed_mice(self) -> dict[str, str]:
        """Return a copy of claimed mice: {mouse_id: rig_name}."""
        return dict(self._claimed_mice)

    def _on_rig_window_close(self, rig_name: str) -> None:
        """Handle a rig window being closed."""
        if rig_name not in self.open_windows:
            return  # Already cleaned up by <Destroy> handler

        if rig_name in self.open_windows:
            window, btn, rig_window = self.open_windows[rig_name]

            # Check if a session is running
            if rig_window.controller.is_running:
                messagebox.showwarning(
                    "Session Running",
                    f"A session is currently running on {rig_name}.\n\n"
                    "Please stop the session before closing the window."
                )
                return
            
            # Release any claimed mice
            self.release_mouse(rig_name)

            # Clean up the rig window
            rig_window.controller.close()

            # Remove from tracking BEFORE destroy (destroy triggers <Destroy> handler)
            del self.open_windows[rig_name]

            # Destroy the window
            try:
                window.destroy()
            except Exception:
                pass

            # Update button appearance (restore to normal unselected state)
            self.rig_selected[rig_name] = False
            self._style_rig_button_state(rig_name)
            
            self.status_var.set(f"{rig_name} closed")
    
    def _on_close(self) -> None:
        """Handle launcher window close."""
        # Warn if rig windows are still open
        if self.open_windows:
            open_rigs = ", ".join(self.open_windows.keys())
            result = messagebox.askyesno(
                "Confirm Close",
                f"The following rig windows are still open:\n\n{open_rigs}\n\n"
                "Closing the launcher will close all rig windows.\n"
                "If a session is running, it may be interrupted.\n\n"
                "Are you sure you want to close?",
                icon="warning"
            )
            if not result:
                return
        
        # Cancel clock update
        if self._clock_update_id:
            self.root.after_cancel(self._clock_update_id)
        
        # Close all open rig windows
        for rig_name in list(self.open_windows.keys()):
            window, _, rig_window = self.open_windows[rig_name]
            try:
                rig_window.controller.close()
                window.destroy()
            except:
                pass
        
        # Stop docs server if running
        if getattr(self, "_docs_process", None) is not None:
            try:
                self._docs_process.terminate()
            except Exception:
                pass

        self.root.destroy()
    
    def run(self) -> None:
        """Start the launcher main loop."""
        self.root.mainloop()


def launch(config_path: Path, board_registry_path: Path):
    """Launch the rig launcher."""
    launcher = RigLauncher(config_path, board_registry_path)
    launcher.run()
