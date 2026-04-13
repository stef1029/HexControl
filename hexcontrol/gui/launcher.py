"""
Rig Launcher — entry point for the Behaviour Rig System GUI.

Creates the DPG application and the unified AppLayout, then runs the
render loop. All layout and business logic lives in AppLayout.
"""

from __future__ import annotations

from pathlib import Path

from . import dpg_app
from .app_layout import AppLayout


def launch(config_path: Path, board_registry_path: Path) -> None:
    """Launch the rig control system GUI."""
    dpg_app.create_app("Behaviour Rig System", 1280, 800)
    app = AppLayout(config_path, board_registry_path)
    dpg_app.run()
    app.cleanup()
    dpg_app.shutdown()
