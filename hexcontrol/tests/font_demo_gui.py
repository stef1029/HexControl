#!/usr/bin/env python3
"""
Font demonstration GUI for Behaviour Rig System (DearPyGui).

Shows all bundled fonts at every registered size, with sample text
rendered in each variant. Useful for verifying fonts load correctly
and checking what's available.

Run:
    python hexcontrol/tests/font_demo_gui.py
"""

from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

# Ensure hexcontrol package is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hexcontrol.gui.theme import (
    Theme, apply_theme, hex_to_rgba, _FONTS_DIR, _FONT_FILES, _resolve_font,
)


SAMPLE = "The quick brown fox jumps over the lazy dog 0123456789"
MONO_SAMPLE = "iiiiii || WWWWWW  (should be same width if monospace)"


def main() -> None:
    dpg.create_context()
    dpg.create_viewport(title="Font Demo", width=1000, height=700)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    # Apply theme (loads fonts)
    apply_theme()

    palette = Theme.palette

    with dpg.window(tag="font_demo", no_title_bar=True):

        # --- Header ---
        t = dpg.add_text("Font Demo", color=hex_to_rgba(palette.text_primary))
        if Theme.font_title():
            dpg.bind_item_font(t, Theme.font_title())

        dpg.add_text(
            f"Bundled font directory: {_FONTS_DIR}",
            color=hex_to_rgba(palette.text_secondary),
        )
        dpg.add_text(
            f"Active palette: font_family='{palette.font_family}', "
            f"font_family_mono='{palette.font_family_mono}', "
            f"font_special='{palette.font_special}'",
            color=hex_to_rgba(palette.text_secondary),
        )

        dpg.add_separator()
        dpg.add_spacer(height=8)

        # --- Bundled font files ---
        dpg.add_text("Bundled Font Files:", color=hex_to_rgba(palette.accent_primary))
        for family, (regular, bold) in _FONT_FILES.items():
            reg_path = _FONTS_DIR / regular
            bold_path = _FONTS_DIR / bold
            reg_exists = reg_path.exists()
            bold_exists = bold_path.exists()
            status_r = "OK" if reg_exists else "MISSING"
            status_b = "OK" if bold_exists else "MISSING"
            dpg.add_text(
                f"  {family}: regular={regular} [{status_r}], bold={bold} [{status_b}]",
                color=hex_to_rgba(palette.success if reg_exists else palette.error),
            )

        dpg.add_separator()
        dpg.add_spacer(height=8)

        # --- Resolved font paths ---
        dpg.add_text("Resolved Paths:", color=hex_to_rgba(palette.accent_primary))
        for label, path in [
            ("Body (regular)", _resolve_font(palette.font_family)),
            ("Body (bold)", _resolve_font(palette.font_family, bold=True)),
            ("Mono (regular)", _resolve_font(palette.font_family_mono)),
            ("Special", _resolve_font(palette.font_special)),
        ]:
            status = path or "NOT FOUND"
            color = palette.text_primary if path else palette.error
            dpg.add_text(f"  {label}: {status}", color=hex_to_rgba(color))

        dpg.add_separator()
        dpg.add_spacer(height=8)

        # --- Font previews ---
        dpg.add_text("Font Previews:", color=hex_to_rgba(palette.accent_primary))
        dpg.add_spacer(height=4)

        font_entries = [
            ("Default (body)", Theme.font_body()),
            ("Small", Theme.font_small()),
            ("Heading", Theme.font_heading()),
            ("Title", Theme.font_title()),
            ("Mono", Theme.font_mono()),
            ("Special", Theme.font_special()),
        ]

        for label, font_id in font_entries:
            with dpg.group():
                header = dpg.add_text(
                    f"--- {label} (font_id={font_id}) ---",
                    color=hex_to_rgba(palette.text_secondary),
                )

                sample = dpg.add_text(SAMPLE)
                if font_id is not None:
                    dpg.bind_item_font(sample, font_id)

                if "mono" in label.lower():
                    mono = dpg.add_text(MONO_SAMPLE)
                    if font_id is not None:
                        dpg.bind_item_font(mono, font_id)

                dpg.add_spacer(height=6)

        dpg.add_separator()
        dpg.add_spacer(height=8)

        # --- Side-by-side comparison ---
        dpg.add_text("Side-by-Side Comparison:", color=hex_to_rgba(palette.accent_primary))
        with dpg.table(header_row=True, borders_innerV=True, borders_outerV=True,
                       borders_innerH=True, borders_outerH=True):
            dpg.add_table_column(label="Font")
            dpg.add_table_column(label="Sample Text")
            dpg.add_table_column(label="Numbers")

            for label, font_id in font_entries:
                with dpg.table_row():
                    dpg.add_text(label)
                    t1 = dpg.add_text("AaBbCcDdEeFf GgHhIiJjKk")
                    if font_id:
                        dpg.bind_item_font(t1, font_id)
                    t2 = dpg.add_text("0123456789 +-=.,;:")
                    if font_id:
                        dpg.bind_item_font(t2, font_id)

    dpg.set_primary_window("font_demo", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
