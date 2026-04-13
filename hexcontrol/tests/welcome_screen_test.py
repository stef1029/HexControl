#!/usr/bin/env python3
"""
Test script for the welcome screen drawlist + generative art.

Tests:
- Generative art rendering on a drawlist
- Centered text overlay card
- Dynamic resizing: art and text reposition when viewport is resized

Run:
    python hexcontrol/tests/welcome_screen_test.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import dearpygui.dearpygui as dpg
from hexcontrol.gui.theme import Theme, apply_theme, hex_to_rgba
from hexcontrol.gui.launcher_background import _GENERATORS


def _estimate_text_width(text: str, font_size: float) -> float:
    return len(text) * font_size * 0.55


def _draw_centered_text(dl, text, cx, y, font_size, color):
    text_w = _estimate_text_width(text, font_size)
    dpg.draw_text(
        pos=[cx - text_w / 2, y], text=text, size=font_size,
        color=color, parent=dl,
    )


def _draw_overlay(dl, w, h, palette):
    card_w = min(520, w - 60)
    card_h = 150
    card_x = (w - card_w) / 2
    card_y = (h - card_h) / 2 - 30
    card_cx = card_x + card_w / 2

    dpg.draw_rectangle(
        pmin=[card_x, card_y], pmax=[card_x + card_w, card_y + card_h],
        fill=hex_to_rgba(palette.bg_primary, alpha=200),
        color=[0, 0, 0, 0], rounding=10, parent=dl,
    )
    dpg.draw_rectangle(
        pmin=[card_x, card_y], pmax=[card_x + card_w, card_y + card_h],
        fill=[0, 0, 0, 0], color=hex_to_rgba(palette.border_medium, alpha=120),
        rounding=10, thickness=1, parent=dl,
    )
    _draw_centered_text(dl, "Hex Behaviour System", card_cx, card_y + 28,
                        28, hex_to_rgba(palette.text_primary))
    _draw_centered_text(dl, "Select a rig from the sidebar to begin",
                        card_cx, card_y + 75, 15,
                        hex_to_rgba(palette.text_secondary))
    _draw_centered_text(dl, f"Drawlist size: {w} x {h}",
                        card_cx, card_y + 110, 12,
                        hex_to_rgba(palette.text_disabled))


def main() -> None:
    dpg.create_context()
    dpg.create_viewport(title="Welcome Screen Test (resize me!)", width=1000, height=700)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    apply_theme()
    palette = Theme.palette

    state = {
        "last_size": (0, 0),
        "gen_index": 0,
        "current_gen": None,
        "rng_seed": random.randint(0, 999999),
    }

    with dpg.window(tag="test_main", no_title_bar=True, no_scrollbar=True):

        # Controls
        with dpg.group(horizontal=True):
            dpg.add_button(label="Redraw (random)", callback=lambda: pick_random())
            dpg.add_button(label="Next generator", callback=lambda: next_gen())
            dpg.add_button(label="Clear", callback=lambda: clear())

        dpg.add_text("Resize the window to test scaling", tag="state_text")
        dpg.add_separator()

        # The drawlist — fills remaining space
        dl = dpg.add_drawlist(width=800, height=500, tag="dl_main")

    dpg.set_primary_window("test_main", True)

    def redraw():
        """Clear and redraw art + overlay at current drawlist size."""
        w = dpg.get_item_width(dl)
        h = dpg.get_item_height(dl)
        if w < 50 or h < 50:
            return

        dpg.delete_item(dl, children_only=True)

        gen = state["current_gen"] or random.choice(_GENERATORS)
        rng = random.Random(state["rng_seed"])
        gen(dl, w, h, rng)
        _draw_overlay(dl, w, h, palette)

        children = dpg.get_item_children(dl, 2) or []
        dpg.set_value("state_text",
                      f"{gen.__name__} | {w}x{h} | {len(children)} items | seed={state['rng_seed']}")

    def pick_random():
        state["current_gen"] = random.choice(_GENERATORS)
        state["rng_seed"] = random.randint(0, 999999)
        state["last_size"] = (0, 0)  # force redraw

    def next_gen():
        state["gen_index"] = (state["gen_index"] + 1) % len(_GENERATORS)
        state["current_gen"] = _GENERATORS[state["gen_index"]]
        state["rng_seed"] = random.randint(0, 999999)
        state["last_size"] = (0, 0)

    def clear():
        dpg.delete_item(dl, children_only=True)
        dpg.set_value("state_text", "Cleared")

    # Initial draw
    state["current_gen"] = random.choice(_GENERATORS)
    redraw()

    # Manual render loop to handle resizing
    while dpg.is_dearpygui_running():
        # Check if viewport size changed — resize drawlist and redraw
        vw = dpg.get_viewport_client_width()
        vh = dpg.get_viewport_client_height()

        # Drawlist should fill the window below the controls (~50px for header)
        target_w = max(100, vw - 20)
        target_h = max(100, vh - 70)

        current_size = (target_w, target_h)
        if current_size != state["last_size"]:
            state["last_size"] = current_size
            dpg.configure_item(dl, width=target_w, height=target_h)
            redraw()

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
