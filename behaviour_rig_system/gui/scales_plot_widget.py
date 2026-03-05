"""
Scales Plot Widget - Live weight readout plot using pure tkinter Canvas.

Displays a rolling 20-second window of scales weight readings at ~5Hz.
Uses no external plotting libraries - pure tkinter Canvas drawing.

Performance: Static elements (axes, grid, labels) are drawn once and only
redrawn on resize. The data line and single-point dot are updated in-place
via canvas.coords() / canvas.itemconfigure() on each poll tick.
"""

import time
import tkinter as tk
from collections import deque
from tkinter import ttk
from typing import Optional, Protocol

from gui.theme import Theme


class ScalesClientProtocol(Protocol):
    """Protocol for scales client interface (duck typing)."""
    def get_weight(self) -> Optional[float]: ...


class ScalesPlotWidget(ttk.Frame):
    """
    Live-updating weight plot widget.
    
    Polls a scales client at ~5Hz and displays a rolling 20-second
    line chart of weight readings on a tkinter Canvas.
    
    Static chrome (axes, grid, labels) is drawn once and redrawn only on
    resize.  The data line is updated in-place each poll tick.
    """
    
    # Plot configuration
    POLL_INTERVAL_MS = 100      # 10 Hz polling
    WINDOW_SECONDS = 20.0       # Show last 20 seconds
    Y_PADDING_FRACTION = 0.15   # 15% vertical padding above/below data
    DEFAULT_Y_MIN = -2.0        # Default lower Y limit (grams)
    DEFAULT_Y_MAX = 40.0        # Default upper Y limit (grams)
    
    # Drawing constants
    MARGIN_LEFT = 52
    MARGIN_RIGHT = 12
    MARGIN_TOP = 8
    MARGIN_BOTTOM = 24
    
    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(parent, **kwargs)
        
        self._scales_client: Optional[ScalesClientProtocol] = None
        self._poll_id: Optional[str] = None
        self._is_active = False
        
        # Data buffer: (timestamp, weight) tuples
        # At 10Hz for 20s we need ~200 points; keep a bit extra
        self._data: deque[tuple[float, float]] = deque(maxlen=250)
        
        # Canvas item IDs for dynamic elements (updated each poll)
        self._data_line_id: Optional[int] = None
        self._data_dot_id: Optional[int] = None
        self._no_data_text_id: Optional[int] = None
        
        # Cached Y-range used by the static chrome so we know when to redraw
        self._drawn_y_min: Optional[float] = None
        self._drawn_y_max: Optional[float] = None
        # Cached canvas dimensions
        self._drawn_w: int = 0
        self._drawn_h: int = 0
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create the canvas and current-weight label."""
        palette = Theme.palette
        
        # Header row with current weight readout
        header = ttk.Frame(self)
        header.pack(fill="x", padx=4, pady=(2, 0))
        
        ttk.Label(
            header, text="Current:", 
            style="Subheading.TLabel"
        ).pack(side="left")
        
        self._weight_label = ttk.Label(
            header, text="-- g",
            font=Theme.font_mono(size=12),
            foreground=palette.accent_primary,
        )
        self._weight_label.pack(side="left", padx=(6, 0))
        
        self._status_label = ttk.Label(
            header, text="",
            font=Theme.font_small(),
            foreground=palette.text_secondary,
        )
        self._status_label.pack(side="right")
        
        # Canvas for the plot
        self._canvas = tk.Canvas(
            self,
            bg=palette.bg_secondary,
            highlightthickness=1,
            highlightbackground=palette.border_medium,
        )
        self._canvas.pack(fill="both", expand=True, padx=4, pady=(2, 4))
        
        # Bind resize to full redraw (static + dynamic)
        self._canvas.bind("<Configure>", lambda e: self._on_resize())
    
    def set_scales_client(self, client: Optional[ScalesClientProtocol]) -> None:
        """Set the scales client to poll for weight readings."""
        self._scales_client = client
    
    def start(self) -> None:
        """Start polling the scales and updating the plot."""
        if self._is_active:
            return
        self._is_active = True
        self._data.clear()
        self._invalidate_static()
        self._status_label.config(text="Live")
        self._poll()
    
    def stop(self) -> None:
        """Stop polling."""
        self._is_active = False
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self._status_label.config(text="Stopped")
    
    def _poll(self) -> None:
        """Poll the scales client and schedule next poll."""
        if not self._is_active:
            return
        
        now = time.monotonic()
        
        if self._scales_client is not None:
            try:
                weight = self._scales_client.get_weight()
            except Exception:
                weight = None
            
            if weight is not None:
                self._data.append((now, weight))
                self._weight_label.config(text=f"{weight:.2f} g")
            else:
                self._weight_label.config(text="-- g")
        
        # Prune old data outside the window
        cutoff = now - self.WINDOW_SECONDS - 1.0
        while self._data and self._data[0][0] < cutoff:
            self._data.popleft()
        
        self._update_data_line()
        
        self._poll_id = self.after(self.POLL_INTERVAL_MS, self._poll)
    
    # =========================================================================
    # Static chrome (axes, grid, labels) — redrawn only on resize or Y-range
    # =========================================================================
    
    def _invalidate_static(self) -> None:
        """Force a full redraw on the next update."""
        self._drawn_y_min = None
        self._drawn_y_max = None
        self._drawn_w = 0
        self._drawn_h = 0
        self._data_line_id = None
        self._data_dot_id = None
        self._no_data_text_id = None
    
    def _on_resize(self) -> None:
        """Canvas was resized — force full redraw."""
        self._invalidate_static()
        self._update_data_line()
    
    def _compute_y_range(self) -> tuple[float, float]:
        """Compute the Y axis range, expanding beyond defaults if data exceeds them."""
        y_min = self.DEFAULT_Y_MIN
        y_max = self.DEFAULT_Y_MAX
        
        if self._data:
            data_min = min(d[1] for d in self._data)
            data_max = max(d[1] for d in self._data)
            if data_min < y_min:
                y_min = data_min - abs(data_min) * self.Y_PADDING_FRACTION
            if data_max > y_max:
                y_max = data_max + abs(data_max) * self.Y_PADDING_FRACTION
        
        return y_min, y_max
    
    def _draw_static_chrome(self, w: int, h: int, y_min: float, y_max: float) -> None:
        """Draw axes, grid lines, labels — everything except the data line."""
        canvas = self._canvas
        canvas.delete("all")
        self._data_line_id = None
        self._data_dot_id = None
        self._no_data_text_id = None
        
        palette = Theme.palette
        
        px_left = self.MARGIN_LEFT
        px_right = w - self.MARGIN_RIGHT
        px_top = self.MARGIN_TOP
        px_bottom = h - self.MARGIN_BOTTOM
        plot_w = px_right - px_left
        plot_h = px_bottom - px_top
        
        if plot_w < 10 or plot_h < 10:
            return
        
        y_range = y_max - y_min
        
        # Background
        canvas.create_rectangle(
            px_left, px_top, px_right, px_bottom,
            fill=palette.bg_tertiary, outline=palette.border_light,
            tags="static",
        )
        
        # Zero-gram reference line
        if y_min <= 0 <= y_max:
            zero_frac = (y_max - 0.0) / y_range
            zero_py = px_top + zero_frac * plot_h
            canvas.create_line(
                px_left, zero_py, px_right, zero_py,
                fill=palette.text_secondary, width=2, dash=(6, 3),
                tags="static",
            )
            canvas.create_text(
                px_left - 4, zero_py,
                text="0.0", anchor="e",
                font=Theme.font_tiny(), fill=palette.text_primary,
                tags="static",
            )
        
        # Y-axis grid lines and labels
        n_grid_y = 4
        for i in range(n_grid_y + 1):
            frac = i / n_grid_y
            y_val = y_max - frac * y_range
            py = px_top + frac * plot_h
            
            canvas.create_line(
                px_left, py, px_right, py,
                fill=palette.border_light, dash=(2, 4), tags="static",
            )
            canvas.create_text(
                px_left - 4, py,
                text=f"{y_val:.1f}", anchor="e",
                font=Theme.font_tiny(), fill=palette.text_secondary,
                tags="static",
            )
        
        # X-axis labels
        x_ticks = [0, 5, 10, 15, 20]
        for sec in x_ticks:
            if sec > self.WINDOW_SECONDS:
                continue
            frac = 1.0 - (sec / self.WINDOW_SECONDS)
            px = px_left + frac * plot_w
            
            canvas.create_line(
                px, px_bottom, px, px_bottom + 4,
                fill=palette.border_medium, tags="static",
            )
            if 0 < sec < self.WINDOW_SECONDS:
                canvas.create_line(
                    px, px_top, px, px_bottom,
                    fill=palette.border_light, dash=(2, 4), tags="static",
                )
            label = "now" if sec == 0 else f"-{sec}s"
            canvas.create_text(
                px, px_bottom + 6, text=label, anchor="n",
                font=Theme.font_tiny(), fill=palette.text_secondary,
                tags="static",
            )
        
        # Axes border (drawn on top of grid)
        canvas.create_rectangle(
            px_left, px_top, px_right, px_bottom,
            outline=palette.border_medium, width=1, tags="static",
        )
        
        # Y-axis unit label
        canvas.create_text(
            4, px_top + plot_h // 2, text="g", anchor="w",
            font=Theme.font_small(), fill=palette.text_secondary,
            tags="static",
        )
        
        # Store drawn state
        self._drawn_y_min = y_min
        self._drawn_y_max = y_max
        self._drawn_w = w
        self._drawn_h = h
    
    # =========================================================================
    # Dynamic data line — updated every poll tick (no delete/recreate of chrome)
    # =========================================================================
    
    def _update_data_line(self) -> None:
        """Update only the data line and related dynamic elements."""
        canvas = self._canvas
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        
        if w < 20 or h < 20:
            return
        
        palette = Theme.palette
        
        # Compute current Y range
        y_min, y_max = self._compute_y_range()
        
        # Redraw static chrome if canvas size changed or Y range changed
        if (w != self._drawn_w
            or h != self._drawn_h
            or y_min != self._drawn_y_min
            or y_max != self._drawn_y_max
        ):
            self._draw_static_chrome(w, h, y_min, y_max)
        
        px_left = self.MARGIN_LEFT
        px_right = w - self.MARGIN_RIGHT
        px_top = self.MARGIN_TOP
        px_bottom = h - self.MARGIN_BOTTOM
        plot_w = px_right - px_left
        plot_h = px_bottom - px_top
        
        if plot_w < 10 or plot_h < 10:
            return
        
        y_range = y_max - y_min
        now = time.monotonic()
        
        # --- Build data points ---
        points: list[float] = []
        if self._data:
            for t, weight in self._data:
                age = now - t
                if age > self.WINDOW_SECONDS:
                    continue
                x_frac = 1.0 - (age / self.WINDOW_SECONDS)
                px = px_left + x_frac * plot_w
                y_frac = (y_max - weight) / y_range
                py = px_top + y_frac * plot_h
                points.extend([px, py])
        
        # --- Update / create / hide the data line ---
        if len(points) >= 4:
            if self._data_line_id is not None:
                canvas.coords(self._data_line_id, *points)
                canvas.itemconfigure(self._data_line_id, state="normal")
            else:
                self._data_line_id = canvas.create_line(
                    *points,
                    fill=palette.accent_primary, width=2, smooth=True,
                    tags="data",
                )
            # Hide dot when we have a line
            if self._data_dot_id is not None:
                canvas.itemconfigure(self._data_dot_id, state="hidden")
        else:
            # Hide line
            if self._data_line_id is not None:
                canvas.itemconfigure(self._data_line_id, state="hidden")
            
            # Single point — show dot
            if len(points) == 2:
                px, py = points
                if self._data_dot_id is not None:
                    canvas.coords(self._data_dot_id, px - 3, py - 3, px + 3, py + 3)
                    canvas.itemconfigure(self._data_dot_id, state="normal")
                else:
                    self._data_dot_id = canvas.create_oval(
                        px - 3, py - 3, px + 3, py + 3,
                        fill=palette.accent_primary, outline="",
                        tags="data",
                    )
            elif self._data_dot_id is not None:
                canvas.itemconfigure(self._data_dot_id, state="hidden")
        
        # --- "No data" message ---
        if not self._data:
            if self._no_data_text_id is not None:
                canvas.itemconfigure(self._no_data_text_id, state="normal")
            else:
                self._no_data_text_id = canvas.create_text(
                    px_left + plot_w // 2, px_top + plot_h // 2,
                    text="Waiting for data...",
                    font=Theme.font(size=10),
                    fill=palette.text_disabled,
                    tags="data",
                )
        elif self._no_data_text_id is not None:
            canvas.itemconfigure(self._no_data_text_id, state="hidden")
