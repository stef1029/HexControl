#!/usr/bin/env python3
"""
Behaviour Rig System - Main Entry Point.

This script launches the Behaviour Rig System GUI, which provides a
graphical interface for configuring and running behaviour protocols
on the behaviour rig hardware.

Usage:
    python main.py

The application will start in simulation mode by default if no hardware
is detected. You can configure the serial port and toggle simulation
mode from within the GUI.

Configuration:
    Modify the variables below to change default settings:
        - SERIAL_PORT: Default serial port for hardware connection
        - BAUD_RATE: Serial communication baud rate
        - SIMULATION_MODE: Whether to start in simulation mode

For command-line usage, you can also run protocols directly without
the GUI by importing from the protocols module.
"""

import sys
from pathlib import Path

# Add the project root to the Python path to allow imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


# =============================================================================
# Configuration
# =============================================================================

# Default serial port for hardware connection
# Change to match your system (e.g., "/dev/ttyUSB0" on Linux)
SERIAL_PORT = "COM7"

# Serial communication baud rate (should match Arduino firmware)
BAUD_RATE = 115200

# Whether to start in simulation mode (no hardware required)
# Set to True for testing without connected hardware
# Set to False to communicate with the actual rig
SIMULATION_MODE = False


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> None:
    """
    Main entry point for the Behaviour Rig System.

    Launches the GUI with the configured default settings.
    """
    from gui.main_window import launch_gui

    print("=" * 60)
    print("  Behaviour Rig System")
    print("=" * 60)
    print()
    print(f"  Serial Port: {SERIAL_PORT}")
    print(f"  Baud Rate: {BAUD_RATE}")
    print(f"  Simulation Mode: {SIMULATION_MODE}")
    print()
    print("  Launching GUI...")
    print()

    launch_gui(
        serial_port=SERIAL_PORT,
        baud_rate=BAUD_RATE,
        simulation_mode=SIMULATION_MODE,
    )


if __name__ == "__main__":
    main()
