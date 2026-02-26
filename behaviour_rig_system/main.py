#!/usr/bin/env python3
"""
Behaviour Rig System - Main Entry Point.

This script launches the Behaviour Rig System launcher, which provides
a graphical interface for selecting and connecting to multiple behaviour
rigs. Each rig can be controlled from its own window.

Usage:
    python main.py

Configuration:
    Edit config/rigs.yaml to configure available rigs and their serial ports.
"""

import sys
from pathlib import Path

# Add the project root to the Python path to allow imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


# =============================================================================
# Configuration
# =============================================================================

# Path to the rig configuration file
CONFIG_PATH = Path(r"C:\Dev\projects\rigs_config.yaml")


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> None:
    """
    Main entry point for the Behaviour Rig System.

    Launches the rig launcher window.
    """
    from gui.launcher import launch

    print("=" * 60)
    print("  Behaviour Rig System")
    print("=" * 60)
    print()
    print(f"  Config: {CONFIG_PATH}")
    print("  Launching rig selector...")
    print()

    launch(config_path=CONFIG_PATH)


if __name__ == "__main__":
    main()
