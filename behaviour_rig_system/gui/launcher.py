"""
Rig Launcher Window.

Provides a simple launcher interface for selecting and connecting to
multiple behaviour rigs. Each rig gets its own control window.
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

import serial
import yaml
from pathlib import Path

from BehavLink import BehaviourRigLink, reset_arduino_via_dtr


# Default rig configuration if config file not found
DEFAULT_RIGS = [
    {"name": "Rig 1", "serial_port": "COM7", "enabled": True},
    {"name": "Rig 2", "serial_port": "COM8", "enabled": True},
    {"name": "Rig 3", "serial_port": "COM9", "enabled": True},
    {"name": "Rig 4", "serial_port": "COM10", "enabled": True},
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


def test_rig_connection(serial_port: str, baud_rate: int) -> tuple[bool, str]:
    """
    Test connection to a rig.
    
    Args:
        serial_port: Serial port to test
        baud_rate: Baud rate for connection
        
    Returns:
        Tuple of (success, message)
    """
    ser = None
    link = None
    
    try:
        # Try to open serial port
        ser = serial.Serial(serial_port, baud_rate, timeout=0.1)
        
        # Reset Arduino
        reset_arduino_via_dtr(ser)
        
        # Create link and test handshake
        link = BehaviourRigLink(ser)
        link.start()
        
        link.send_hello()
        link.wait_hello(timeout=3.0)
        
        # Success - clean up
        link.stop()
        ser.close()
        
        return True, "Connection successful!"
        
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
        self.root.geometry("400x350")
        self.root.resizable(False, False)
        
        # Store config path for passing to child windows
        self.config_path = config_path
        
        # Load configuration
        self.rigs, self.baud_rate, self.processes = load_rig_config(config_path)
        
        # Track open rig windows: {rig_name: (window, button)}
        self.open_windows: dict[str, tuple[tk.Toplevel, ttk.Button]] = {}
        
        # Track buttons for enabling/disabling
        self.rig_buttons: dict[str, ttk.Button] = {}
        
        self._create_widgets()
        
        # Handle main window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self) -> None:
        """Create the launcher widgets."""
        # Title
        title_label = ttk.Label(
            self.root,
            text="Behaviour Rig System",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(pady=20)
        
        # Instructions
        instructions = ttk.Label(
            self.root,
            text="Select a rig to connect:",
            font=("Helvetica", 10)
        )
        instructions.pack(pady=(0, 15))
        
        # Rig buttons frame
        button_frame = ttk.Frame(self.root)
        button_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Create a button for each rig (2x2 grid)
        for i, rig in enumerate(self.rigs[:4]):  # Max 4 rigs
            row = i // 2
            col = i % 2
            
            rig_name = rig.get("name", f"Rig {i+1}")
            serial_port = rig.get("serial_port", f"COM{7+i}")
            enabled = rig.get("enabled", True)
            
            # Create button
            btn = ttk.Button(
                button_frame,
                text=rig_name,
                command=lambda r=rig: self._on_rig_click(r),
                width=18,
            )
            btn.grid(row=row, column=col, padx=10, pady=10, ipady=15)
            
            # Store reference
            self.rig_buttons[rig_name] = btn
            
            # Disable if not enabled in config
            if not enabled:
                btn.configure(state="disabled")
        
        # Configure grid weights for centering
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        # Status label at bottom
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Helvetica", 9)
        )
        status_label.pack(pady=15)
    
    def _on_rig_click(self, rig: dict) -> None:
        """Handle rig button click."""
        rig_name = rig.get("name", "Unknown")
        serial_port = rig.get("serial_port", "")
        
        # Check if already open
        if rig_name in self.open_windows:
            messagebox.showinfo("Already Open", f"{rig_name} is already open.")
            return
        
        # Disable button and show testing status
        btn = self.rig_buttons.get(rig_name)
        if btn:
            btn.configure(state="disabled")
        
        self.status_var.set(f"Testing connection to {rig_name}...")
        self.root.update()
        
        # Test connection in background thread
        def test_and_open():
            success, message = test_rig_connection(serial_port, self.baud_rate)
            
            # Update UI in main thread
            self.root.after(0, lambda: self._handle_connection_result(
                rig, success, message
            ))
        
        thread = threading.Thread(target=test_and_open, daemon=True)
        thread.start()
    
    def _handle_connection_result(
        self, rig: dict, success: bool, message: str
    ) -> None:
        """Handle the result of a connection test."""
        rig_name = rig.get("name", "Unknown")
        serial_port = rig.get("serial_port", "")
        btn = self.rig_buttons.get(rig_name)
        
        if success:
            self.status_var.set(f"{rig_name}: Connected!")
            
            # Open the rig control window
            self._open_rig_window(rig)
        else:
            self.status_var.set(f"{rig_name}: {message}")
            messagebox.showerror(
                "Connection Failed",
                f"Could not connect to {rig_name} on {serial_port}:\n\n{message}"
            )
            
            # Re-enable button
            if btn:
                btn.configure(state="normal")
    
    def _open_rig_window(self, rig: dict) -> None:
        """Open a control window for the specified rig."""
        from .rig_window import RigWindow
        
        rig_name = rig.get("name", "Unknown")
        serial_port = rig.get("serial_port", "")
        
        # Create new window
        window = tk.Toplevel(self.root)
        
        # Combine rig config with processes config and config path for RigWindow
        rig_config = {
            **rig,
            "processes": self.processes,
            "config_path": self.config_path,
        }
        
        # Create RigWindow content in the toplevel
        rig_window = RigWindow(
            serial_port=serial_port,
            baud_rate=self.baud_rate,
            parent=window,
            rig_name=rig_name,
            rig_config=rig_config,
        )
        
        # Track this window
        btn = self.rig_buttons.get(rig_name)
        self.open_windows[rig_name] = (window, btn)
        
        # Handle window close
        def on_window_close():
            self._on_rig_window_close(rig_name)
        
        window.protocol("WM_DELETE_WINDOW", on_window_close)
        
        self.status_var.set(f"{rig_name} opened")
    
    def _on_rig_window_close(self, rig_name: str) -> None:
        """Handle a rig window being closed."""
        if rig_name in self.open_windows:
            window, btn = self.open_windows[rig_name]
            
            # Destroy the window
            try:
                window.destroy()
            except:
                pass
            
            # Remove from tracking
            del self.open_windows[rig_name]
            
            # Re-enable button
            if btn:
                btn.configure(state="normal")
            
            self.status_var.set(f"{rig_name} closed")
    
    def _on_close(self) -> None:
        """Handle launcher window close."""
        # Close all open rig windows
        for rig_name in list(self.open_windows.keys()):
            window, _ = self.open_windows[rig_name]
            try:
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
