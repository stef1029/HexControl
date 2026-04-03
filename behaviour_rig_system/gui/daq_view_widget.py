"""
DAQ View Widget - Live DAQ channel display during behaviour sessions.

Listens for UDP packets broadcast by serial_listen.py and renders all
23 digital channels as scrolling logic-analyzer traces.  Designed to be
embedded in the main behaviour rig GUI or opened as a pop-out window.

The widget is entirely passive — it never touches the serial port or the
DAQ subprocess.  Data arrives via localhost UDP, so enabling/disabling
the viewer has zero impact on data acquisition or HDF5 saving.
"""
from __future__ import annotations

import socket
import struct
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

from gui.theme import Theme

# Import rendering components from the standalone viewer
import sys
from pathlib import Path

_daqlink_src = Path(__file__).resolve().parents[2] / "DAQLink" / "src"
if str(_daqlink_src) not in sys.path:
    sys.path.insert(0, str(_daqlink_src))

from DAQLink.viewer import LogicAnalyzerCanvas, SampleBuffer

# ---------------------------------------------------------------------------
# UDP base port (must match serial_listen.py)
# ---------------------------------------------------------------------------
_UDP_BASE_PORT = 9876


class DAQUDPListener(threading.Thread):
    """Daemon thread that receives UDP packets from serial_listen.py
    and pushes decoded samples into a :class:`SampleBuffer`.

    Each packet is 16 bytes: ``>dQ`` (8-byte float64 timestamp +
    8-byte uint64 state word).
    """

    def __init__(self, rig_number: int, buffer: SampleBuffer):
        super().__init__(daemon=True)
        self.rig_number = rig_number
        self.buffer = buffer
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self.receiving = False

    def stop(self) -> None:
        self._stop_event.set()
        # Closing the socket unblocks recvfrom()
        if self._sock:
            try:
                self._sock.close()
            except OSError as e:
                print(f"Warning: error closing DAQ socket: {e}")

    def run(self) -> None:
        port = _UDP_BASE_PORT + self.rig_number
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("127.0.0.1", port))
            self._sock.settimeout(0.5)  # allow periodic stop-check
        except OSError as exc:
            print(f"DAQView: Cannot bind to UDP port {port}: {exc}")
            return

        self.receiving = True
        unpack = struct.Struct(">dQ").unpack

        while not self._stop_event.is_set():
            try:
                data, _addr = self._sock.recvfrom(64)
                if len(data) == 16:
                    timestamp, state_word = unpack(data)
                    self.buffer.append(timestamp, state_word)
            except socket.timeout:
                continue
            except OSError:
                break

        self.receiving = False
        try:
            self._sock.close()
        except OSError as e:
            print(f"Warning: error closing DAQ socket: {e}")


