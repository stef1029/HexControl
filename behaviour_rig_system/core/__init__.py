"""
Core module for the Behaviour Rig System.

This module contains the foundational components:
    - Parameter type definitions for protocol configuration
    - Base protocol class that all behaviour protocols inherit from
    - Hardware abstraction layer for rig communication
    - Session management utilities

Note: BehavLink types (GPIOMode, SpeakerFrequency, SpeakerDuration) should
be imported directly from BehavLink, not from this module.
"""

from .parameter_types import (
    Parameter,
    IntParameter,
    FloatParameter,
    BoolParameter,
    ChoiceParameter,
)
from .protocol_base import BaseProtocol, ProtocolStatus
from .hardware import HardwareInterface

__all__ = [
    "Parameter",
    "IntParameter",
    "FloatParameter",
    "BoolParameter",
    "ChoiceParameter",
    "BaseProtocol",
    "ProtocolStatus",
    "HardwareInterface",
]
