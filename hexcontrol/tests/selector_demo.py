#!/usr/bin/env python3
"""
Demo of all dropdown / selector / expandable / input widget types in DearPyGui.

Shows each type so you can compare and decide which fits best for
protocol selection or other UI needs.

Run:
    python hexcontrol/tests/selector_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import dearpygui.dearpygui as dpg
from hexcontrol.gui.theme import Theme, apply_theme, hex_to_rgba


PROTOCOLS = [
    "Auto Training Visual",
    "Auto Training Audio",
    "Auto Training Audio Spatial",
    "Cue Conflict Test",
]


def main() -> None:
    dpg.create_context()
    dpg.create_viewport(title="Selector / Widget Demo", width=1200, height=900)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    apply_theme()
    palette = Theme.palette

    with dpg.window(tag="demo_main", no_title_bar=True):

        t = dpg.add_text("Selector & Input Widget Types",
                         color=hex_to_rgba(palette.text_primary))
        if Theme.font_heading():
            dpg.bind_item_font(t, Theme.font_heading())
        dpg.add_text("All available selection/input patterns in DearPyGui",
                     color=hex_to_rgba(palette.text_secondary))
        dpg.add_separator()
        dpg.add_spacer(height=6)

        # ── 1. Combo (standard dropdown) ────────────────────────────
        with dpg.collapsing_header(label="1. Combo (standard dropdown)", default_open=True):
            dpg.add_text("dpg.add_combo() — compact dropdown, single line",
                         color=hex_to_rgba(palette.text_secondary))
            result1 = dpg.add_text("Selected: (none)")
            dpg.add_combo(
                items=PROTOCOLS, label="Protocol",
                default_value=PROTOCOLS[0], width=350,
                callback=lambda s, a: dpg.set_value(result1, f"Selected: {a}"),
            )

        dpg.add_spacer(height=6)

        # ── 2. Combo height variants ────────────────────────────────
        with dpg.collapsing_header(label="2. Combo height variants", default_open=False):
            dpg.add_text("height_mode controls how tall the popup is",
                         color=hex_to_rgba(palette.text_secondary))
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("Small:")
                    dpg.add_combo(items=PROTOCOLS, default_value=PROTOCOLS[0],
                                  width=220, height_mode=dpg.mvComboHeight_Small)
                with dpg.group():
                    dpg.add_text("Regular:")
                    dpg.add_combo(items=PROTOCOLS, default_value=PROTOCOLS[0],
                                  width=220, height_mode=dpg.mvComboHeight_Regular)
                with dpg.group():
                    dpg.add_text("Large:")
                    dpg.add_combo(items=PROTOCOLS, default_value=PROTOCOLS[0],
                                  width=220, height_mode=dpg.mvComboHeight_Large)

        dpg.add_spacer(height=6)

        # ── 3. Listbox ──────────────────────────────────────────────
        with dpg.collapsing_header(label="3. Listbox (always-visible list)", default_open=False):
            dpg.add_text("dpg.add_listbox() — all options visible, click to select",
                         color=hex_to_rgba(palette.text_secondary))
            result3 = dpg.add_text("Selected: (none)")
            dpg.add_listbox(
                items=PROTOCOLS, default_value=PROTOCOLS[0],
                num_items=len(PROTOCOLS), width=350,
                callback=lambda s, a: dpg.set_value(result3, f"Selected: {a}"),
            )

        dpg.add_spacer(height=6)

        # ── 4. Radio buttons (vertical) ─────────────────────────────
        with dpg.collapsing_header(label="4. Radio buttons (vertical)", default_open=False):
            dpg.add_text("dpg.add_radio_button() — one selection, all visible",
                         color=hex_to_rgba(palette.text_secondary))
            result4 = dpg.add_text("Selected: (none)")
            dpg.add_radio_button(
                items=PROTOCOLS, default_value=PROTOCOLS[0],
                callback=lambda s, a: dpg.set_value(result4, f"Selected: {a}"),
            )

        dpg.add_spacer(height=6)

        # ── 5. Radio buttons (horizontal) ───────────────────────────
        with dpg.collapsing_header(label="5. Radio buttons (horizontal)", default_open=False):
            dpg.add_text("dpg.add_radio_button(horizontal=True)",
                         color=hex_to_rgba(palette.text_secondary))
            result5 = dpg.add_text("Selected: (none)")
            dpg.add_radio_button(
                items=PROTOCOLS, default_value=PROTOCOLS[0], horizontal=True,
                callback=lambda s, a: dpg.set_value(result5, f"Selected: {a}"),
            )

        dpg.add_spacer(height=6)

        # ── 6. Selectable items ─────────────────────────────────────
        with dpg.collapsing_header(label="6. Selectable items (menu-style)", default_open=False):
            dpg.add_text("dpg.add_selectable() — toggleable items, custom deselect",
                         color=hex_to_rgba(palette.text_secondary))
            result6 = dpg.add_text("Selected: (none)")
            selectables = []

            def on_sel(sender, app_data):
                for s in selectables:
                    if s != sender:
                        dpg.set_value(s, False)
                dpg.set_value(result6, f"Selected: {dpg.get_item_label(sender)}")

            for proto in PROTOCOLS:
                sel = dpg.add_selectable(label=proto, width=350, callback=on_sel)
                selectables.append(sel)
            dpg.set_value(selectables[0], True)

        dpg.add_spacer(height=6)

        # ── 7. Collapsing headers (accordion) ───────────────────────
        with dpg.collapsing_header(label="7. Accordion (collapsing headers)", default_open=False):
            dpg.add_text("Expand one to see its content inline",
                         color=hex_to_rgba(palette.text_secondary))
            for proto in PROTOCOLS:
                with dpg.collapsing_header(label=proto, default_open=False):
                    dpg.add_text(f"Parameters for {proto}",
                                 color=hex_to_rgba(palette.text_secondary))
                    dpg.add_input_int(label="Trials", default_value=1000, width=180)
                    dpg.add_input_float(label="Duration", default_value=60.0, width=180)

        dpg.add_spacer(height=6)

        # ── 8. Tree nodes ───────────────────────────────────────────
        with dpg.collapsing_header(label="8. Tree nodes (hierarchical)", default_open=False):
            dpg.add_text("dpg.add_tree_node() — expandable tree",
                         color=hex_to_rgba(palette.text_secondary))
            with dpg.tree_node(label="All Protocols", default_open=True):
                for proto in PROTOCOLS:
                    with dpg.tree_node(label=proto, leaf=True):
                        dpg.add_text(f"Leaf content for {proto}")

        dpg.add_spacer(height=6)

        # ── 9. Popup (right-click context menu) ─────────────────────
        with dpg.collapsing_header(label="9. Popup (right-click context menu)", default_open=True):
            dpg.add_text("dpg.popup() — appears on right-click of a target widget",
                         color=hex_to_rgba(palette.text_secondary))
            result9 = dpg.add_text("Selected: (none)")
            popup_btn = dpg.add_button(label="Right-click me for protocol menu", width=350)
            with dpg.popup(popup_btn, tag="proto_popup"):
                for proto in PROTOCOLS:
                    dpg.add_selectable(
                        label=proto, width=300,
                        callback=lambda s, a, u=proto: (
                            dpg.set_value(result9, f"Selected: {u}"),
                            dpg.configure_item("proto_popup", show=False),
                        ),
                    )

        dpg.add_spacer(height=6)

        # ── 10. Popup (left-click, modal) ───────────────────────────
        with dpg.collapsing_header(label="10. Modal popup (left-click)", default_open=True):
            dpg.add_text("Modal popup — blocks background, must choose or dismiss",
                         color=hex_to_rgba(palette.text_secondary))
            result10 = dpg.add_text("Selected: (none)")
            modal_btn = dpg.add_button(label="Click to choose protocol (modal)", width=350)
            with dpg.popup(modal_btn, modal=True, mousebutton=dpg.mvMouseButton_Left,
                          tag="modal_popup"):
                dpg.add_text("Choose a protocol:")
                dpg.add_separator()
                for proto in PROTOCOLS:
                    dpg.add_selectable(
                        label=proto, width=300,
                        callback=lambda s, a, u=proto: (
                            dpg.set_value(result10, f"Selected: {u}"),
                            dpg.configure_item("modal_popup", show=False),
                        ),
                    )
                dpg.add_separator()
                dpg.add_button(label="Cancel", width=100,
                              callback=lambda: dpg.configure_item("modal_popup", show=False))

        dpg.add_spacer(height=6)

        # ── 11. Knob float ──────────────────────────────────────────
        with dpg.collapsing_header(label="11. Knob float (rotary dial)", default_open=True):
            dpg.add_text("dpg.add_knob_float() — rotary knob input",
                         color=hex_to_rgba(palette.text_secondary))
            with dpg.group(horizontal=True):
                dpg.add_knob_float(label="Speed", default_value=0.5, min_value=0, max_value=1)
                dpg.add_knob_float(label="Volume", default_value=25, min_value=0, max_value=100)
                dpg.add_knob_float(label="Mix", default_value=75, min_value=0, max_value=100)

        dpg.add_spacer(height=6)

        # ── 12. Color button / picker ───────────────────────────────
        with dpg.collapsing_header(label="12. Color button & picker", default_open=True):
            dpg.add_text("dpg.add_color_button() — clickable color swatch",
                         color=hex_to_rgba(palette.text_secondary))
            with dpg.group(horizontal=True):
                dpg.add_color_button(default_value=[255, 0, 0, 255], width=40, height=40)
                dpg.add_color_button(default_value=[0, 255, 0, 255], width=40, height=40)
                dpg.add_color_button(default_value=[0, 0, 255, 255], width=40, height=40)
                dpg.add_color_button(default_value=[255, 255, 0, 255], width=40, height=40)
            dpg.add_text("dpg.add_color_edit() — inline color editor",
                         color=hex_to_rgba(palette.text_secondary))
            dpg.add_color_edit(default_value=[128, 64, 200, 255], width=300)

        dpg.add_spacer(height=6)

        # ── 13. Loading indicator ───────────────────────────────────
        with dpg.collapsing_header(label="13. Loading indicators", default_open=True):
            dpg.add_text("dpg.add_loading_indicator() — animated spinner",
                         color=hex_to_rgba(palette.text_secondary))
            with dpg.group(horizontal=True):
                dpg.add_loading_indicator(style=0, radius=3.0,
                                          color=hex_to_rgba(palette.accent_primary))
                dpg.add_text("  Style 0 (dots)  ")
                dpg.add_loading_indicator(style=1, radius=3.0,
                                          color=hex_to_rgba(palette.accent_primary))
                dpg.add_text("  Style 1 (spinner)  ")

        dpg.add_spacer(height=6)

        # ── 14. Filter set ──────────────────────────────────────────
        with dpg.collapsing_header(label="14. Filter set (searchable list)", default_open=True):
            dpg.add_text("dpg.add_filter_set() — type to filter items. Try typing below:",
                         color=hex_to_rgba(palette.text_secondary))
            filter_id = dpg.add_filter_set()
            dpg.add_input_text(
                label="Search", width=350, hint="Type to filter...",
                callback=lambda s, a: dpg.set_value(filter_id, a),
            )
            items = PROTOCOLS + [
                "Passive Viewing", "Reward Only", "Habituation",
                "Open Field", "Social Interaction", "Novel Object",
            ]
            for item in items:
                dpg.add_text(item, parent=filter_id, filter_key=item)

        dpg.add_spacer(height=6)

        # ── 15. Input text with hint ────────────────────────────────
        with dpg.collapsing_header(label="15. Input text with hint / password", default_open=True):
            dpg.add_text("dpg.add_input_text(hint=...) — placeholder text",
                         color=hex_to_rgba(palette.text_secondary))
            dpg.add_input_text(hint="Search protocols...", width=350)
            dpg.add_input_text(hint="Enter password", password=True, width=350)

        dpg.add_spacer(height=6)

        # ── 16. Tab buttons ─────────────────────────────────────────
        with dpg.collapsing_header(label="16. Tab bar with tab buttons (+)", default_open=True):
            dpg.add_text("dpg.add_tab_button() — non-tab buttons in a tab bar",
                         color=hex_to_rgba(palette.text_secondary))
            result16 = dpg.add_text("Action: (none)")
            with dpg.tab_bar():
                with dpg.tab(label="Protocol A"):
                    dpg.add_text("Content for Protocol A")
                with dpg.tab(label="Protocol B"):
                    dpg.add_text("Content for Protocol B")
                dpg.add_tab_button(label="+",
                    callback=lambda: dpg.set_value(result16, "Action: Add new"))
                dpg.add_tab_button(label="?",
                    callback=lambda: dpg.set_value(result16, "Action: Help"))

        dpg.add_spacer(height=6)

        # ── 17. Slider as selector ──────────────────────────────────
        with dpg.collapsing_header(label="17. Slider int (as index selector)", default_open=True):
            dpg.add_text("dpg.add_slider_int() — slide to pick by index",
                         color=hex_to_rgba(palette.text_secondary))
            result17 = dpg.add_text(f"Selected: {PROTOCOLS[0]}")

            def on_slider(s, a):
                idx = max(0, min(a, len(PROTOCOLS) - 1))
                dpg.set_value(result17, f"Selected: {PROTOCOLS[idx]}")

            dpg.add_slider_int(
                min_value=0, max_value=len(PROTOCOLS) - 1,
                default_value=0, width=350,
                format=f"Protocol %d / {len(PROTOCOLS) - 1}",
                callback=on_slider,
            )

    dpg.set_primary_window("demo_main", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
