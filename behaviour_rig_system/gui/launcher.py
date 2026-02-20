"""
Rig Launcher Window.

Provides a simple launcher interface for selecting and connecting to
multiple behaviour rigs. Each rig gets its own control window.

Supports linked sessions where multiple rigs share a common multi-session folder.
"""

from __future__ import annotations

import os
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
from .theme import apply_theme, Theme, style_rig_button, create_rig_button

if TYPE_CHECKING:
    from .rig_window import RigWindow


# Default rig configuration if config file not found
DEFAULT_RIGS = [
    {"name": "Rig 1", "board_name": "rig_1_behaviour", "enabled": True},
    {"name": "Rig 2", "board_name": "rig_2_behaviour", "enabled": True},
    {"name": "Rig 3", "board_name": "rig_3_behaviour", "enabled": True},
    {"name": "Rig 4", "board_name": "rig_4_behaviour", "enabled": True},
]


def load_rig_config(config_path: Path) -> tuple[list[dict], int, dict]:
    """
    Load rig configuration from rigs.yaml.
    
    Args:
        config_path: Path to the configuration file
    
    Returns:
        Tuple of (list of rig configs, baud rate, processes config)
    """
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        rigs = config.get("rigs", DEFAULT_RIGS)
        baud_rate = config.get("global", {}).get("baud_rate", 115200)
        processes = config.get("processes", {})
        return rigs, baud_rate, processes
    
    return DEFAULT_RIGS, 115200, {}


