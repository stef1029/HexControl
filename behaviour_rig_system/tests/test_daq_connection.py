"""
Test script for DAQ connection.

This script tests the DAQ serial listener independently of the GUI.
It uses the DAQLink library to start the DAQ subprocess, wait for the
Arduino connection, run briefly, and shut down cleanly.

All configuration (DAQ board name, COM port resolution) is loaded
automatically from rigs.yaml and the board registry.

Usage:
    Edit the configuration section below, then run:
        python tests/test_daq_connection.py
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ===========================================================================
# CONFIGURATION — edit these values for your setup
# ===========================================================================
RIG_NUMBER = 1                                        # Which rig to test (1-based)
CONFIG_PATH = Path(r"C:\dev\projects\rigs.yaml")      # Path to rigs.yaml
MOUSE_ID = "test_daq"                                 # Mouse ID for the test session
CONNECTION_TIMEOUT = 30                               # Seconds to wait for connection
RUN_DURATION = 10                                     # Seconds to run after connection
# ===========================================================================

# ---------------------------------------------------------------------------
# Ensure the behaviour_rig_system root is on sys.path so we can import
# core.board_registry and the DAQLink package.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent                     # behaviour_rig_system/
_HEX_BEHAV_CONTROL = _PROJECT_DIR.parent              # hex_behav_control/
_DAQLINK_SRC = _HEX_BEHAV_CONTROL / "DAQLink" / "src" # DAQLink/src/

for _p in (_PROJECT_DIR, _DAQLINK_SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import yaml  # type: ignore
from DAQLink import DAQManager
from core.board_registry import BoardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_rig_entry(config_path: Path, rig_number: int) -> dict:
    """
    Load the rig entry for *rig_number* from *config_path* (rigs.yaml).

    Returns the rig dict (with keys like ``daq_board_name``, ``board_name``, etc.)
    Raises SystemExit if the file or rig entry is not found.
    """
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    rigs = config.get("rigs", [])
    if not rigs:
        print("ERROR: No rigs defined in config file")
        sys.exit(1)

    if rig_number < 1 or rig_number > len(rigs):
        print(f"ERROR: Rig {rig_number} not found (config has {len(rigs)} rig(s))")
        sys.exit(1)

    return rigs[rig_number - 1]


def main() -> int:
    # ------------------------------------------------------------------
    # Load rig config
    # ------------------------------------------------------------------
    rig_entry = load_rig_entry(CONFIG_PATH, RIG_NUMBER)
    daq_board_name = rig_entry.get("daq_board_name", "")

    print("=" * 60)
    print("DAQ CONNECTION TEST")
    print("=" * 60)
    print(f"  Rig number      : {RIG_NUMBER}")
    print(f"  Config file      : {CONFIG_PATH}")
    print(f"  DAQ board name   : {daq_board_name or '(none)'}")

    # Resolve the COM port via the board registry so we can display it
    if daq_board_name:
        try:
            registry = BoardRegistry()
            com_port = registry.resolve_port(daq_board_name)
            print(f"  Resolved COM port: {com_port}")
        except Exception as exc:
            print(f"  WARNING: Could not resolve board name: {exc}")
    print("-" * 60)

    # ------------------------------------------------------------------
    # Create a temporary session folder
    # ------------------------------------------------------------------
    date_time = datetime.now().strftime("%y%m%d_%H%M%S")
    output_folder = Path(f"D:/behaviour_data/test_{date_time}_{MOUSE_ID}")
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {output_folder}")

    # ------------------------------------------------------------------
    # Use DAQManager to run the DAQ subprocess
    # ------------------------------------------------------------------
    manager = DAQManager(
        mouse_id=MOUSE_ID,
        date_time=date_time,
        session_folder=str(output_folder),
        rig_number=RIG_NUMBER,
        daq_board_name=daq_board_name,
        connection_timeout=CONNECTION_TIMEOUT,
        log_callback=lambda msg: print(f"  [DAQManager] {msg}"),
    )

    print("-" * 60)
    print("Starting DAQ process...")

    if not manager.start():
        print(f"ERROR: Failed to start DAQ — {manager.last_error}")
        return 1

    print("-" * 60)
    print(f"Waiting for Arduino connection (timeout {CONNECTION_TIMEOUT}s)...")

    if not manager.wait_for_connection():
        print(f"ERROR: {manager.last_error}")
        manager.stop()
        return 1

    print("-" * 60)
    print(f"CONNECTION SUCCESSFUL — running for {RUN_DURATION}s...")

    run_start = time.time()
    while time.time() - run_start < RUN_DURATION:
        if not manager.is_running:
            print("DAQ process ended early")
            break
        time.sleep(0.5)

    # ------------------------------------------------------------------
    # Stop gracefully
    # ------------------------------------------------------------------
    print("-" * 60)
    print("Stopping DAQ...")
    manager.stop()

    # ------------------------------------------------------------------
    # Report results
    # ------------------------------------------------------------------
    print("-" * 60)
    print("TEST COMPLETE")
    print(f"Check output folder: {output_folder}")

    # List output files
    if output_folder.exists():
        print("\nOutput files:")
        for f in sorted(output_folder.iterdir()):
            if f.is_file():
                print(f"  {f.name} ({f.stat().st_size} bytes)")
            else:
                print(f"  {f.name}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