class DAQViewWidget(ttk.Frame):
    """Embeddable widget showing live DAQ channel traces.

    Call :meth:`start` with a rig number to begin listening, and
    :meth:`stop` to tear down the listener thread.  The widget is safe
    to create before a session starts — it will simply show an empty
    canvas until data arrives.
    """

    UPDATE_INTERVAL_MS = 33   # ~30 fps
    DEFAULT_WINDOW_SEC = 5.0

    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(parent, **kwargs)

        self._buffer = SampleBuffer()
        self._listener: Optional[DAQUDPListener] = None
        self._update_id: Optional[str] = None
        self._rig_number: int = 0

        self._paused = False
        self._pause_time: float = 0.0
        self._window_sec = self.DEFAULT_WINDOW_SEC

        self._build_toolbar()
        self._build_canvas()
        self._build_status_bar()

    # -- construction ---------------------------------------------------

    def _build_toolbar(self) -> None:
        palette = Theme.palette
        tb = tk.Frame(self, bg=palette.bg_secondary, padx=6, pady=3)
        tb.pack(fill="x", side="top")

        # Pause / resume
        self._pause_btn = tk.Button(
            tb, text="Pause", command=self._toggle_pause,
            bg=palette.bg_secondary, fg=palette.text_secondary,
            relief="flat", font=("Consolas", 8), padx=6,
            activebackground=palette.bg_tertiary,
            activeforeground=palette.text_primary)
        self._pause_btn.pack(side="left", padx=(0, 8))

        # Window size
        tk.Label(tb, text="Window:", bg=palette.bg_secondary,
                 fg=palette.text_secondary,
                 font=("Consolas", 8)).pack(side="left")
        self._window_var = tk.StringVar(value="5s")
        win_combo = ttk.Combobox(
            tb, textvariable=self._window_var, width=4,
            values=["0.1s", "0.2s", "0.5s", "1s", "2s", "5s", "10s", "30s"],
            state="readonly", font=("Consolas", 8))
        win_combo.pack(side="left", padx=(4, 0))
        win_combo.bind("<<ComboboxSelected>>", self._on_window_change)

    def _build_canvas(self) -> None:
        self._canvas = LogicAnalyzerCanvas(self)
        self._canvas.pack(fill="both", expand=True)

    def _build_status_bar(self) -> None:
        palette = Theme.palette
        sb = tk.Frame(self, bg=palette.bg_primary, padx=6, pady=2)
        sb.pack(fill="x", side="bottom")

        self._status_label = tk.Label(
            sb, text="Waiting for data...", bg=palette.bg_primary,
            fg=palette.text_disabled, font=("Consolas", 7), anchor="w")
        self._status_label.pack(side="left")

        self._rate_label = tk.Label(
            sb, text="", bg=palette.bg_primary,
            fg=palette.text_secondary, font=("Consolas", 7), anchor="e")
        self._rate_label.pack(side="right")

    # -- public API -----------------------------------------------------

    def start(self, rig_number: int) -> None:
        """Start listening for DAQ data from *rig_number*."""
        self.stop()  # clean up any previous listener
        self._rig_number = rig_number
        self._buffer = SampleBuffer()
        self._paused = False
        self._listener = DAQUDPListener(rig_number, self._buffer)
        self._listener.start()
        self._status_label.configure(
            text=f"Listening on UDP :{_UDP_BASE_PORT + rig_number}",
            fg=Theme.palette.text_secondary)
        self._start_update_loop()

    def stop(self) -> None:
        """Stop listening and rendering."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        if self._update_id:
            self.winfo_toplevel().after_cancel(self._update_id)
            self._update_id = None
        self._status_label.configure(
            text="Stopped", fg=Theme.palette.text_disabled)
        self._rate_label.configure(text="")

    # -- pause / resume -------------------------------------------------

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            latest = self._buffer.latest
            self._pause_time = latest[0] if latest else 0.0
            self._pause_btn.configure(text="Resume")
        else:
            self._pause_btn.configure(text="Pause")

    # -- window size ----------------------------------------------------

    def _on_window_change(self, _event=None) -> None:
        text = self._window_var.get().rstrip("s")
        try:
            self._window_sec = float(text)
        except ValueError as e:
            print(f"Warning: invalid window size value: {e}")

    # -- update loop ----------------------------------------------------

    def _start_update_loop(self) -> None:
        self._update()

    def _update(self) -> None:
        if self._listener is None:
            return

        latest = self._buffer.latest
        if latest is None:
            # No data yet — keep polling
            self._update_id = self.winfo_toplevel().after(
                self.UPDATE_INTERVAL_MS, self._update)
            return

        if self._paused:
            t_right = self._pause_time
        else:
            t_right = latest[0]
        t_left = t_right - self._window_sec

        self._canvas.update_traces(self._buffer, t_left, t_right)
        self._canvas.update_time_axis(t_left, t_right)

        # Status
        buf_len = len(self._buffer)
        elapsed = latest[0]
        rate = buf_len / elapsed if elapsed > 0.5 else 0.0
        self._rate_label.configure(
            text=f"{rate:,.0f} msg/s  |  {elapsed:.1f}s  |  {buf_len:,} buffered")

        self._update_id = self.winfo_toplevel().after(
            self.UPDATE_INTERVAL_MS, self._update)
