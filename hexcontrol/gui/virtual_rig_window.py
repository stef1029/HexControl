"""
Virtual Rig Window — Interactive top-down hex rig visualisation (DearPyGui).

Opens as a DPG window alongside the RigWindow when in simulate mode.
Renders the 6-port hexagonal rig with clickable nose-poke ports, a weight
slider for platform simulation, GPIO toggles, and real-time visual feedback
for LEDs, spotlights, valves, speaker and IR state.
"""

from __future__ import annotations

import math
from typing import Optional, TYPE_CHECKING

import dearpygui.dearpygui as dpg

from .dpg_app import frame_poller
from .theme import Theme, hex_to_rgba

if TYPE_CHECKING:
    from BehavLink.simulation import VirtualRigState, RigStateSnapshot


# ── Constants ───────────────────────────────────────────────────────────

_CANVAS_SIZE = 420
_CENTRE = _CANVAS_SIZE // 2
_PORT_RADIUS = 38
_PORT_ORBIT = 145
_PLATFORM_RADIUS = 60

_PORT_ANGLES_DEG = [90, 30, 330, 270, 210, 150]

_COLOUR_PORT_OFF = [42, 48, 64, 255]
_COLOUR_PORT_OUTLINE = [74, 85, 104, 255]
_COLOUR_LED_ON = [52, 152, 219, 255]
_COLOUR_SPOTLIGHT = [241, 196, 15, 255]
_COLOUR_VALVE = [46, 204, 113, 255]
_COLOUR_PLATFORM_EMPTY = [30, 37, 48, 255]
_COLOUR_PLATFORM_MOUSE = [39, 174, 96, 255]
_COLOUR_SPEAKER_ON = [230, 126, 34, 255]
_COLOUR_IR_ON = [155, 89, 182, 255]
_COLOUR_CANVAS_BG = [20, 24, 32, 255]
_COLOUR_TEXT = [205, 213, 224, 255]
_COLOUR_DIM = [85, 85, 85, 255]


def _lerp_colour(c_off: list[int], c_on: list[int], fraction: float) -> list[int]:
    fraction = max(0.0, min(1.0, fraction))
    return [
        int(c_off[i] + (c_on[i] - c_off[i]) * fraction)
        for i in range(4)
    ]


