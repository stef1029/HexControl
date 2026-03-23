"""
Hidden template for new class-based protocols.

Copy this file to a new filename (without leading underscore) to create a protocol.
"""

import time

from core.parameter_types import BoolParameter, FloatParameter, IntParameter, StringParameter
from core.protocol_base import BaseProtocol, ProtocolEvent


class ProtocolTemplate(BaseProtocol):
    """Template protocol: copy and rename this class for a new protocol."""

    _scales_client = None
    _perf_tracker = None

    @classmethod
    def get_name(cls) -> str:
        return "Template Protocol"

    @classmethod
    def get_description(cls) -> str:
        return "Template description. Replace with your protocol summary."

    @classmethod
    def get_parameters(cls) -> list:
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

    def _cleanup(self) -> None:
        if self.link:
            try:
                self.link.shutdown()
            except Exception:
                pass

    def _on_abort(self) -> None:
        if self.link:
            try:
                self.link.shutdown()
            except Exception:
                pass

    def _log(self, message: str) -> None:
        self._emit_event(ProtocolEvent("status_update", data={"message": message}))

    def _run_protocol(self) -> None:
        scales = getattr(self, "_scales_client", None)
        perf_tracker = getattr(self, "_perf_tracker", None)

        if perf_tracker is not None:
            perf_tracker.reset()

        self._log("Template protocol started")
        self._log(f"Parameters: {self.parameters}")

        if scales is not None:
            weight = scales.get_weight()
            if weight is not None:
                self._log(f"Current weight: {weight:.2f} g")

        for trial in range(self.parameters["example_int"]):
            if self._check_abort():
                self._log("Aborted by user")
                return

            time.sleep(0.1)

        self._log("Template protocol complete")
