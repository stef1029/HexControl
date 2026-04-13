"""
DearPyGui Application Singleton.

Owns the DPG lifecycle: context creation, viewport setup, manual render loop,
thread-safe callback queue, and frame-based polling.

Usage:
    from gui.dpg_app import create_app, run, shutdown, call_on_main_thread, frame_poller

    create_app("My Title", 1280, 800)
    # ... build GUI ...
    run()
"""

from __future__ import annotations

import collections
import ctypes
import sys
import time

import dearpygui.dearpygui as dpg


# ---------------------------------------------------------------------------
# Thread-safe callback queue  (replaces root.after(0, fn))
# ---------------------------------------------------------------------------

_callback_queue: collections.deque[tuple] = collections.deque()


def call_on_main_thread(fn, **kwargs) -> None:
    """Schedule *fn* to run on the render thread during the next frame.

    Thread-safe — may be called from any thread.
    """
    _callback_queue.append((fn, kwargs))


# ---------------------------------------------------------------------------
# Frame-based poller  (replaces root.after(interval_ms, fn))
# ---------------------------------------------------------------------------

class FramePoller:
    """Call registered functions at fixed time intervals, checked each frame."""

    def __init__(self) -> None:
        self._polls: list[list] = []  # [[interval_sec, last_call, callback], ...]
        self._pending_once: list[list] = []  # [[fire_at, callback], ...]

    def register(self, interval_ms: int, callback) -> None:
        """Register *callback* to be called every *interval_ms* milliseconds."""
        self._polls.append([interval_ms / 1000.0, time.monotonic(), callback])

    def unregister(self, callback) -> None:
        """Remove a previously registered callback."""
        self._polls = [p for p in self._polls if p[2] is not callback]

    def call_later(self, delay_ms: int, callback) -> None:
        """Schedule *callback* to run once after *delay_ms* milliseconds."""
        fire_at = time.monotonic() + delay_ms / 1000.0
        self._pending_once.append([fire_at, callback])

    def tick(self) -> None:
        """Call from the render loop once per frame."""
        now = time.monotonic()

        # Recurring polls
        for entry in self._polls:
            interval, last, cb = entry
            if now - last >= interval:
                cb()
                entry[1] = now

        # One-shot delayed callbacks
        if self._pending_once:
            still_pending = []
            for entry in self._pending_once:
                if now >= entry[0]:
                    entry[1]()
                else:
                    still_pending.append(entry)
            self._pending_once = still_pending


# Module-level poller instance
frame_poller = FramePoller()


def call_later(delay_ms: int, fn) -> None:
    """Convenience wrapper: schedule *fn* to run once after *delay_ms* ms."""
    frame_poller.call_later(delay_ms, fn)


# ---------------------------------------------------------------------------
# Dark title bar (Windows DWM API)
# ---------------------------------------------------------------------------

def _apply_dark_title_bar() -> None:
    """Apply dark mode to the viewport title bar on Windows."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.user32.GetActiveWindow()
        if hwnd == 0:
            return
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value),
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

_is_running = False


def create_app(
    title: str = "Behaviour Rig System",
    width: int = 1280,
    height: int = 800,
) -> None:
    """Create the DPG context, viewport, and font registry.

    Must be called once before building any GUI.
    """
    dpg.create_context()
    dpg.create_viewport(
        title=title, width=width, height=height,
        min_width=900, min_height=600,
    )

    # Fonts are loaded by theme.py's apply_theme()

    dpg.setup_dearpygui()
    dpg.show_viewport()
    _apply_dark_title_bar()


def run() -> None:
    """Enter the manual render loop (blocks until the viewport is closed).

    Drains the callback queue and ticks the frame poller each frame.
    """
    global _is_running
    _is_running = True

    while dpg.is_dearpygui_running():
        # Drain thread-safe callback queue
        while _callback_queue:
            fn, kwargs = _callback_queue.popleft()
            try:
                fn(**kwargs)
            except Exception as exc:
                print(f"Warning: error in main-thread callback: {exc}")

        # Time-based polling
        frame_poller.tick()

        dpg.render_dearpygui_frame()

    _is_running = False


def shutdown() -> None:
    """Destroy the DPG context.  Call after :func:`run` returns."""
    try:
        dpg.destroy_context()
    except Exception:
        pass


def is_running() -> bool:
    """Return True while the render loop is active."""
    return _is_running
