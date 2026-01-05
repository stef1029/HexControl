"""
Behaviour Protocols Module.

This module contains all available behaviour protocols that can be run on
the behaviour rig. Each protocol is a class that inherits from BaseProtocol
and implements the required methods.

Available Protocols:
    - HardwareTestProtocol: Tests all hardware components on the rig.

To add a new protocol:
    1. Create a new Python file in this directory
    2. Define a class that inherits from BaseProtocol
    3. Implement the required abstract methods
    4. Import and add to __all__ in this file
"""

from .hardware_test import HardwareTestProtocol

__all__ = [
    "HardwareTestProtocol",
]


def get_available_protocols() -> list[type]:
    """
    Return a list of all available protocol classes.

    This function is used by the GUI to populate the protocol selector.
    Protocols are returned in the order they should appear in the GUI.

    Returns:
        List of protocol classes (not instances).
    """
    return [
        HardwareTestProtocol,
    ]
