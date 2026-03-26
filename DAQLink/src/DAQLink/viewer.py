"""
DAQ Live Viewer — real-time logic-analyzer display for Arduino DAQ channels.

Connects to an Arduino DAQ board via serial, decodes the binary protocol,
and renders all 26 digital channels as scrolling high/low traces on a
tkinter Canvas.  Designed to handle data rates up to 2 000 Hz without
dropping frames by using transition-based rendering and pre-allocated
canvas items.

Usage::

    python -m DAQLink.viewer                        # pick port in GUI
    python -m DAQLink.viewer --port COM10           # direct COM port
    python -m DAQLink.viewer --board rig_1_daq \\
        --registry path/to/board_registry.json      # use board registry
"""
from __future__ import annotations

import bisect
import sys
import threading
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import ttk
from typing import Optional

import serial
import serial.tools.list_ports

try:
    from .protocol import (
        BAUDRATE,
        CHANNEL_GROUPS,
        DISPLAY_ORDER,
        HANDSHAKE_BYTE,
        _CHANNEL_BIT_INDEX,
        decode_message,
    )
except ImportError:
    from protocol import (  # type: ignore[no-redef]
        BAUDRATE,
        CHANNEL_GROUPS,
        DISPLAY_ORDER,
        HANDSHAKE_BYTE,
        _CHANNEL_BIT_INDEX,
        decode_message,
    )

# ---------------------------------------------------------------------------
# Colour palette (dark theme, one colour per channel group)
# ---------------------------------------------------------------------------
_GROUP_COLOURS: dict[str, str] = {
    "Sensors": "#00CED1",   # dark turquoise
    "LEDs":    "#5B9BD5",   # steel blue
    "Valves":  "#70AD47",   # olive green
    "GPIOs":   "#ED7D31",   # orange
    "System":  "#C678DD",   # soft purple
}

_CHANNEL_COLOUR: dict[str, str] = {}
for _grp, _names in CHANNEL_GROUPS.items():
    for _n in _names:
        _CHANNEL_COLOUR[_n] = _GROUP_COLOURS[_grp]

_BG       = "#1E1E1E"
_FG       = "#CCCCCC"
_GRID     = "#333333"
_DIVIDER  = "#444444"
_TOOLBAR  = "#2D2D2D"
_STATUS   = "#252525"


# ===================================================================
# SampleBuffer — thread-safe ring buffer
# ===================================================================

class SampleBuffer:
    """Ring buffer storing ``(timestamp, state_word)`` tuples.

    The reader thread appends; the GUI thread reads windows.
    ``collections.deque`` with *maxlen* is used for lock-free append in
    CPython.  Bulk reads snapshot the deque (cheap — it copies pointers,
    not payloads).
    """

    def __init__(self, maxlen: int = 600_000):
        self._data: deque[tuple[float, int]] = deque(maxlen=maxlen)

    # -- writer (reader thread) -----------------------------------------

    def append(self, timestamp: float, state_word: int) -> None:
        self._data.append((timestamp, state_word))

    # -- reader (GUI thread) --------------------------------------------

    @property
    def latest(self) -> Optional[tuple[float, int]]:
        try:
            return self._data[-1]
        except IndexError:
            return None

    def get_window(self, t_start: float, t_end: float) -> list[tuple[float, int]]:
        """Return samples in *[t_start, t_end]*.

        Takes a snapshot of the deque, then uses bisect on the sorted
        timestamps to extract only the visible range.
        """
        snap = list(self._data)  # O(n) but only copies pointers
        if not snap:
            return []
        lo = bisect.bisect_left(snap, (t_start,))
        hi = bisect.bisect_right(snap, (t_end + 1e-9,))
        # Include one sample before the window so the trace starts at
        # the correct level on the left edge.
        if lo > 0:
            lo -= 1
        return snap[lo:hi]

    def __len__(self) -> int:
        return len(self._data)


# ===================================================================
# DAQReaderThread — background serial acquisition
# ===================================================================

