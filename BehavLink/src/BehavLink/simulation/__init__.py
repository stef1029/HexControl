"""
BehavLink simulation package.

Provides the interactive virtual rig system:
    - VirtualRigState / RigStateSnapshot — thread-safe hardware state model
    - SimulatedRig — drop-in replacement for BehaviourRigLink backed by state
"""

from .rig_state import RigStateSnapshot, VirtualRigState
from .simulated_rig import SimulatedRig

__all__ = [
    "RigStateSnapshot",
    "SimulatedRig",
    "VirtualRigState",
]