def test_rig_connection(
    board_name: str,
    board_type: str = "giga",
    registry: BoardRegistry | None = None,
) -> tuple[bool, str]:
    """
    Test connection to a rig by resolving its board name via the registry.
    
    Args:
        board_name: Human-readable board key (e.g. "rig_1_behaviour")
        board_type: Board type string ("mega" or "giga")
        registry: Optional pre-loaded BoardRegistry instance.
        
    Returns:
        Tuple of (success, message)
    """
    ser = None
    link = None
    
    try:
        # Resolve board name to COM port
        reg = registry or BoardRegistry()
        serial_port = reg.find_board_port(board_name)
        baud_rate = reg.get_baudrate(board_name)
        
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
    
    def __init__(self, config_path: Path):
        self.root = tk.Tk()
        self.root.title("Behaviour Rig Launcher")
        self.root.geometry("420x460")
        self.root.resizable(False, False)
        
        # Apply modern theme
        apply_theme(self.root)
        
        # Store config path for passing to child windows
        self.config_path = config_path
        
        # Load configuration
        self.rigs, self.baud_rate, self.processes = load_rig_config(config_path)
        
        # Load board registry for resolving board names to COM ports
        registry_path = config_path.parent / "board_registry.json"
        try:
            self.board_registry = BoardRegistry(registry_path)
        except FileNotFoundError:
            self.board_registry = BoardRegistry()
        
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
        
        # Main container with padding
        main_container = ttk.Frame(self.root, padding=(16, 10))
        main_container.pack(fill="both", expand=True)
        
        # Header section with clock
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 6))
        
        # Clock and date
        clock_frame = ttk.Frame(header_frame)
        clock_frame.pack()
        
        self._clock_var = tk.StringVar(value="--:--")
        clock_label = ttk.Label(
            clock_frame,
            textvariable=self._clock_var,
            font=(Theme.FONT_FAMILY, 26, "bold"),
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
        ttk.Separator(main_container, orient="horizontal").pack(fill="x", pady=6)
        
        # Title
        title_label = ttk.Label(
            main_container,
            text="Behaviour Rig System",
            style="Heading.TLabel"
        )
        title_label.pack(pady=(3, 2))
        
        # Instructions
        instructions = ttk.Label(
            main_container,
            text="Select rigs to launch:",
            style="Muted.TLabel"
        )
        instructions.pack(pady=(0, 8))
        
        # Store main_container for use in other widget creation
        self._main_container = main_container
        
        # Rig selection frame (toggle buttons in 2x2 grid)
        button_frame = ttk.Frame(self._main_container)
        button_frame.pack(pady=6, fill="both", expand=True)
        
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
            btn.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            
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
        self.root.update()
        
        def do_zeroing():
            def progress_callback(rig_name: str, message: str):
                # Update status in main thread
                self.root.after(0, lambda: self.status_var.set(f"{rig_name}: {message}"))
            
            results = zero_all_scales(self.rigs, callback=progress_callback)
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
        self._update_button_appearance(rig_name)
        
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

    def _update_button_appearance(self, rig_name: str) -> None:
        """Update button appearance based on selection and open state."""
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
            rig_name = rig.get("name", f"Rig {self.rigs.index(rig)+1}")
            if self.rig_selected.get(rig_name, False):
                # Check if already open
                if rig_name in self.open_windows:
                    continue
                selected_rigs.append(rig)
        
        if not selected_rigs:
            messagebox.showinfo("No Rigs Selected", "Please select at least one rig to launch.")
            return
        
        # Create shared multi-session folder timestamp
        date_time = datetime.now().strftime("%y%m%d_%H%M%S")
        self._shared_multi_session_folder = date_time
        
        # Disable launch button during connection tests
        self._launch_selected_btn.configure(state="disabled")
        
        self.status_var.set(f"Testing connections to {len(selected_rigs)} rig(s)...")
        self.root.update()
        
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
            self._update_button_appearance(rig_name)
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
        self.root.update()

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
                self._update_button_appearance(rig_name)

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
            "shared_multi_session": shared_multi_session,
        }
        
        # Resolve board name to COM port via registry
        try:
            serial_port = self.board_registry.find_board_port(board_name) if board_name else ""
            baud_rate = self.board_registry.get_baudrate(board_name) if board_name else self.baud_rate
        except (KeyError, RuntimeError):
            serial_port = ""
            baud_rate = self.baud_rate
        
        # Create RigWindow content in the toplevel
        rig_window = RigWindow(
            serial_port=serial_port,
            baud_rate=baud_rate,
            parent=window,
            rig_name=rig_name,
            rig_config=rig_config,
            simulate=simulate,
        )
        
        # Track this window (including rig_window for session checking)
        btn = self.rig_buttons.get(rig_name)
        self.open_windows[rig_name] = (window, btn, rig_window)
        
        # Update button appearance to show it's open (grayed out)
        self._update_button_appearance(rig_name)
        
        # Handle window close
        def on_window_close():
            self._on_rig_window_close(rig_name)
        
        window.protocol("WM_DELETE_WINDOW", on_window_close)
        
        self.status_var.set(f"{rig_name} opened")
    
    def _on_rig_window_close(self, rig_name: str) -> None:
        """Handle a rig window being closed."""
        if rig_name in self.open_windows:
            window, btn, rig_window = self.open_windows[rig_name]
            
            # Check if a session is running
            if rig_window.current_protocol is not None and rig_window.current_protocol.is_running:
                messagebox.showwarning(
                    "Session Running",
                    f"A session is currently running on {rig_name}.\n\n"
                    "Please stop the session before closing the window."
                )
                return
            
            # Clean up the rig window
            rig_window._cleanup_session()
            
            # Destroy the window
            try:
                window.destroy()
            except:
                pass
            
            # Remove from tracking
            del self.open_windows[rig_name]
            
            # Update button appearance (restore to normal unselected state)
            self.rig_selected[rig_name] = False
            self._update_button_appearance(rig_name)
            
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
                rig_window._cleanup_session()
                window.destroy()
            except:
                pass
        
        self.root.destroy()
    
    def run(self) -> None:
        """Start the launcher main loop."""
        self.root.mainloop()


def launch(config_path: Path):
    """Launch the rig launcher."""
    launcher = RigLauncher(config_path)
    launcher.run()