class VirtualRigWindow:
    """DPG window showing an interactive top-down rig schematic."""

    def __init__(self, parent: int | str, state: "VirtualRigState") -> None:
        self._state = state
        self._closed = False

        self._port_items: list[dict] = []
        self._platform_item: int | None = None
        self._platform_text: int | None = None
        self._speaker_item: int | None = None
        self._speaker_text: int | None = None
        self._ir_item: int | None = None
        self._ir_text: int | None = None

        self._weight_text: int | None = None
        self._gpio_indicators: list[int] = []
        self._gpio_buttons: list[int] = []
        self._daq_indicators: list[int] = []

        self._last_snap: Optional["RigStateSnapshot"] = None

        self._build_window()
        self._draw_rig()

        # Start polling
        frame_poller.register(33, self._poll_tick)

    def _build_window(self) -> None:
        palette = Theme.palette
        self._window_id = dpg.add_window(
            label="Virtual Rig", width=500, height=720,
            on_close=self._on_close_request,
        )

        # Rig schematic drawlist
        with dpg.collapsing_header(label="Rig Schematic", default_open=True,
                                   parent=self._window_id):
            self._drawlist = dpg.add_drawlist(
                width=_CANVAS_SIZE, height=_CANVAS_SIZE,
                parent=dpg.last_item(),
            )

        # Platform Weight controls
        with dpg.collapsing_header(label="Platform Weight", default_open=True,
                                   parent=self._window_id):
            with dpg.group(horizontal=True):
                dpg.add_text("0 g", color=hex_to_rgba(palette.text_secondary))
                dpg.add_slider_float(
                    min_value=0, max_value=50, default_value=0,
                    width=300, format="%.1f g",
                    callback=self._on_weight_change, tag="vr_weight_slider",
                )
                dpg.add_text("50 g", color=hex_to_rgba(palette.text_secondary))
            with dpg.group(horizontal=True):
                self._weight_text = dpg.add_text("Weight: 0.0 g")
                dpg.add_checkbox(
                    label="Quick: Mouse on (25g)",
                    callback=self._on_mouse_toggle, tag="vr_mouse_toggle",
                )

        # GPIO pins
        with dpg.collapsing_header(label="GPIO Pins", default_open=True,
                                   parent=self._window_id):
            with dpg.group(horizontal=True):
                for pin in range(4):
                    with dpg.group():
                        dpg.add_text(f"Pin {pin}", color=hex_to_rgba(palette.text_secondary))
                        indicator = dpg.add_text("--")
                        self._gpio_indicators.append(indicator)
                        btn = dpg.add_button(
                            label="Toggle",
                            callback=lambda s, a, p=pin: self._on_gpio_click(p),
                        )
                        self._gpio_buttons.append(btn)

        # DAQ link pins
        with dpg.collapsing_header(label="DAQ Link Pins", default_open=True,
                                   parent=self._window_id):
            with dpg.group(horizontal=True):
                for idx in range(2):
                    with dpg.group():
                        dpg.add_text(f"DAQ {idx}", color=hex_to_rgba(palette.text_secondary))
                        indicator = dpg.add_text("LO")
                        self._daq_indicators.append(indicator)

    def _draw_rig(self) -> None:
        dl = self._drawlist

        # Platform
        self._platform_item = dpg.draw_circle(
            center=[_CENTRE, _CENTRE], radius=_PLATFORM_RADIUS,
            fill=_COLOUR_PLATFORM_EMPTY, color=[58, 69, 85, 255], thickness=2,
            parent=dl,
        )
        self._platform_text = dpg.draw_text(
            pos=[_CENTRE - 20, _CENTRE - 6], text="0.0 g",
            color=_COLOUR_TEXT, size=14, parent=dl,
        )

        # Speaker indicator
        sx, sy = _CENTRE + _PLATFORM_RADIUS + 18, _CENTRE - _PLATFORM_RADIUS - 18
        self._speaker_item = dpg.draw_circle(
            center=[sx, sy], radius=10,
            fill=_COLOUR_CANVAS_BG, color=_COLOUR_PORT_OUTLINE, thickness=1,
            parent=dl,
        )
        self._speaker_text = dpg.draw_text(
            pos=[sx - 4, sy - 6], text="M", color=_COLOUR_DIM, size=12, parent=dl,
        )

        # IR indicator
        ix, iy = _CENTRE - _PLATFORM_RADIUS - 18, _CENTRE - _PLATFORM_RADIUS - 18
        self._ir_item = dpg.draw_circle(
            center=[ix, iy], radius=10,
            fill=_COLOUR_CANVAS_BG, color=_COLOUR_PORT_OUTLINE, thickness=1,
            parent=dl,
        )
        self._ir_text = dpg.draw_text(
            pos=[ix - 5, iy - 5], text="IR", color=_COLOUR_DIM, size=10, parent=dl,
        )

        # 6 Ports
        for port in range(6):
            angle_deg = _PORT_ANGLES_DEG[port]
            angle_rad = math.radians(angle_deg)
            px = _CENTRE + _PORT_ORBIT * math.cos(angle_rad)
            py = _CENTRE - _PORT_ORBIT * math.sin(angle_rad)

            glow = dpg.draw_circle(
                center=[px, py], radius=_PORT_RADIUS + 6,
                fill=[0, 0, 0, 0], color=[0, 0, 0, 0], thickness=3,
                parent=dl,
            )
            circle = dpg.draw_circle(
                center=[px, py], radius=_PORT_RADIUS,
                fill=_COLOUR_PORT_OFF, color=_COLOUR_PORT_OUTLINE, thickness=2,
                parent=dl,
            )
            label = dpg.draw_text(
                pos=[px - 18, py - 12], text=f"Port {port}",
                color=_COLOUR_TEXT, size=12, parent=dl,
            )

            self._port_items.append({
                "circle": circle,
                "glow": glow,
                "label": label,
                "cx": px, "cy": py,
            })

        # Click handler for the drawlist — hit-test port circles
        with dpg.item_handler_registry() as handler:
            dpg.add_item_clicked_handler(callback=self._on_canvas_click)
        dpg.bind_item_handler_registry(self._drawlist, handler)

    def _on_canvas_click(self, sender, app_data) -> None:
        mx, my = dpg.get_drawing_mouse_pos()
        for port, items in enumerate(self._port_items):
            dx = mx - items["cx"]
            dy = my - items["cy"]
            if dx * dx + dy * dy <= _PORT_RADIUS * _PORT_RADIUS:
                self._on_port_click(port)
                break

    # ── Polling-based redraw ───────────────────────────────────────────

    def _poll_tick(self) -> None:
        if self._closed:
            return
        snap = self._state.take_snapshot_if_dirty()
        if snap is not None:
            self._redraw(snap)

    def _redraw(self, snap: "RigStateSnapshot") -> None:
        if self._closed:
            return
        prev = self._last_snap

        for port in range(6):
            items = self._port_items[port]
            led_br = snap.led_brightness[port]
            spot_br = snap.spotlight_brightness[port]
            valve = snap.valve_pulsing[port]

            if prev is not None and (
                led_br == prev.led_brightness[port]
                and spot_br == prev.spotlight_brightness[port]
                and valve == prev.valve_pulsing[port]
            ):
                continue

            if led_br > 0:
                fill = _lerp_colour(_COLOUR_PORT_OFF, _COLOUR_LED_ON, led_br / 255)
            else:
                fill = _COLOUR_PORT_OFF
            dpg.configure_item(items["circle"], fill=fill)

            if spot_br > 0:
                glow_colour = _lerp_colour([51, 40, 0, 255], _COLOUR_SPOTLIGHT, spot_br / 255)
                dpg.configure_item(items["glow"], color=glow_colour, thickness=4)
            elif valve:
                dpg.configure_item(items["glow"], color=_COLOUR_VALVE, thickness=4)
            elif led_br > 0:
                dpg.configure_item(items["glow"], color=_COLOUR_LED_ON, thickness=2)
            else:
                dpg.configure_item(items["glow"], color=[0, 0, 0, 0], thickness=0)

        # Platform
        if prev is None or snap.platform_weight != prev.platform_weight:
            w = snap.platform_weight
            if w > 5:
                plat_fill = _lerp_colour(
                    _COLOUR_PLATFORM_EMPTY, _COLOUR_PLATFORM_MOUSE, min(w / 30, 1.0)
                )
            else:
                plat_fill = _COLOUR_PLATFORM_EMPTY
            dpg.configure_item(self._platform_item, fill=plat_fill)
            dpg.configure_item(self._platform_text, text=f"{w:.1f} g")

        # Speaker
        if prev is None or snap.speaker_active != prev.speaker_active:
            if snap.speaker_active:
                dpg.configure_item(self._speaker_item, fill=_COLOUR_SPEAKER_ON)
                dpg.configure_item(self._speaker_text, color=[255, 255, 255, 255])
            else:
                dpg.configure_item(self._speaker_item, fill=_COLOUR_CANVAS_BG)
                dpg.configure_item(self._speaker_text, color=_COLOUR_DIM)

        # IR
        if prev is None or snap.ir_brightness != prev.ir_brightness:
            if snap.ir_brightness > 0:
                ir_fill = _lerp_colour(
                    _COLOUR_CANVAS_BG, _COLOUR_IR_ON, snap.ir_brightness / 255
                )
                dpg.configure_item(self._ir_item, fill=ir_fill)
                dpg.configure_item(self._ir_text, color=[255, 255, 255, 255])
            else:
                dpg.configure_item(self._ir_item, fill=_COLOUR_CANVAS_BG)
                dpg.configure_item(self._ir_text, color=_COLOUR_DIM)

        # GPIO
        for pin in range(4):
            if prev is not None and (
                snap.gpio_modes[pin] == prev.gpio_modes[pin]
                and snap.gpio_output_states[pin] == prev.gpio_output_states[pin]
            ):
                continue
            mode = snap.gpio_modes[pin]
            out_state = snap.gpio_output_states[pin]
            ind = self._gpio_indicators[pin]
            btn = self._gpio_buttons[pin]
            if mode is None:
                dpg.set_value(ind, "--")
                dpg.configure_item(btn, enabled=False)
            elif mode.value == 0:  # OUTPUT
                dpg.set_value(ind, "OUT:" + ("HI" if out_state else "LO"))
                dpg.configure_item(btn, enabled=False)
            else:  # INPUT
                dpg.set_value(ind, "INPUT")
                dpg.configure_item(btn, enabled=True)

        # DAQ link
        for idx in range(2):
            if prev is not None and snap.daq_link_states[idx] == prev.daq_link_states[idx]:
                continue
            state = snap.daq_link_states[idx]
            dpg.set_value(self._daq_indicators[idx], "HI" if state else "LO")

        self._last_snap = snap

    # ── User interactions ───────────────────────────────────────────────

    def _on_port_click(self, port: int) -> None:
        self._state.inject_sensor_event(port, is_activation=True)

    def _on_weight_change(self, sender, app_data) -> None:
        w = app_data
        self._state.set_weight(w)
        if self._weight_text and dpg.does_item_exist(self._weight_text):
            dpg.set_value(self._weight_text, f"Weight: {w:.1f} g")

    def _on_mouse_toggle(self, sender, app_data) -> None:
        if app_data:
            dpg.set_value("vr_weight_slider", 25.0)
            self._state.set_weight(25.0)
            if self._weight_text:
                dpg.set_value(self._weight_text, "Weight: 25.0 g")
        else:
            dpg.set_value("vr_weight_slider", 0.0)
            self._state.set_weight(0.0)
            if self._weight_text:
                dpg.set_value(self._weight_text, "Weight: 0.0 g")

    def _on_gpio_click(self, pin: int) -> None:
        self._state.inject_gpio_event(pin, is_activation=True)

    # ── Lifecycle ───────────────────────────────────────────────────────

    def _on_close_request(self) -> None:
        # Don't destroy, just hide
        if self._window_id and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        frame_poller.unregister(self._poll_tick)
        if hasattr(self, '_window_id') and dpg.does_item_exist(self._window_id):
            dpg.delete_item(self._window_id)

    def show(self) -> None:
        if not self._closed and hasattr(self, '_window_id') and dpg.does_item_exist(self._window_id):
            dpg.configure_item(self._window_id, show=True)