class DAQReaderThread(threading.Thread):
    """Daemon thread that reads from the Arduino and fills a :class:`SampleBuffer`."""

    def __init__(self, port: str, buffer: SampleBuffer):
        super().__init__(daemon=True)
        self.port = port
        self.buffer = buffer

        self._stop_event = threading.Event()
        self.error: Optional[str] = None
        self.connected = False
        self.message_count = 0
        self.error_count = 0
        self._start_time: float = 0.0

    # -- public API -----------------------------------------------------

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def elapsed(self) -> float:
        if self._start_time == 0.0:
            return 0.0
        return time.perf_counter() - self._start_time

    @property
    def messages_per_second(self) -> float:
        if self.elapsed < 0.5:
            return 0.0
        return self.message_count / self.elapsed

    # -- thread body ----------------------------------------------------

    def run(self) -> None:
        try:
            conn = serial.Serial(self.port, BAUDRATE, timeout=1)
        except serial.SerialException as exc:
            self.error = f"Cannot open {self.port}: {exc}"
            return

        try:
            # Wait for Arduino bootloader
            time.sleep(2)
            conn.reset_input_buffer()
            conn.write(HANDSHAKE_BYTE)
            echo = conn.read_until(HANDSHAKE_BYTE, 5)
            if HANDSHAKE_BYTE not in echo:
                self.error = "Handshake failed — no echo from Arduino."
                conn.close()
                return

            self.connected = True
            self._start_time = time.perf_counter()
            first_message = True

            while not self._stop_event.is_set():
                if conn.in_waiting > 9:
                    ts = time.perf_counter() - self._start_time
                    raw = conn.read_until(b"\x02\x01")[:-2]
                    if first_message:
                        raw = raw[1:]  # strip leading 0x00 from Arduino reset
                        first_message = False
                    if len(raw) == 9:
                        _msg_id, state_word = decode_message(raw)
                        self.buffer.append(ts, state_word)
                        self.message_count += 1
                    else:
                        self.error_count += 1
                else:
                    # Yield CPU when no data waiting
                    time.sleep(0.0001)

        except serial.SerialException as exc:
            self.error = f"Serial error: {exc}"
        finally:
            try:
                for _ in range(3):
                    conn.write(b"e")
                    time.sleep(0.05)
                conn.close()
            except Exception:
                pass
            self.connected = False


# ===================================================================
# LogicAnalyzerCanvas — high-performance waveform display
# ===================================================================

