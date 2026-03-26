"""
Behaviour Rig Communication Library
====================================

Serial communication interface for Arduino-based behavioural experiment rigs.

Hardware Capabilities:
    - 6 LEDs with brightness control (0-255, software PWM)
    - 6 solenoid valves with timed pulse delivery
    - 6 spotlights with hardware PWM brightness control
    - IR illuminator with PWM brightness control
    - 6 piezo buzzers with on/off control
    - Overhead I2C speaker with preset tones
    - 2 DAQ link pins (output, recorded by DAQ)
    - 4 configurable GPIO pins (input with events or output, local to ctrl board)
    - 6 infrared sensor gates with debounced detection

Example:
    import serial
    from behaviour_rig import BehaviourRigLink, GPIOMode

    with serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1) as ser:
        with BehaviourRigLink(ser) as link:
            link.send_hello()
            link.wait_hello(timeout=3.0)

            link.gpio_configure(0, GPIOMode.OUTPUT)
            link.spotlight_set(port=0, brightness=50)
            link.ir_set(brightness=255)

            link.led_set(port=0, brightness=255)
            event = link.wait_for_event(port=0, timeout=30.0)
            link.led_set(port=0, brightness=0)
            link.valve_pulse(port=0, duration_ms=500)
"""

from BehavLink.link import (
    BehaviourRigLink,
    EventType,
    GPIOEvent,
    GPIOMode,
    SensorEvent,
    SpeakerDuration,
    SpeakerFrequency,
    build_frame,
    calculate_crc16,
    reset_arduino_via_dtr,
)
from BehavLink.mock import MockSerial, mock_reset_arduino_via_dtr
from BehavLink.simulation import SimulatedRig, VirtualRigState, RigStateSnapshot

__all__ = [
    "BehaviourRigLink",
    "EventType",
    "GPIOEvent",
    "GPIOMode",
    "SensorEvent",
    "SpeakerDuration",
    "SpeakerFrequency",
    "build_frame",
    "calculate_crc16",
    "reset_arduino_via_dtr",
    # Mock serial stubs
    "MockSerial",
    "mock_reset_arduino_via_dtr",
    # Simulation
    "SimulatedRig",
    "VirtualRigState",
    "RigStateSnapshot",
]

__version__ = "0.1.0"
