"""
Standalone DAQ View launcher — runs in its own process.

Launched by RunningMode._toggle_daq_view() so that each DAQ viewer has
its own DearPyGui context and does not compete with the main GUI.

Usage:
    python -m gui.daq_view_subprocess <rig_number>
"""
from __future__ import annotations

import sys

import dearpygui.dearpygui as dpg

from hexcontrol.gui.theme import Theme, apply_theme
from hexcontrol.gui.daq_view_widget import DAQViewWidget


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m gui.daq_view_subprocess <rig_number>")
        sys.exit(1)

    rig_number = int(sys.argv[1])

    dpg.create_context()
    dpg.create_viewport(title=f"DAQ Live View -- Rig {rig_number}", width=1100, height=800)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    apply_theme()

    with dpg.window(tag="daq_main", no_title_bar=True):
        widget = DAQViewWidget("daq_main")
        widget.start(rig_number)

    dpg.set_primary_window("daq_main", True)

    # Manual render loop to drive frame_poller
    from hexcontrol.gui.dpg_app import frame_poller
    while dpg.is_dearpygui_running():
        frame_poller.tick()
        dpg.render_dearpygui_frame()

    widget.stop()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
