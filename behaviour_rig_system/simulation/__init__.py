"""
Simulation — Simulated mouse for automated protocol testing.

Provides a SimulatedMouse that observes VirtualRigState and injects
events (port pokes, weight changes) based on a multi-dimensional
Rescorla-Wagner learning model.
"""

from .simulated_mouse import SimulatedMouse
from .mouse_parameters import MOUSE_PARAMETERS

__all__ = [
    "SimulatedMouse",
    "MOUSE_PARAMETERS",
]
