"""
GUI Module for Behaviour Rig System.

This module provides the graphical user interface components:
    - Main launcher window with protocol selection
    - Dynamic parameter form builder
    - Live monitoring display
    - Protocol execution management

The GUI is built using tkinter for cross-platform compatibility and
ease of deployment (no additional dependencies required).
"""

from .main_window import MainWindow
from .parameter_widget import ParameterFormBuilder

__all__ = [
    "MainWindow",
    "ParameterFormBuilder",
]
