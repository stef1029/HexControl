"""
Core module for the Behaviour Rig System.

This module contains the foundational components:
    - Parameter type definitions for protocol configuration
    - Base protocol class that all behaviour protocols inherit from
    - Protocol loader for creating protocols from simple definitions

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
from .protocol_loader import create_protocol_class

__all__ = [
    "Parameter",
    "IntParameter",
    "FloatParameter",
    "BoolParameter",
    "ChoiceParameter",
    "BaseProtocol",
    "ProtocolStatus",
    "create_protocol_class",
]
