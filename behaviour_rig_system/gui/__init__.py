"""
GUI Module for Behaviour Rig System.

This module provides the graphical user interface components:
    - Rig launcher for selecting and connecting to rigs
    - Main control window with protocol selection
    - Dynamic parameter form builder
    - Live monitoring display
    - Protocol execution management

The GUI is built using tkinter for cross-platform compatibility and
ease of deployment (no additional dependencies required).
"""

from .launcher import RigLauncher, launch
from .main_window import MainWindow
from .parameter_widget import ParameterFormBuilder

__all__ = [
    "RigLauncher",
    "launch",
    "MainWindow",
    "ParameterFormBuilder",
]
