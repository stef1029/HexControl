#!/usr/bin/env python3
"""
Simple font demonstration GUI for Behaviour Rig System.

- Discovers available fonts using tkinter on the current machine.
- Shows fonts in a list for quick selection.
- Displays a preview of the selected font.

Run:
    python behaviour_rig_system/tests/font_demo_gui.py
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

# Ensure project-local imports work when run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PROJECT_ROOT))

from gui.theme import Theme, apply_theme


class FontDemoApp:
    """Minimal font browser and preview tool."""

    SAMPLE_TEXT = "The quick brown fox jumps over the lazy dog 0123456789"
    MONO_TEST_NARROW = "iiiiiiiiii"
    MONO_TEST_WIDE = "WWWWWWWWWW"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Font Demo")
        self.root.geometry("900x520")
        self.root.minsize(780, 420)

        apply_theme(self.root)
        self.palette = Theme.palette

        self.selected_font = tk.StringVar(value="")
        self.font_size = tk.IntVar(value=14)

        self._build_ui()
        self._populate_fonts()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=(14, 10))
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Available Fonts", style="Heading.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            main,
            text="Select a font to preview it. This shows fonts available to Tk on this machine.",
            style="Muted.TLabel",
        )
        subtitle.pack(anchor="w", pady=(0, 8))

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = ttk.Frame(content)
        right.pack(side="right", fill="both", expand=True)

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)

        self.font_list = tk.Listbox(
            list_frame,
            bg=self.palette.bg_secondary,
            fg=self.palette.text_primary,
            selectbackground=self.palette.accent_primary,
            selectforeground=self.palette.text_inverse,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.palette.border_light,
            highlightcolor=self.palette.accent_primary,
            font=Theme.font_body(),
        )
        self.font_list.pack(side="left", fill="both", expand=True)
        self.font_list.bind("<<ListboxSelect>>", self._on_font_selected)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.font_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.font_list.config(yscrollcommand=scrollbar.set)

        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=(8, 0))

        ttk.Label(controls, text="Size:", style="Muted.TLabel").pack(side="left")

        size_spin = ttk.Spinbox(
            controls,
            from_=8,
            to=48,
            width=6,
            textvariable=self.font_size,
            command=self._update_preview,
        )
        size_spin.pack(side="left", padx=(6, 10))

        refresh_btn = ttk.Button(
            controls,
            text="Refresh Fonts",
            command=self._populate_fonts,
            style="Secondary.TButton",
        )
        refresh_btn.pack(side="left")

        self.count_label = ttk.Label(controls, text="", style="Muted.TLabel")
        self.count_label.pack(side="right")

        preview_card = ttk.Frame(right, style="Card.TFrame", padding=12)
        preview_card.pack(fill="both", expand=True)

        self.preview_name = ttk.Label(preview_card, text="No font selected", style="Subheading.TLabel")
        self.preview_name.pack(anchor="w", pady=(0, 8))

        self.mono_result_label = ttk.Label(preview_card, text="Monospace: -", style="Muted.TLabel")
        self.mono_result_label.pack(anchor="w", pady=(0, 8))

        self.preview_text = tk.Text(
            preview_card,
            height=12,
            wrap="word",
            bg="#1a1d21",
            fg="#e8eaed",
            insertbackground="#e8eaed",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
        )
        self.preview_text.pack(fill="both", expand=True)
        self.preview_text.insert("1.0", self.SAMPLE_TEXT + "\n\n" + self.SAMPLE_TEXT.lower())
        self.preview_text.config(state="disabled")

    def _populate_fonts(self) -> None:
        fonts = sorted(set(tkfont.families(self.root)), key=str.casefold)

        self.font_list.delete(0, tk.END)
        for name in fonts:
            self.font_list.insert(tk.END, name)

        self.count_label.config(text=f"{len(fonts)} fonts")

        # Pick a sensible default if present.
        default_candidates = ["Segoe UI", "Arial", "Calibri", "DejaVu Sans"]
        default_name = next((f for f in default_candidates if f in fonts), fonts[0] if fonts else "")

        if default_name:
            idx = fonts.index(default_name)
            self.font_list.selection_clear(0, tk.END)
            self.font_list.selection_set(idx)
            self.font_list.see(idx)
            self.selected_font.set(default_name)
            self._update_preview()

    def _on_font_selected(self, _event: tk.Event | None = None) -> None:
        selected = self.font_list.curselection()
        if not selected:
            return

        font_name = self.font_list.get(selected[0])
        self.selected_font.set(font_name)
        self._update_preview()

    def _update_preview(self) -> None:
        font_name = self.selected_font.get().strip()
        if not font_name:
            return

        size = max(8, int(self.font_size.get()))
        self.preview_name.config(text=f"Preview: {font_name} ({size}pt)")

        is_mono, narrow_px, wide_px = self._is_monospace(font_name, size)
        mono_text = "Yes" if is_mono else "No"
        self.mono_result_label.config(
            text=f"Monospace: {mono_text}  (i={narrow_px}px, W={wide_px}px)"
        )

        self.preview_text.config(state="normal")
        self.preview_text.configure(font=(font_name, size))
        self.preview_text.config(state="disabled")

    def _is_monospace(self, font_name: str, size: int) -> tuple[bool, int, int]:
        """Return whether the font appears monospace using width measurements."""
        test_font = tkfont.Font(root=self.root, family=font_name, size=size)
        narrow_px = test_font.measure(self.MONO_TEST_NARROW)
        wide_px = test_font.measure(self.MONO_TEST_WIDE)
        return narrow_px == wide_px, narrow_px, wide_px

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    FontDemoApp().run()
