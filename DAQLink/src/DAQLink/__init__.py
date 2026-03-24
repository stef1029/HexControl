"""
DAQLink - Arduino DAQ data acquisition for behavioural experiment rigs.

This module provides serial communication with Arduino Mega-based DAQ systems
for recording rig state during behavioural experiments.
"""

from .serial_listen import listen, main
from .manager import DAQManager

__all__ = [
    "listen",
    "main",
    "DAQManager",
]
