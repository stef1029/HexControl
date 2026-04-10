"""
Solenoid Test Protocol

Activates a solenoid valve on a chosen port a set number of times with a delay between pulses.
"""

import time

from hexcontrol.core.parameter_types import FloatParameter, IntParameter
from hexcontrol.core.protocol_base import BaseProtocol


class SolenoidTestProtocol(BaseProtocol):
    """Fires a solenoid valve repeatedly on a single port for testing."""

    @classmethod
    def get_name(cls) -> str:
        return "Solenoid Test"

    @classmethod
    def get_description(cls) -> str:
        return "Activates a solenoid valve on a chosen port a number of times with a delay between each pulse."

    @classmethod
    def get_parameters(cls) -> list:
        return [
            IntParameter(
                name="port",
                display_name="Solenoid Port",
                default=0,
                min_value=0,
                max_value=5,
            ),
            IntParameter(
                name="num_pulses",
                display_name="Number of Pulses",
                default=5,
                min_value=1,
                max_value=100,
            ),
            IntParameter(
                name="pulse_duration_ms",
                display_name="Pulse Duration (ms)",
                default=100,
                min_value=10,
                max_value=2000,
            ),
            FloatParameter(
                name="delay_between_s",
                display_name="Delay Between Pulses (s)",
                default=1.0,
                min_value=0.1,
                max_value=10.0,
            ),
        ]

    def _run_protocol(self) -> None:
        port = self.parameters["port"]
        num_pulses = self.parameters["num_pulses"]
        pulse_ms = self.parameters["pulse_duration_ms"]
        delay_s = self.parameters["delay_between_s"]

        self.log(f"Solenoid test: port {port}, {num_pulses} pulses, "
                 f"{pulse_ms} ms each, {delay_s} s delay")

        for i in range(1, num_pulses + 1):
            if self.check_stop():
                return
            self.log(f"  Pulse {i}/{num_pulses}")
            self.link.valve_pulse(port, pulse_ms)
            if i < num_pulses:
                time.sleep(delay_s)

        self.log("Solenoid test complete.")
