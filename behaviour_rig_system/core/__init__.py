"""
Core module for the Behaviour Rig System.

This module contains the foundational components:
    - Parameter type definitions for protocol configuration
    - Base protocol class that all behaviour protocols inherit from

For hardware control, use BehavLink directly in your protocols:
    from BehavLink import BehaviourRigLink, GPIOMode, SpeakerFrequency, SpeakerDuration
"""

from .parameter_types import (
    Parameter,
    IntParameter,
    FloatParameter,
    BoolParameter,
    ChoiceParameter,
)
from .protocol_base import BaseProtocol, ProtocolStatus

__all__ = [
    "Parameter",
    "IntParameter",
    "FloatParameter",
    "BoolParameter",
    "ChoiceParameter",
    "BaseProtocol",
    "ProtocolStatus",
]
