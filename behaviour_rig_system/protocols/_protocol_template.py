"""
Hidden template for new class-based protocols.

Copy this file to a new filename (without leading underscore) to create a protocol.

Minimum required protocol shape:

    from core.protocol_base import BaseProtocol

    class MyProtocol(BaseProtocol):
        @classmethod
        def get_name(cls) -> str:
            return "My Protocol"

        @classmethod
        def get_description(cls) -> str:
            return "What it does"

        @classmethod
        def get_parameters(cls) -> list:
            return []

        def _run_protocol(self) -> None:
            if self._check_stop():
                return

Everything else in this template is optional quality-of-life.
"""

import time

from core.parameter_types import BoolParameter, FloatParameter, IntParameter, StringParameter
from core.protocol_base import BaseProtocol


class ProtocolTemplate(BaseProtocol):
    """Template protocol: copy, rename, then simplify as needed."""

    @classmethod
    def get_name(cls) -> str:
        """REQUIRED: display name shown in setup tabs."""
        return "Template Protocol"

    @classmethod
    def get_description(cls) -> str:
        """REQUIRED: short description shown at top of the protocol tab."""
        return "Template description. Replace with your protocol summary."

    @classmethod
    def get_parameters(cls) -> list:
        """REQUIRED: list of parameter definitions. Can be [] if none."""
        return [
            IntParameter(
                name="example_int",
                display_name="Example Integer",
                default=10,
                min_value=1,
                max_value=1000,
            ),
            FloatParameter(
                name="example_float",
                display_name="Example Float",
                default=1.0,
                min_value=0.0,
                max_value=60.0,
            ),
            BoolParameter(
                name="example_flag",
                display_name="Example Flag",
                default=True,
            ),
            StringParameter(
                name="example_text",
                display_name="Example Text",
                default="",
            ),
        ]

    def _run_protocol(self) -> None:
        """REQUIRED: main protocol body."""
        scales = self.scales
        perf_tracker = self.perf_tracker

        if perf_tracker is not None:
            perf_tracker.reset()

        self.log("Template protocol started")
        self.log(f"Parameters: {self.parameters}")

        if scales is not None:
            weight = scales.get_weight()
            if weight is not None:
                self.log(f"Current weight: {weight:.2f} g")

        for trial in range(self.parameters["example_int"]):
            if self._check_stop():
                self.log("Stopped by user")
                return

            time.sleep(0.1)

        self.log("Template protocol complete")
