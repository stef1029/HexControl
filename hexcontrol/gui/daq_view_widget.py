"""
DAQ View Widget - Live DAQ channel display during behaviour sessions (DearPyGui).

Listens for UDP packets broadcast by serial_listen.py and renders all
23 digital channels as scrolling logic-analyzer traces using a DPG drawlist.

The widget is entirely passive — it never touches the serial port or the
DAQ subprocess.  Data arrives via localhost UDP.
"""
from __future__ import annotations

import socket
import struct
import threading
from typing import Optional

import dearpygui.dearpygui as dpg

from hexcontrol.gui.dpg_app import frame_poller
from hexcontrol.gui.theme import Theme, hex_to_rgba

# Import sample buffer (data structure only, no tkinter Canvas)
from DAQLink.viewer import SampleBuffer

_UDP_BASE_PORT = 9876

_NUM_CHANNELS = 23
_CHANNEL_HEIGHT = 20
_TRACE_HEIGHT = 14
_MARGIN_LEFT = 60


class DAQUDPListener(threading.Thread):
    """Daemon thread that receives UDP packets and pushes decoded samples
    into a SampleBuffer."""

    def __init__(self, rig_number: int, buffer: SampleBuffer):
        super().__init__(daemon=True)
        self.rig_number = rig_number
        self.buffer = buffer
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self.receiving = False

    def stop(self) -> None:
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def run(self) -> None:
        port = _UDP_BASE_PORT + self.rig_number
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("127.0.0.1", port))
            self._sock.settimeout(0.5)
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
        except OSError:
            pass


class DAQViewWidget:
    """Embeddable widget showing live DAQ channel traces via DPG drawlist."""

    UPDATE_INTERVAL_MS = 33
    DEFAULT_WINDOW_SEC = 5.0

    def __init__(self, parent: int | str):
        self._parent = parent
        self._buffer = SampleBuffer()
        self._listener: Optional[DAQUDPListener] = None
        self._rig_number: int = 0
        self._paused = False
        self._pause_time: float = 0.0
        self._window_sec = self.DEFAULT_WINDOW_SEC

        # DPG IDs
        self._group_id: int | None = None
        self._drawlist: int | None = None
        self._status_text: int | None = None
        self._rate_text: int | None = None
        self._pause_btn: int | None = None

        self._build()

    def _build(self) -> None:
        palette = Theme.palette
        self._group_id = dpg.add_group(parent=self._parent)

        # Toolbar
        with dpg.group(horizontal=True, parent=self._group_id):
            self._pause_btn = dpg.add_button(
                label="Pause", callback=lambda: self._toggle_pause(),
            )
            dpg.add_text("Window:", color=hex_to_rgba(palette.text_secondary))
            dpg.add_combo(
                items=["0.1s", "0.2s", "0.5s", "1s", "2s", "5s", "10s", "30s"],
                default_value="5s", width=70,
                callback=self._on_window_change,
            )

        # Drawlist for traces
        draw_h = _NUM_CHANNELS * _CHANNEL_HEIGHT + 30
        self._drawlist = dpg.add_drawlist(
            width=-1, height=draw_h, parent=self._group_id,
        )

        # Status bar
        with dpg.group(horizontal=True, parent=self._group_id):
            self._status_text = dpg.add_text(
                "Waiting for data...",
                color=hex_to_rgba(palette.text_disabled),
            )
            dpg.add_spacer(width=20)
            self._rate_text = dpg.add_text("", color=hex_to_rgba(palette.text_secondary))

    def start(self, rig_number: int) -> None:
        self.stop()
        self._rig_number = rig_number
        self._buffer = SampleBuffer()
        self._paused = False
        self._listener = DAQUDPListener(rig_number, self._buffer)
        self._listener.start()
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.set_value(self._status_text,
                          f"Listening on UDP :{_UDP_BASE_PORT + rig_number}")
        frame_poller.register(self.UPDATE_INTERVAL_MS, self._update)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        frame_poller.unregister(self._update)
        if self._status_text and dpg.does_item_exist(self._status_text):
            dpg.set_value(self._status_text, "Stopped")
        if self._rate_text and dpg.does_item_exist(self._rate_text):
            dpg.set_value(self._rate_text, "")

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            latest = self._buffer.latest
            self._pause_time = latest[0] if latest else 0.0
            if self._pause_btn and dpg.does_item_exist(self._pause_btn):
                dpg.configure_item(self._pause_btn, label="Resume")
        else:
            if self._pause_btn and dpg.does_item_exist(self._pause_btn):
                dpg.configure_item(self._pause_btn, label="Pause")

    def _on_window_change(self, sender, app_data) -> None:
        text = app_data.rstrip("s")
        try:
            self._window_sec = float(text)
        except ValueError:
            pass

    def _update(self) -> None:
        if self._listener is None or self._drawlist is None:
            return
        if not dpg.does_item_exist(self._drawlist):
            return

        latest = self._buffer.latest
        if latest is None:
            return

        if self._paused:
            t_right = self._pause_time
        else:
            t_right = latest[0]
        t_left = t_right - self._window_sec

        # Clear and redraw traces
        dpg.delete_item(self._drawlist, children_only=True)

        palette = Theme.palette
        draw_w = dpg.get_item_width(self._drawlist) or 800
        plot_w = draw_w - _MARGIN_LEFT - 10

        # Get samples in range
        samples = self._buffer.get_range(t_left, t_right)

        for ch in range(_NUM_CHANNELS):
            y_base = ch * _CHANNEL_HEIGHT + 15
            # Channel label
            dpg.draw_text(
                pos=[2, y_base], text=f"CH{ch:02d}",
                color=hex_to_rgba(palette.text_secondary), size=10,
                parent=self._drawlist,
            )
            # Baseline
            dpg.draw_line(
                p1=[_MARGIN_LEFT, y_base + _TRACE_HEIGHT],
                p2=[_MARGIN_LEFT + plot_w, y_base + _TRACE_HEIGHT],
                color=hex_to_rgba(palette.border_light), thickness=1,
                parent=self._drawlist,
            )

            if not samples:
                continue

            # Draw trace
            points = []
            for ts, state_word in samples:
                x = _MARGIN_LEFT + (ts - t_left) / self._window_sec * plot_w
                bit = (state_word >> ch) & 1
                y = y_base + (0 if bit else _TRACE_HEIGHT)
                points.append([x, y])

            if len(points) >= 2:
                dpg.draw_polyline(
                    points, color=hex_to_rgba(palette.accent_primary),
                    thickness=1, parent=self._drawlist,
                )

        # Status
        buf_len = len(self._buffer)
        elapsed = latest[0]
        rate = buf_len / elapsed if elapsed > 0.5 else 0.0
        if self._rate_text and dpg.does_item_exist(self._rate_text):
            dpg.set_value(self._rate_text,
                          f"{rate:,.0f} msg/s  |  {elapsed:.1f}s  |  {buf_len:,} buffered")
