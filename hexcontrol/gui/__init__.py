"""
GUI Module for Behaviour Rig System.

This module provides the graphical user interface components:
    - Unified app layout with activity bar, sidebar, tabbed content, info bar
    - Rig window with mode-based navigation (setup, running, post-session)
    - Dynamic parameter form builder
    - Protocol execution management
    - Post-processing window for batch cohort processing
    - Modern theme system for consistent, professional appearance

The GUI is built using DearPyGui for GPU-accelerated rendering with
built-in plotting and theming support.
"""

from .launcher import launch
from .app_layout import AppLayout
from .rig_window import RigWindow
from .parameter_widget import ParameterFormBuilder
from .post_processing_window import PostProcessingWindow, open_post_processing_window
from .theme import apply_theme, Theme

__all__ = [
    "launch",
    "AppLayout",
    "RigWindow",
    "ParameterFormBuilder",
    "PostProcessingWindow",
    "open_post_processing_window",
    "apply_theme",
    "Theme",
]
