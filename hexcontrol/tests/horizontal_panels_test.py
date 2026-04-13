#!/usr/bin/env python3
"""
Test script for horizontal panel layout with dynamic add/remove.

Simulates the rig window layout where multiple panels sit side by side,
each filling an equal share of the available width, and scale when
panels are added or removed.

Run:
    python hexcontrol/tests/horizontal_panels_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import dearpygui.dearpygui as dpg
from hexcontrol.gui.theme import Theme, apply_theme, hex_to_rgba


def main() -> None:
    dpg.create_context()
    dpg.create_viewport(title="Horizontal Panels Test (add/remove)", width=1200, height=700)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    apply_theme()
    palette = Theme.palette

    # State
    panels: list[dict] = []  # [{id, label, container}]
    panel_counter = [0]

    with dpg.window(tag="test_main", no_title_bar=True, no_scrollbar=True,
                    no_scroll_with_mouse=True):

        # Controls
        with dpg.group(horizontal=True):
            dpg.add_button(label="Add Panel", callback=lambda: add_panel())
            dpg.add_button(label="Remove Last", callback=lambda: remove_last())
            dpg.add_button(label="Remove First", callback=lambda: remove_first())

        status = dpg.add_text("0 panels", tag="status_text")
        dpg.add_separator()

        # The horizontal container for panels
        panel_row = dpg.add_group(horizontal=True, tag="panel_row")

    dpg.set_primary_window("test_main", True)

    def recalc_widths():
        """Recalculate each panel's width to split evenly."""
        if not panels:
            return
        # Get available width from the viewport
        total_w = dpg.get_viewport_client_width() - 30  # margin
        panel_w = max(200, total_w // len(panels))
        for p in panels:
            if dpg.does_item_exist(p["container"]):
                dpg.configure_item(p["container"], width=panel_w)
        dpg.set_value("status_text",
                      f"{len(panels)} panels, {panel_w}px each")

    def add_panel():
        panel_counter[0] += 1
        idx = panel_counter[0]
        label = f"Panel {idx}"

        # Create a child window inside the horizontal group
        container = dpg.add_child_window(
            width=300, height=-1, parent="panel_row",
            border=True,
        )

        # Fill with some content
        t = dpg.add_text(label, parent=container,
                         color=hex_to_rgba(palette.accent_primary))
        if Theme.font_heading():
            dpg.bind_item_font(t, Theme.font_heading())
        dpg.add_separator(parent=container)

        dpg.add_text(f"This is panel #{idx}", parent=container)
        dpg.add_text("Content scales with width", parent=container,
                     color=hex_to_rgba(palette.text_secondary))
        dpg.add_spacer(height=10, parent=container)
        dpg.add_button(label=f"Button in {label}", width=-1, parent=container)
        dpg.add_spacer(height=10, parent=container)
        dpg.add_input_text(label="Input", width=-1, parent=container)
        dpg.add_spacer(height=10, parent=container)

        # A small plot to show it scales
        with dpg.plot(label="Plot", height=150, width=-1, parent=container):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="x")
            with dpg.plot_axis(dpg.mvYAxis, label="y"):
                import math
                xs = [i * 0.1 for i in range(50)]
                ys = [math.sin(x + idx) for x in xs]
                dpg.add_line_series(xs, ys, label=f"sin(x+{idx})")

        panels.append({"id": idx, "label": label, "container": container})
        recalc_widths()

    def remove_last():
        if not panels:
            return
        p = panels.pop()
        if dpg.does_item_exist(p["container"]):
            dpg.delete_item(p["container"])
        recalc_widths()
        if not panels:
            dpg.set_value("status_text", "0 panels")

    def remove_first():
        if not panels:
            return
        p = panels.pop(0)
        if dpg.does_item_exist(p["container"]):
            dpg.delete_item(p["container"])
        recalc_widths()
        if not panels:
            dpg.set_value("status_text", "0 panels")

    # Add 2 initial panels
    add_panel()
    add_panel()

    # Manual render loop to handle viewport resize
    last_vw = 0
    while dpg.is_dearpygui_running():
        vw = dpg.get_viewport_client_width()
        if vw != last_vw:
            last_vw = vw
            recalc_widths()
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
