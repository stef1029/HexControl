"""
Simulation — Simulated mouse for automated protocol testing.

Provides a SimulatedMouse that observes VirtualRigState and injects
events (port pokes, weight changes) based on a multi-dimensional
Rescorla-Wagner learning model.
"""

from .behaviour_clock import BehaviourClock, REAL_TIME
from .simulated_mouse import SimulatedMouse
from .mouse_parameters import MOUSE_PARAMETERS

__all__ = [
    "BehaviourClock",
    "REAL_TIME",
    "SimulatedMouse",
    "MOUSE_PARAMETERS",
]
