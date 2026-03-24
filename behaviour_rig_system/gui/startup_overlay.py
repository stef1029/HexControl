"""
Startup Overlay — loading screen shown during session initialization.

Displays a progress bar, status label, scrolled log, and cancel button
while the background thread connects to hardware peripherals.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk
from typing import Callable

from .theme import Theme, style_scrolled_text


class StartupOverlay(ttk.Frame):
    """
    Overlay shown during the startup sequence.

    Provides a progress bar, live status label, timestamped scrolled log,
    and a cancel button. The cancel button can be swapped to a "Close"
    button when an error occurs.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._on_cancel = on_cancel
        self._build_widgets()

    def _build_widgets(self) -> None:
        palette = Theme.palette

        inner = ttk.Frame(self, padding=(18, 12))
        inner.pack(fill="both", expand=True)

        self._title_label = ttk.Label(
            inner, text="Starting Session...", style="Heading.TLabel"
        )
        self._title_label.pack(pady=(6, 3))

        self._status_var = tk.StringVar(value="Initializing...")
        self._status_label = ttk.Label(
            inner,
            textvariable=self._status_var,
            foreground=palette.accent_primary,
            font=Theme.font(size=10),
        )
        self._status_label.pack(pady=3)

        self._progress = ttk.Progressbar(inner, mode="indeterminate", length=400)
        self._progress.pack(pady=10)

        ttk.Label(inner, text="Startup Log:", style="Subheading.TLabel").pack(
            anchor="w", pady=(6, 3)
        )

        self._log = scrolledtext.ScrolledText(
            inner, height=14, width=70, state="disabled", wrap="word"
        )
        style_scrolled_text(self._log, log_style=True)
        self._log.pack(fill="both", expand=True, pady=3)

        self._action_btn = ttk.Button(
            inner, text="Cancel", command=self._on_cancel, style="Danger.TButton"
        )
        self._action_btn.pack(pady=10)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Reset state and show the overlay."""
        self._log.config(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.config(state="disabled")
        self._status_var.set("Initializing...")
        self._title_label.config(text="Starting Session...", foreground="")
        self._action_btn.config(text="Cancel", command=self._on_cancel)
        self.pack(fill="both", expand=True)
        self._progress.start(10)

    def hide(self) -> None:
        """Stop progress and hide the overlay."""
        self._progress.stop()
        self.pack_forget()

    def update_status(self, message: str) -> None:
        """
        Update the status label and append a timestamped line to the log.

        Must be called on the main thread. For thread-safe updates, wrap
        the call with ``root.after(0, ...)``.
        """
        short = message.split("]", 1)[-1].strip() if "]" in message else message
        self._status_var.set(short[:60] + "..." if len(short) > 60 else short)

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log.config(state="normal")
        self._log.insert(tk.END, f"[{timestamp}] {message}\n")
        self._log.see(tk.END)
        self._log.config(state="disabled")

    def show_error(self, error_msg: str, on_close: Callable[[], None]) -> None:
        """Switch the overlay to error state with a Close button."""
        self._progress.stop()
        self._title_label.config(text="Startup Failed", foreground="red")
        self._status_var.set(error_msg[:80])
        self.update_status(f"ERROR: {error_msg}")
        self._action_btn.config(text="Close", command=on_close)
