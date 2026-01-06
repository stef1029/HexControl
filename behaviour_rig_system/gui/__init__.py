"""
GUI Module for Behaviour Rig System.

This module provides the graphical user interface components:
    - Rig launcher for selecting and connecting to rigs
    - Rig window with mode-based navigation (setup, running, post-session)
    - Dynamic parameter form builder
    - Protocol execution management

The GUI is built using tkinter for cross-platform compatibility and
ease of deployment (no additional dependencies required).
"""

from .launcher import RigLauncher, launch
from .rig_window import RigWindow
from .parameter_widget import ParameterFormBuilder

__all__ = [
    "RigLauncher",
    "launch",
    "RigWindow",
    "ParameterFormBuilder",
]
