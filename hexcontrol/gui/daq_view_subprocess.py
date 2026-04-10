"""
Standalone DAQ View launcher — runs in its own process.

Launched by RunningMode._toggle_daq_view() so that each DAQ viewer has
its own tkinter mainloop and does not compete with the main GUI thread.

Usage:
    python -m gui.daq_view_subprocess <rig_number>
"""
from __future__ import annotations

import sys
import tkinter as tk

from pathlib import Path

from hexcontrol.gui.theme import Theme, apply_theme
from hexcontrol.gui.daq_view_widget import DAQViewWidget


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m gui.daq_view_subprocess <rig_number>")
        sys.exit(1)

    rig_number = int(sys.argv[1])

    root = tk.Tk()
    root.title(f"DAQ Live View \u2014 Rig {rig_number}")
    root.geometry("1100x800")
    root.configure(bg=Theme.palette.bg_primary)
    apply_theme(root)

    widget = DAQViewWidget(root)
    widget.pack(fill="both", expand=True)
    widget.start(rig_number)

    def on_close() -> None:
        widget.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
