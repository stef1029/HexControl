"""
Scales Plot Widget - Live weight readout plot using pure tkinter Canvas.

Displays a rolling 20-second window of scales weight readings at ~5Hz.
Uses no external plotting libraries - pure tkinter Canvas drawing.
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
        
        # Bind resize to redraw
        self._canvas.bind("<Configure>", lambda e: self._draw_plot())
    
    def set_scales_client(self, client: Optional[ScalesClientProtocol]) -> None:
        """Set the scales client to poll for weight readings."""
        self._scales_client = client
    
    def start(self) -> None:
        """Start polling the scales and updating the plot."""
        if self._is_active:
            return
        self._is_active = True
        self._data.clear()
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
        
        self._draw_plot()
        
        self._poll_id = self.after(self.POLL_INTERVAL_MS, self._poll)
    
    def _draw_plot(self) -> None:
        """Redraw the entire plot on the canvas."""
        canvas = self._canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        
        if w < 20 or h < 20:
            return
        
        palette = Theme.palette
        
        # Plot area bounds
        px_left = self.MARGIN_LEFT
        px_right = w - self.MARGIN_RIGHT
        px_top = self.MARGIN_TOP
        px_bottom = h - self.MARGIN_BOTTOM
        
        plot_w = px_right - px_left
        plot_h = px_bottom - px_top
        
        if plot_w < 10 or plot_h < 10:
            return
        
        now = time.monotonic()
        
        # --- Determine Y range from data ---
        # Start with default limits, expand if data exceeds them
        y_min_data = self.DEFAULT_Y_MIN
        y_max_data = self.DEFAULT_Y_MAX
        
        weights = [d[1] for d in self._data]
        if weights:
            data_min = min(weights)
            data_max = max(weights)
            # Only expand beyond defaults, never shrink
            if data_min < y_min_data:
                y_min_data = data_min - abs(data_min) * self.Y_PADDING_FRACTION
            if data_max > y_max_data:
                y_max_data = data_max + abs(data_max) * self.Y_PADDING_FRACTION
        
        y_min = y_min_data
        y_max = y_max_data
        y_range_padded = y_max - y_min
        
        # --- Draw background ---
        canvas.create_rectangle(
            px_left, px_top, px_right, px_bottom,
            fill=palette.bg_tertiary, outline=palette.border_light
        )
        
        # --- Draw zero-gram reference line ---
        if y_min <= 0 <= y_max:
            zero_frac = (y_max - 0.0) / y_range_padded
            zero_py = px_top + zero_frac * plot_h
            canvas.create_line(
                px_left, zero_py, px_right, zero_py,
                fill=palette.text_secondary, width=2, dash=(6, 3)
            )
            canvas.create_text(
                px_left - 4, zero_py,
                text="0.0",
                anchor="e",
                font=Theme.font_tiny(),
                fill=palette.text_primary,
            )
        
        # --- Draw grid lines and Y-axis labels ---
        n_grid_y = 4
        for i in range(n_grid_y + 1):
            frac = i / n_grid_y
            y_val = y_max - frac * y_range_padded
            py = px_top + frac * plot_h
            
            # Grid line
            canvas.create_line(
                px_left, py, px_right, py,
                fill=palette.border_light, dash=(2, 4)
            )
            
            # Y-axis label
            canvas.create_text(
                px_left - 4, py,
                text=f"{y_val:.1f}",
                anchor="e",
                font=Theme.font_tiny(),
                fill=palette.text_secondary,
            )
        
        # --- Draw X-axis labels (seconds ago) ---
        x_ticks = [0, 5, 10, 15, 20]
        for sec in x_ticks:
            if sec > self.WINDOW_SECONDS:
                continue
            frac = 1.0 - (sec / self.WINDOW_SECONDS)  # 0=left (oldest), 1=right (now)
            px = px_left + frac * plot_w
            
            # Tick mark
            canvas.create_line(
                px, px_bottom, px, px_bottom + 4,
                fill=palette.border_medium
            )
            
            # Vertical grid line
            if 0 < sec < self.WINDOW_SECONDS:
                canvas.create_line(
                    px, px_top, px, px_bottom,
                    fill=palette.border_light, dash=(2, 4)
                )
            
            # Label
            label = "now" if sec == 0 else f"-{sec}s"
            canvas.create_text(
                px, px_bottom + 6,
                text=label,
                anchor="n",
                font=Theme.font_tiny(),
                fill=palette.text_secondary,
            )
        
        # --- Draw data line ---
        if len(self._data) >= 2:
            points = []
            for t, weight in self._data:
                # X: time relative to now, mapped to pixels
                age = now - t
                if age > self.WINDOW_SECONDS:
                    continue
                x_frac = 1.0 - (age / self.WINDOW_SECONDS)
                px = px_left + x_frac * plot_w
                
                # Y: weight mapped to pixels (inverted, higher = up)
                y_frac = (y_max - weight) / y_range_padded
                py = px_top + y_frac * plot_h
                
                points.extend([px, py])
            
            if len(points) >= 4:  # Need at least 2 points (4 coords)
                canvas.create_line(
                    *points,
                    fill=palette.accent_primary,
                    width=2,
                    smooth=True,
                )
        elif len(self._data) == 1:
            # Single point - draw a dot
            t, weight = self._data[0]
            age = now - t
            if age <= self.WINDOW_SECONDS:
                x_frac = 1.0 - (age / self.WINDOW_SECONDS)
                px = px_left + x_frac * plot_w
                y_frac = (y_max - weight) / y_range_padded
                py = px_top + y_frac * plot_h
                canvas.create_oval(
                    px - 3, py - 3, px + 3, py + 3,
                    fill=palette.accent_primary, outline=""
                )
        
        # --- Draw axes border ---
        canvas.create_rectangle(
            px_left, px_top, px_right, px_bottom,
            outline=palette.border_medium, width=1
        )
        
        # --- Y-axis unit label ---
        canvas.create_text(
            4, px_top + plot_h // 2,
            text="g",
            anchor="w",
            font=Theme.font_small(),
            fill=palette.text_secondary,
        )
        
        # --- "No data" message ---
        if not self._data:
            canvas.create_text(
                px_left + plot_w // 2, px_top + plot_h // 2,
                text="Waiting for data...",
                font=Theme.font(size=10),
                fill=palette.text_disabled,
            )