class LogicAnalyzerCanvas(tk.Canvas):
    """Renders 26 digital channels as a scrolling logic-analyzer view.

    Static chrome (labels, grid, dividers) is drawn once and redrawn
    only on resize.  Waveform lines are pre-allocated canvas items
    whose coordinates are updated in-place each frame.
    """

    MARGIN_LEFT = 80
    MARGIN_RIGHT = 12
    MARGIN_TOP = 6
    MARGIN_BOTTOM = 24
    LANE_HEIGHT = 24
    LANE_PAD = 3  # vertical padding within lane for HIGH/LOW levels

    def __init__(self, parent: tk.Widget, **kwargs):
        kwargs.setdefault("bg", _BG)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(parent, **kwargs)

        self._line_ids: dict[str, int] = {}
        self._label_ids: list[int] = []
        self._group_label_ids: list[int] = []
        self._divider_ids: list[int] = []
        self._tick_ids: list[int] = []
        self._chrome_drawn = False
        self._prev_size: tuple[int, int] = (0, 0)

        # Create one line item per channel (invisible until data arrives)
        for ch_name in DISPLAY_ORDER:
            lid = self.create_line(0, 0, 0, 0,
                                   fill=_CHANNEL_COLOUR[ch_name],
                                   width=1.5,
                                   state="hidden")
            self._line_ids[ch_name] = lid

        self.bind("<Configure>", self._on_resize)

    # -- coordinate helpers ---------------------------------------------

    def _plot_area(self) -> tuple[int, int, int, int]:
        """Return (x0, y0, x1, y1) of the plot region."""
        w = self.winfo_width()
        h = self.winfo_height()
        return (self.MARGIN_LEFT, self.MARGIN_TOP,
                w - self.MARGIN_RIGHT, h - self.MARGIN_BOTTOM)

    def _lane_y(self, lane_index: int) -> tuple[float, float]:
        """Return (y_high, y_low) pixel positions for a lane."""
        _, y0, _, _ = self._plot_area()
        top = y0 + lane_index * self.LANE_HEIGHT
        y_high = top + self.LANE_PAD
        y_low = top + self.LANE_HEIGHT - self.LANE_PAD
        return y_high, y_low

    # -- static chrome --------------------------------------------------

    def _on_resize(self, _event: tk.Event = None) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if (w, h) != self._prev_size:
            self._prev_size = (w, h)
            self._draw_chrome()

    def _draw_chrome(self) -> None:
        # Clear old chrome
        for cid in self._label_ids + self._group_label_ids + self._divider_ids + self._tick_ids:
            self.delete(cid)
        self._label_ids.clear()
        self._group_label_ids.clear()
        self._divider_ids.clear()
        self._tick_ids.clear()

        x0, y0, x1, y1 = self._plot_area()

        lane_idx = 0
        for group_name, channels in CHANNEL_GROUPS.items():
            # Group label
            group_y = y0 + lane_idx * self.LANE_HEIGHT
            gid = self.create_text(
                4, group_y + 1,
                text=group_name, anchor="nw",
                fill=_GROUP_COLOURS[group_name],
                font=("Consolas", 7, "bold"),
            )
            self._group_label_ids.append(gid)

            for ch_name in channels:
                y_high, y_low = self._lane_y(lane_idx)
                y_mid = (y_high + y_low) / 2

                # Channel label
                lid = self.create_text(
                    self.MARGIN_LEFT - 6, y_mid,
                    text=ch_name, anchor="e",
                    fill=_CHANNEL_COLOUR[ch_name],
                    font=("Consolas", 7),
                )
                self._label_ids.append(lid)

                # Lane divider
                did = self.create_line(
                    x0, y_high - self.LANE_PAD,
                    x1, y_high - self.LANE_PAD,
                    fill=_GRID, width=1, dash=(2, 4),
                )
                self._divider_ids.append(did)

                lane_idx += 1

            # Group separator (slightly heavier)
            sep_y = y0 + lane_idx * self.LANE_HEIGHT
            sid = self.create_line(x0, sep_y, x1, sep_y, fill=_DIVIDER, width=1)
            self._divider_ids.append(sid)

        self._chrome_drawn = True

    # -- waveform update ------------------------------------------------

    def update_traces(self, buffer: SampleBuffer,
                      t_left: float, t_right: float) -> None:
        """Rebuild all 23 trace polylines from *buffer* data."""
        x0, _y0, x1, _y1 = self._plot_area()
        plot_width = x1 - x0
        if plot_width < 2 or t_right <= t_left:
            return

        samples = buffer.get_window(t_left, t_right)
        dt = t_right - t_left

        def time_to_px(t: float) -> float:
            return x0 + (t - t_left) / dt * plot_width

        for lane_idx, ch_name in enumerate(DISPLAY_ORDER):
            bit_idx = _CHANNEL_BIT_INDEX[ch_name]
            y_high, y_low = self._lane_y(lane_idx)
            line_id = self._line_ids[ch_name]

            if not samples:
                self.itemconfigure(line_id, state="hidden")
                continue

            # Build transition-based coordinate list
            coords: list[float] = []
            prev_bit: Optional[int] = None
            prev_px: Optional[float] = None

            for t, word in samples:
                bit = (word >> bit_idx) & 1
                px = time_to_px(t)

                # Clamp to plot area
                if px < x0:
                    px = float(x0)
                elif px > x1:
                    px = float(x1)

                y = y_high if bit else y_low

                if prev_bit is None:
                    # First sample — just record starting point
                    coords.extend([px, y])
                    prev_bit = bit
                    prev_px = px
                    continue

                if bit != prev_bit:
                    # Pixel-column merging: if same pixel as last point,
                    # just draw a vertical bar instead of tiny horizontal
                    prev_y = y_high if prev_bit else y_low
                    if prev_px is not None and abs(px - prev_px) < 1.0:
                        # Collapse: extend vertical at this x
                        coords.extend([px, prev_y, px, y])
                    else:
                        # Normal transition: horizontal to here, then step
                        coords.extend([px, prev_y, px, y])
                    prev_bit = bit

                prev_px = px

            # Extend last level to right edge
            if prev_bit is not None:
                last_y = y_high if prev_bit else y_low
                coords.extend([float(x1), last_y])

            if len(coords) >= 4:
                self.coords(line_id, *coords)
                self.itemconfigure(line_id, state="normal")
            else:
                self.itemconfigure(line_id, state="hidden")

    # -- time axis ticks ------------------------------------------------

    def update_time_axis(self, t_left: float, t_right: float) -> None:
        for tid in self._tick_ids:
            self.delete(tid)
        self._tick_ids.clear()

        x0, _y0, x1, y1 = self._plot_area()
        plot_width = x1 - x0
        if plot_width < 20:
            return

        dt = t_right - t_left
        # Choose a nice tick interval
        for interval in (0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0):
            if plot_width / (dt / interval) > 40:
                break

        t_tick = (t_left // interval + 1) * interval
        while t_tick < t_right:
            px = x0 + (t_tick - t_left) / dt * plot_width
            # Tick mark
            tid = self.create_line(px, y1, px, y1 + 4, fill=_FG, width=1)
            self._tick_ids.append(tid)
            # Label
            if dt <= 5.0:
                label = f"{t_tick:.1f}s"
            else:
                label = f"{t_tick:.0f}s"
            tid = self.create_text(px, y1 + 6, text=label, anchor="n",
                                   fill=_FG, font=("Consolas", 7))
            self._tick_ids.append(tid)
            t_tick += interval


# ===================================================================
# DAQViewer — top-level application
# ===================================================================

class DAQViewer:
    """Standalone tkinter application for live DAQ viewing."""

    UPDATE_INTERVAL_MS = 33   # ~30 fps
    DEFAULT_WINDOW_SEC = 5.0

    def __init__(self, root: tk.Tk, *,
                 initial_port: Optional[str] = None):
        self.root = root
        self.root.title("DAQ Live Viewer")
        self.root.configure(bg=_BG)
        self.root.minsize(700, 400)

        self._buffer = SampleBuffer()
        self._reader: Optional[DAQReaderThread] = None
        self._update_id: Optional[str] = None

        self._paused = False
        self._pause_time: float = 0.0
        self._window_sec = self.DEFAULT_WINDOW_SEC

        self._build_toolbar()
        self._build_canvas()
        self._build_status_bar()
        self._bind_keys()

        if initial_port:
            self._port_var.set(initial_port)

        self._refresh_ports()

    # -- UI construction ------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = tk.Frame(self.root, bg=_TOOLBAR, padx=6, pady=4)
        tb.pack(fill="x", side="top")

        # Port selection
        tk.Label(tb, text="Port:", bg=_TOOLBAR, fg=_FG,
                 font=("Consolas", 9)).pack(side="left")
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(
            tb, textvariable=self._port_var, width=14,
            state="readonly", font=("Consolas", 9))
        self._port_combo.pack(side="left", padx=(4, 2))

        self._refresh_btn = tk.Button(
            tb, text="\u21BB", command=self._refresh_ports,
            bg=_TOOLBAR, fg=_FG, relief="flat", font=("Consolas", 10),
            activebackground=_GRID, activeforeground=_FG)
        self._refresh_btn.pack(side="left", padx=(0, 8))

        # Connect / disconnect
        self._connect_btn = tk.Button(
            tb, text="Connect", command=self._toggle_connection,
            bg="#2D5A2D", fg="#FFFFFF", relief="flat",
            font=("Consolas", 9, "bold"), padx=10,
            activebackground="#3D7A3D", activeforeground="#FFFFFF")
        self._connect_btn.pack(side="left", padx=(0, 8))

        # Pause
        self._pause_btn = tk.Button(
            tb, text="Pause", command=self._toggle_pause,
            bg=_TOOLBAR, fg=_FG, relief="flat",
            font=("Consolas", 9), padx=8, state="disabled",
            activebackground=_GRID, activeforeground=_FG)
        self._pause_btn.pack(side="left", padx=(0, 8))

        # Window size
        tk.Label(tb, text="Window:", bg=_TOOLBAR, fg=_FG,
                 font=("Consolas", 9)).pack(side="left")
        self._window_var = tk.StringVar(value="5s")
        win_combo = ttk.Combobox(
            tb, textvariable=self._window_var, width=5,
            values=["1s", "2s", "5s", "10s", "30s"],
            state="readonly", font=("Consolas", 9))
        win_combo.pack(side="left", padx=(4, 0))
        win_combo.bind("<<ComboboxSelected>>", self._on_window_change)

    def _build_canvas(self) -> None:
        self._canvas = LogicAnalyzerCanvas(self.root)
        self._canvas.pack(fill="both", expand=True)

    def _build_status_bar(self) -> None:
        sb = tk.Frame(self.root, bg=_STATUS, padx=6, pady=3)
        sb.pack(fill="x", side="bottom")

        self._status_label = tk.Label(
            sb, text="Disconnected", bg=_STATUS, fg="#888888",
            font=("Consolas", 8), anchor="w")
        self._status_label.pack(side="left")

        self._rate_label = tk.Label(
            sb, text="", bg=_STATUS, fg=_FG,
            font=("Consolas", 8), anchor="e")
        self._rate_label.pack(side="right")

    def _bind_keys(self) -> None:
        self.root.bind("<space>", lambda _e: self._toggle_pause())
        self.root.bind("<Escape>", lambda _e: self._disconnect())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- port management ------------------------------------------------

    def _refresh_ports(self) -> None:
        ports = sorted(p.device for p in serial.tools.list_ports.comports())
        self._port_combo["values"] = ports
        if ports and not self._port_var.get():
            self._port_var.set(ports[0])

    # -- connection control ---------------------------------------------

    def _toggle_connection(self) -> None:
        if self._reader and self._reader.is_alive():
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        port = self._port_var.get()
        if not port:
            return

        self._buffer = SampleBuffer()
        self._reader = DAQReaderThread(port, self._buffer)
        self._paused = False
        self._pause_time = 0.0

        self._connect_btn.configure(text="Connecting...", state="disabled")
        self._reader.start()

        # Poll for connection result
        self._poll_connection()

    def _poll_connection(self) -> None:
        if self._reader is None:
            return
        if self._reader.connected:
            self._connect_btn.configure(
                text="Disconnect", state="normal",
                bg="#5A2D2D", activebackground="#7A3D3D")
            self._pause_btn.configure(state="normal")
            self._status_label.configure(text="Connected", fg="#70AD47")
            self._start_update_loop()
        elif self._reader.error:
            self._status_label.configure(text=self._reader.error, fg="#FF6B6B")
            self._connect_btn.configure(text="Connect", state="normal",
                                        bg="#2D5A2D", activebackground="#3D7A3D")
            self._reader = None
        elif self._reader.is_alive():
            self.root.after(100, self._poll_connection)
        else:
            self._status_label.configure(text="Connection lost", fg="#FF6B6B")
            self._connect_btn.configure(text="Connect", state="normal",
                                        bg="#2D5A2D", activebackground="#3D7A3D")
            self._reader = None

    def _disconnect(self) -> None:
        if self._reader:
            self._reader.stop()
            self._reader = None
        if self._update_id:
            self.root.after_cancel(self._update_id)
            self._update_id = None
        self._connect_btn.configure(
            text="Connect", state="normal",
            bg="#2D5A2D", activebackground="#3D7A3D")
        self._pause_btn.configure(state="disabled")
        self._status_label.configure(text="Disconnected", fg="#888888")
        self._rate_label.configure(text="")

    # -- pause / resume -------------------------------------------------

    def _toggle_pause(self) -> None:
        if not self._reader or not self._reader.connected:
            return
        self._paused = not self._paused
        if self._paused:
            self._pause_time = self._reader.elapsed
            self._pause_btn.configure(text="Resume", bg="#5A4A2D",
                                      activebackground="#7A6A3D")
        else:
            self._pause_btn.configure(text="Pause", bg=_TOOLBAR,
                                      activebackground=_GRID)

    # -- window size ----------------------------------------------------

    def _on_window_change(self, _event=None) -> None:
        text = self._window_var.get().rstrip("s")
        try:
            self._window_sec = float(text)
        except ValueError:
            pass

    # -- update loop ----------------------------------------------------

    def _start_update_loop(self) -> None:
        self._update()

    def _update(self) -> None:
        if self._reader is None:
            return

        # Check for errors
        if self._reader.error and not self._reader.connected:
            self._status_label.configure(text=self._reader.error, fg="#FF6B6B")
            self._disconnect()
            return

        # Determine visible time window
        if self._paused:
            t_right = self._pause_time
        else:
            t_right = self._reader.elapsed
        t_left = t_right - self._window_sec

        # Update traces
        self._canvas.update_traces(self._buffer, t_left, t_right)
        self._canvas.update_time_axis(t_left, t_right)

        # Update status bar
        rate = self._reader.messages_per_second
        errs = self._reader.error_count
        elapsed = self._reader.elapsed
        buf_len = len(self._buffer)

        parts = [
            f"{rate:,.0f} msg/s",
            f"{errs} errors" if errs else "",
            f"{elapsed:.1f}s",
            f"{buf_len:,} buffered",
        ]
        self._rate_label.configure(text="  |  ".join(p for p in parts if p))

        # Schedule next frame
        self._update_id = self.root.after(self.UPDATE_INTERVAL_MS, self._update)

    # -- cleanup --------------------------------------------------------

    def _on_close(self) -> None:
        self._disconnect()
        self.root.destroy()


# ===================================================================
# Rig config resolution
# ===================================================================

def _resolve_port_for_rig(
    rig_number: int,
    config_path: str,
    registry_path: str,
) -> str:
    """Look up the DAQ COM port for a rig number via the YAML config
    and board registry, following the same resolution chain as the
    main behaviour rig system.

    Resolution: rig number -> rigs.yaml ``daq_board_name`` ->
    board_registry.json -> USB scan -> COM port.
    """
    import yaml

    # Lazy import — avoids hard dependency on behaviour_rig_system at
    # module level, but we need BoardRegistry for USB-serial resolution.
    sys.path.insert(0, str(
        Path(__file__).resolve().parents[3] / "behaviour_rig_system"))
    from core.board_registry import BoardRegistry

    # Load rig config
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Rig config not found: {cfg_path}")
    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    rigs = config.get("rigs", [])
    if not rigs:
        raise ValueError(f"No rigs defined in {cfg_path}")

    # Find the matching rig entry (1-indexed)
    if rig_number < 1 or rig_number > len(rigs):
        available = ", ".join(str(i + 1) for i in range(len(rigs)))
        raise ValueError(
            f"Rig {rig_number} not found. Available: {available}")

    rig_entry = rigs[rig_number - 1]
    daq_board_name = rig_entry.get("daq_board_name", "")
    if not daq_board_name:
        raise ValueError(
            f"Rig {rig_number} ({rig_entry.get('name', '?')}) "
            f"has no 'daq_board_name' in config")

    # Resolve via board registry
    registry = BoardRegistry(Path(registry_path))
    port = registry.resolve_port(daq_board_name)
    rig_name = rig_entry.get("name", f"Rig {rig_number}")
    print(f"Resolved {rig_name} -> {daq_board_name} -> {port}")
    return port


# ===================================================================
# Configuration — edit these to match your setup
# ===================================================================

# Path to the rig configuration file
CONFIG_PATH = Path(r"D:\test\hex_behav_configs\rigs.yaml")

# Path to the board registry file
BOARD_REGISTRY_PATH = Path(
    r"C:\Dev\projects\hex_behav\hex_behav_control\behaviour_rig_system\config\board_registry.json"
)

# Rig number to connect to (1-indexed). Set to None to pick port manually in GUI.
RIG_NUMBER = 1




# ===================================================================
# Entry point
# ===================================================================

def main() -> None:
    """Launch the DAQ Live Viewer.

    Edit the configuration variables above to select which rig to
    connect to.  When ``RIG_NUMBER`` is set, the DAQ COM port is
    resolved automatically from the rig config and board registry
    (same chain as the main behaviour rig system).  Set it to
    ``None`` to pick a port manually in the GUI.
    """
    port = None

    if RIG_NUMBER is not None:
        try:
            port = _resolve_port_for_rig(
                RIG_NUMBER, str(CONFIG_PATH), str(BOARD_REGISTRY_PATH))
        except Exception as exc:
            print(f"Error resolving rig {RIG_NUMBER}: {exc}",
                  file=sys.stderr)
            sys.exit(1)

    root = tk.Tk()
    root.geometry("1100x620")
    DAQViewer(root, initial_port=port)
    root.mainloop()


if __name__ == "__main__":
    main()
