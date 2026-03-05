"""
Virtual Rig Window — Interactive top-down hex rig visualisation.

Opens as a separate Toplevel alongside the RigWindow when in simulate mode.
Renders the 6.port hexagonal rig with clickable nose-poke ports, a weight
slider for platform simulation, GPIO toggles, and real-time visual feedback
for LEDs, spotlights, valves, speaker and IR state.

Usage (from rig_window.py):
    from gui.virtual_rig_window import VirtualRigWindow
    vr_win = VirtualRigWindow(parent, virtual_rig_state)
    ...
    vr_win.close()
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import Optional, TYPE_CHECKING

from .theme import Theme, apply_theme

if TYPE_CHECKING:
    from BehavLink.simulation import VirtualRigState, RigStateSnapshot


# ── Colour helpers ──────────────────────────────────────────────────────────

def _lerp_colour(colour_off: str, colour_on: str, fraction: float) -> str:
    """
    Linearly interpolate between two hex colours.

    *fraction* is clamped to [0, 1].
    """
    fraction = max(0.0, min(1.0, fraction))
    r1, g1, b1 = int(colour_off[1:3], 16), int(colour_off[3:5], 16), int(colour_off[5:7], 16)
    r2, g2, b2 = int(colour_on[1:3], 16), int(colour_on[3:5], 16), int(colour_on[5:7], 16)
    r = int(r1 + (r2 - r1) * fraction)
    g = int(g1 + (g2 - g1) * fraction)
    b = int(b1 + (b2 - b1) * fraction)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── Constants ───────────────────────────────────────────────────────────────

_CANVAS_SIZE = 420
_CENTRE = _CANVAS_SIZE // 2
_PORT_RADIUS = 38
_PORT_ORBIT = 145  # distance from centre to port centre
_PLATFORM_RADIUS = 60

# Port positions: 0 = top, going clockwise
_PORT_ANGLES_DEG = [90, 30, 330, 270, 210, 150]  # 0=top, 1=upper-right, ...

_COLOUR_PORT_OFF = "#2a3040"
_COLOUR_PORT_OUTLINE = "#4a5568"
_COLOUR_LED_ON = "#3498db"
_COLOUR_SPOTLIGHT = "#f1c40f"
_COLOUR_VALVE = "#2ecc71"
_COLOUR_PLATFORM_EMPTY = "#1e2530"
_COLOUR_PLATFORM_MOUSE = "#27ae60"
_COLOUR_SPEAKER_ON = "#e67e22"
_COLOUR_IR_ON = "#9b59b6"
_COLOUR_CANVAS_BG = "#141820"
_COLOUR_TEXT = "#cdd5e0"


class VirtualRigWindow:
    """
    Tkinter Toplevel window showing an interactive top-down rig schematic.
    """

    def __init__(self, parent: tk.Misc, state: "VirtualRigState") -> None:
        self._state = state
        self._closed = False

        # ── Window setup ────────────────────────────────────────────────
        self._win = tk.Toplevel(parent)
        self._win.title("Virtual Rig")
        self._win.geometry("480x720")
        self._win.minsize(420, 600)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self._win.configure(bg=Theme.palette.bg_primary)

        # Try to position to the right of the parent
        try:
            parent.update_idletasks()
            px = parent.winfo_x() + parent.winfo_width() + 12
            py = parent.winfo_y()
            self._win.geometry(f"+{px}+{py}")
        except Exception:
            pass

        # ── Main layout ─────────────────────────────────────────────────
        self._build_canvas()
        self._build_controls()
        self._build_gpio_panel()

        # Port canvas item IDs
        self._port_items: list[dict] = []  # [{circle, label, glow, ...}, ...]
        self._platform_item: Optional[int] = None
        self._speaker_item: Optional[int] = None
        self._ir_item: Optional[int] = None

        # Draw the initial rig
        self._draw_rig()

        # Store the last snapshot for diff-based redraws
        self._last_snap: Optional["RigStateSnapshot"] = None

        # Polling-based redraw (~30 fps).  No observer callbacks.
        self._POLL_INTERVAL_MS = 33  # ~30 Hz
        self._poll_timer_id: Optional[str] = None
        self._start_polling()

    # ── Build UI ────────────────────────────────────────────────────────

    def _build_canvas(self) -> None:
        """Create the hex schematic Canvas."""
        frame = ttk.LabelFrame(
            self._win, text="  Rig Schematic  ", padding=6
        )
        frame.pack(fill="x", padx=10, pady=(10, 4))

        self._canvas = tk.Canvas(
            frame,
            width=_CANVAS_SIZE,
            height=_CANVAS_SIZE,
            bg=_COLOUR_CANVAS_BG,
            highlightthickness=0,
        )
        self._canvas.pack(padx=4, pady=4)

    def _build_controls(self) -> None:
        """Create weight slider and mouse-on-platform toggle."""
        frame = ttk.LabelFrame(
            self._win, text="  Platform Weight  ", padding=8
        )
        frame.pack(fill="x", padx=10, pady=4)

        # Weight slider
        slider_frame = ttk.Frame(frame)
        slider_frame.pack(fill="x")

        ttk.Label(slider_frame, text="0 g", style="Muted.TLabel").pack(side="left")
        ttk.Label(slider_frame, text="50 g", style="Muted.TLabel").pack(side="right")

        self._weight_var = tk.DoubleVar(value=0.0)
        self._weight_scale = tk.Scale(
            slider_frame,
            from_=0, to=50,
            resolution=0.1,
            orient="horizontal",
            variable=self._weight_var,
            command=self._on_weight_change,
            bg=Theme.palette.bg_secondary,
            fg=Theme.palette.text_primary,
            troughcolor=Theme.palette.bg_tertiary,
            highlightthickness=0,
            length=340,
        )
        self._weight_scale.pack(fill="x", padx=4, pady=(0, 2))

        # Weight readout and quick-toggle
        bottom_row = ttk.Frame(frame)
        bottom_row.pack(fill="x")

        self._weight_label = ttk.Label(
            bottom_row, text="Weight: 0.0 g",
            font=Theme.font_mono(size=11),
        )
        self._weight_label.pack(side="left", padx=4)

        self._mouse_on_var = tk.BooleanVar(value=False)
        self._mouse_btn = ttk.Checkbutton(
            bottom_row,
            text="Quick: Mouse on (25 g)",
            variable=self._mouse_on_var,
            command=self._on_mouse_toggle,
        )
        self._mouse_btn.pack(side="right", padx=4)

    def _build_gpio_panel(self) -> None:
        """Create the GPIO simulation panel."""
        frame = ttk.LabelFrame(
            self._win, text="  GPIO Pins  ", padding=8
        )
        frame.pack(fill="x", padx=10, pady=(4, 10))

        self._gpio_buttons: list[ttk.Button] = []
        self._gpio_indicators: list[ttk.Label] = []

        grid = ttk.Frame(frame)
        grid.pack(fill="x")

        for pin in range(6):
            col_frame = ttk.Frame(grid)
            col_frame.pack(side="left", expand=True, padx=2)

            lbl = ttk.Label(col_frame, text=f"Pin {pin}", style="Muted.TLabel")
            lbl.pack()

            indicator = ttk.Label(
                col_frame, text="—", width=6, anchor="center",
                font=Theme.font_mono(size=9),
            )
            indicator.pack(pady=(2, 2))
            self._gpio_indicators.append(indicator)

            btn = ttk.Button(
                col_frame, text="Toggle",
                command=lambda p=pin: self._on_gpio_click(p),
                width=7,
            )
            btn.pack()
            self._gpio_buttons.append(btn)

        # Status hint
        self._gpio_hint = ttk.Label(
            frame,
            text="Click Toggle to inject a GPIO event (for INPUT pins)",
            style="Muted.TLabel",
        )
        self._gpio_hint.pack(pady=(4, 0))

    # ── Draw rig schematic ──────────────────────────────────────────────

    def _draw_rig(self) -> None:
        """Draw the initial rig layout on the canvas."""
        c = self._canvas

        # Platform (centre circle)
        r = _PLATFORM_RADIUS
        self._platform_item = c.create_oval(
            _CENTRE - r, _CENTRE - r, _CENTRE + r, _CENTRE + r,
            fill=_COLOUR_PLATFORM_EMPTY, outline="#3a4555", width=2,
        )
        self._platform_text = c.create_text(
            _CENTRE, _CENTRE,
            text="0.0 g", fill=_COLOUR_TEXT,
            font=Theme.font_mono(size=11),
        )

        # Speaker indicator (small circle top-right of platform)
        sx, sy = _CENTRE + _PLATFORM_RADIUS + 18, _CENTRE - _PLATFORM_RADIUS - 18
        self._speaker_item = c.create_oval(
            sx - 10, sy - 10, sx + 10, sy + 10,
            fill=_COLOUR_CANVAS_BG, outline="#4a5568", width=1,
        )
        self._speaker_label = c.create_text(
            sx, sy, text="♪", fill="#555", font=("Segoe UI", 12),
        )

        # IR indicator (small circle top-left of platform)
        ix, iy = _CENTRE - _PLATFORM_RADIUS - 18, _CENTRE - _PLATFORM_RADIUS - 18
        self._ir_item = c.create_oval(
            ix - 10, iy - 10, ix + 10, iy + 10,
            fill=_COLOUR_CANVAS_BG, outline="#4a5568", width=1,
        )
        self._ir_label = c.create_text(
            ix, iy, text="IR", fill="#555", font=("Segoe UI", 8, "bold"),
        )

        # 6 ports
        for port in range(6):
            angle_deg = _PORT_ANGLES_DEG[port]
            angle_rad = math.radians(angle_deg)
            px = _CENTRE + _PORT_ORBIT * math.cos(angle_rad)
            py = _CENTRE - _PORT_ORBIT * math.sin(angle_rad)  # canvas Y is inverted

            r = _PORT_RADIUS

            # Glow ring (invisible at start, shown when LED/spotlight is on)
            glow = c.create_oval(
                px - r - 6, py - r - 6, px + r + 6, py + r + 6,
                fill="", outline="", width=3,
            )

            # Main port circle
            circle = c.create_oval(
                px - r, py - r, px + r, py + r,
                fill=_COLOUR_PORT_OFF, outline=_COLOUR_PORT_OUTLINE, width=2,
            )

            # Port label
            label = c.create_text(
                px, py - 8,
                text=f"Port {port}", fill=_COLOUR_TEXT,
                font=Theme.font(size=9),
            )

            # Sensor label (below port number)
            sensor_lbl = c.create_text(
                px, py + 10,
                text="⬡", fill="#555",
                font=("Segoe UI", 12),
            )

            # Click binding on the port circle
            for item in (circle, label, sensor_lbl):
                c.tag_bind(item, "<Button-1>", lambda e, p=port: self._on_port_click(p))
                c.tag_bind(item, "<Enter>", lambda e, cid=circle: c.configure(cursor="hand2"))
                c.tag_bind(item, "<Leave>", lambda e, cid=circle: c.configure(cursor=""))

            self._port_items.append({
                "circle": circle,
                "label": label,
                "sensor": sensor_lbl,
                "glow": glow,
                "cx": px,
                "cy": py,
            })

    # ── Polling-based redraw ───────────────────────────────────────────

    def _start_polling(self) -> None:
        """Start the fixed-rate polling loop."""
        self._poll_tick()

    def _poll_tick(self) -> None:
        """Called at ~30 Hz.  Takes a snapshot only if state is dirty."""
        if self._closed:
            return
        try:
            snap = self._state.take_snapshot_if_dirty()
            if snap is not None:
                self._redraw(snap)
            self._poll_timer_id = self._win.after(self._POLL_INTERVAL_MS, self._poll_tick)
        except tk.TclError:
            pass  # window destroyed

    def _redraw(self, snap: "RigStateSnapshot") -> None:
        """Redraw only the elements that changed since the last snapshot."""
        if self._closed:
            return
        c = self._canvas
        prev = self._last_snap

        # ── Ports (only update changed ones) ────────────────────────────
        for port in range(6):
            items = self._port_items[port]
            led_br = snap.led_brightness[port]
            spot_br = snap.spotlight_brightness[port]
            valve = snap.valve_pulsing[port]

            # Skip if nothing changed for this port
            if prev is not None and (
                led_br == prev.led_brightness[port]
                and spot_br == prev.spotlight_brightness[port]
                and valve == prev.valve_pulsing[port]
            ):
                continue

            # Port fill: blend with LED colour
            if led_br > 0:
                fill = _lerp_colour(_COLOUR_PORT_OFF, _COLOUR_LED_ON, led_br / 255)
            else:
                fill = _COLOUR_PORT_OFF
            c.itemconfigure(items["circle"], fill=fill)

            # Glow ring: spotlight = yellow, valve = green, LED = blue, off = hidden
            if spot_br > 0:
                glow_colour = _lerp_colour("#332800", _COLOUR_SPOTLIGHT, spot_br / 255)
                c.itemconfigure(items["glow"], outline=glow_colour, width=4)
            elif valve:
                c.itemconfigure(items["glow"], outline=_COLOUR_VALVE, width=4)
            elif led_br > 0:
                c.itemconfigure(items["glow"], outline=_COLOUR_LED_ON, width=2)
            else:
                c.itemconfigure(items["glow"], outline="", width=0)

        # ── Platform (only if weight changed) ───────────────────────────
        if prev is None or snap.platform_weight != prev.platform_weight:
            w = snap.platform_weight
            if w > 5:
                plat_fill = _lerp_colour(
                    _COLOUR_PLATFORM_EMPTY, _COLOUR_PLATFORM_MOUSE, min(w / 30, 1.0)
                )
            else:
                plat_fill = _COLOUR_PLATFORM_EMPTY
            c.itemconfigure(self._platform_item, fill=plat_fill)
            c.itemconfigure(self._platform_text, text=f"{w:.1f} g")

        # ── Speaker (only if changed) ──────────────────────────────────
        if prev is None or snap.speaker_active != prev.speaker_active:
            if snap.speaker_active:
                c.itemconfigure(self._speaker_item, fill=_COLOUR_SPEAKER_ON)
                c.itemconfigure(self._speaker_label, fill="#fff")
            else:
                c.itemconfigure(self._speaker_item, fill=_COLOUR_CANVAS_BG)
                c.itemconfigure(self._speaker_label, fill="#555")

        # ── IR (only if changed) ────────────────────────────────────────
        if prev is None or snap.ir_brightness != prev.ir_brightness:
            if snap.ir_brightness > 0:
                ir_fill = _lerp_colour(
                    _COLOUR_CANVAS_BG, _COLOUR_IR_ON, snap.ir_brightness / 255
                )
                c.itemconfigure(self._ir_item, fill=ir_fill)
                c.itemconfigure(self._ir_label, fill="#fff")
            else:
                c.itemconfigure(self._ir_item, fill=_COLOUR_CANVAS_BG)
                c.itemconfigure(self._ir_label, fill="#555")

        # ── GPIO indicators (only if changed) ──────────────────────────
        for pin in range(6):
            if prev is not None and (
                snap.gpio_modes[pin] == prev.gpio_modes[pin]
                and snap.gpio_output_states[pin] == prev.gpio_output_states[pin]
            ):
                continue

            mode = snap.gpio_modes[pin]
            out_state = snap.gpio_output_states[pin]
            indicator = self._gpio_indicators[pin]
            btn = self._gpio_buttons[pin]

            if mode is None:
                indicator.configure(text="—")
                btn.state(["disabled"])
            elif mode.value == 0:  # OUTPUT
                indicator.configure(text="OUT:" + ("HI" if out_state else "LO"))
                btn.state(["disabled"])
            else:  # INPUT
                indicator.configure(text="INPUT")
                btn.state(["!disabled"])

        self._last_snap = snap

    # ── User interactions ───────────────────────────────────────────────

    def _on_port_click(self, port: int) -> None:
        """User clicked a port — inject a sensor event (beam break)."""
        self._state.inject_sensor_event(port, is_activation=True)
        # Brief visual flash on the sensor icon
        items = self._port_items[port]
        self._canvas.itemconfigure(items["sensor"], fill="#fff")
        self._win.after(200, lambda: self._canvas.itemconfigure(items["sensor"], fill="#555"))

    def _on_weight_change(self, value: str) -> None:
        """Weight slider moved."""
        w = float(value)
        self._state.set_weight(w)
        self._weight_label.configure(text=f"Weight: {w:.1f} g")

    def _on_mouse_toggle(self) -> None:
        """Quick toggle button for mouse on/off platform."""
        if self._mouse_on_var.get():
            self._weight_var.set(25.0)
            self._weight_scale.set(25.0)
            self._state.set_weight(25.0)
            self._weight_label.configure(text="Weight: 25.0 g")
        else:
            self._weight_var.set(0.0)
            self._weight_scale.set(0.0)
            self._state.set_weight(0.0)
            self._weight_label.configure(text="Weight: 0.0 g")

    def _on_gpio_click(self, pin: int) -> None:
        """User clicked GPIO toggle — inject a GPIO event."""
        self._state.inject_gpio_event(pin, is_activation=True)
        # Brief visual flash
        btn = self._gpio_buttons[pin]
        original_text = btn.cget("text")
        btn.configure(text="⚡")
        self._win.after(300, lambda: btn.configure(text=original_text))

    # ── Lifecycle ───────────────────────────────────────────────────────

    def _on_close_request(self) -> None:
        """User tried to close the virtual rig window directly."""
        # Don't allow closing while session is running — just hide
        self._win.withdraw()

    def close(self) -> None:
        """Programmatic close (called by rig_window cleanup)."""
        if self._closed:
            return
        self._closed = True
        # Cancel the polling timer
        if self._poll_timer_id is not None:
            try:
                self._win.after_cancel(self._poll_timer_id)
            except (tk.TclError, ValueError):
                pass
            self._poll_timer_id = None
        try:
            self._win.destroy()
        except tk.TclError:
            pass

    def show(self) -> None:
        """Show the window if it was hidden."""
        if not self._closed:
            try:
                self._win.deiconify()
            except tk.TclError:
                pass
