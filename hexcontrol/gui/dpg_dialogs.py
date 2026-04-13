"""
DearPyGui dialog utilities.

Provides modal message boxes:
    show_info, show_warning, show_error, ask_yes_no
"""

from __future__ import annotations

from typing import Callable, Optional

import dearpygui.dearpygui as dpg

from .theme import Theme, hex_to_rgba


def _close_dialog(dialog_id: int | str) -> None:
    if dpg.does_item_exist(dialog_id):
        dpg.delete_item(dialog_id)


def _center_pos(w: int, h: int) -> list[int]:
    """Compute a centered position for a dialog of size w x h."""
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    return [max(0, (vw - w) // 2), max(0, (vh - h) // 2)]


def show_info(title: str, message: str) -> None:
    _show_message(title, message, "info")


def show_warning(title: str, message: str) -> None:
    _show_message(title, message, "warning")


def show_error(title: str, message: str) -> None:
    _show_message(title, message, "error")


def _show_message(title: str, message: str, level: str = "info") -> None:
    palette = Theme.palette
    color_map = {
        "info": palette.info,
        "warning": palette.warning,
        "error": palette.error,
    }
    color = hex_to_rgba(color_map.get(level, palette.text_primary))
    w, h = 420, 180

    with dpg.window(
        label=title, modal=True, no_resize=True, no_collapse=True,
        width=w, height=h, pos=_center_pos(w, h),
    ) as win:
        dpg.add_spacer(height=8)
        dpg.add_text(message, wrap=380, color=color)
        dpg.add_spacer(height=12)
        dpg.add_button(label="OK", width=80, callback=lambda: _close_dialog(win))


def ask_yes_no(
    title: str,
    message: str,
    on_yes: Callable[[], None],
    on_no: Optional[Callable[[], None]] = None,
) -> None:
    """Show a yes/no confirmation dialog."""
    palette = Theme.palette
    w, h = 440, 200

    with dpg.window(
        label=title, modal=True, no_resize=True, no_collapse=True,
        width=w, height=h, pos=_center_pos(w, h),
    ) as win:
        dpg.add_spacer(height=8)
        dpg.add_text(message, wrap=400, color=hex_to_rgba(palette.warning))
        dpg.add_spacer(height=12)
        with dpg.group(horizontal=True):
            def _yes():
                _close_dialog(win)
                on_yes()

            def _no():
                _close_dialog(win)
                if on_no:
                    on_no()

            dpg.add_button(label="Yes", width=80, callback=lambda: _yes())
            dpg.add_button(label="No", width=80, callback=lambda: _no())
