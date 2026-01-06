"""
Post-Session Mode - Review completed session.

Shows:
    - Session summary (status, protocol, mouse, duration, save path)
    - New Session button to return to setup
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class PostSessionMode(ttk.Frame):
    """
    Post-session mode - shows session summary and new session button.
    """
    
    def __init__(self, parent: tk.Widget, on_new_session: Callable[[], None]):
        """
        Args:
            parent: Parent widget
            on_new_session: Callback when new session is clicked
        """
        super().__init__(parent)
        self._on_new_session = on_new_session
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the post-session UI widgets."""
        # Session complete header
        self._header = ttk.Label(
            self, text="Session Complete",
            font=("Helvetica", 18, "bold")
        )
        self._header.pack(pady=20)
        
        # Session summary
        summary_frame = ttk.LabelFrame(self, text="Session Summary", padding=(15, 10))
        summary_frame.pack(fill="x", padx=20, pady=10)
        
        self._summary_labels = {}
        summary_items = [
            ("status", "Status:"),
            ("protocol", "Protocol:"),
            ("mouse", "Mouse:"),
            ("duration", "Duration:"),
            ("save_path", "Data saved to:"),
        ]
        
        for key, label_text in summary_items:
            row = ttk.Frame(summary_frame)
            row.pack(fill="x", pady=3)
            ttk.Label(
                row, text=label_text,
                font=("TkDefaultFont", 10, "bold"), width=15, anchor="e"
            ).pack(side="left")
            value_label = ttk.Label(row, text="", font=("TkDefaultFont", 10))
            value_label.pack(side="left", padx=10)
            self._summary_labels[key] = value_label
        
        # Spacer
        ttk.Frame(self).pack(fill="both", expand=True)
        
        # New session button
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        self._new_session_button = ttk.Button(
            button_frame, text="New Session",
            command=self._on_new_session_clicked
        )
        self._new_session_button.pack(side="right", padx=5)
    
    def activate(self, session_result: dict) -> None:
        """
        Called when this mode becomes active.
        
        Args:
            session_result: Dict with status, protocol_name, mouse_id, 
                          elapsed_time, save_path
        """
        # Format duration
        elapsed = session_result.get("elapsed_time", 0)
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Set summary values
        status = session_result.get("status", "Unknown")
        self._summary_labels["status"].config(text=status)
        self._summary_labels["protocol"].config(text=session_result.get("protocol_name", ""))
        self._summary_labels["mouse"].config(text=session_result.get("mouse_id", ""))
        self._summary_labels["duration"].config(text=duration_str)
        self._summary_labels["save_path"].config(text=session_result.get("save_path", ""))
        
        # Color-code status
        status_colors = {
            "Completed": "darkgreen",
            "Aborted": "darkorange",
            "Error": "red",
        }
        color = status_colors.get(status, "black")
        self._summary_labels["status"].config(foreground=color)
    
    def _on_new_session_clicked(self) -> None:
        """Handle new session button click."""
        if self._on_new_session:
            self._on_new_session()
