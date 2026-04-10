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
            if self.check_stop():
                return

Everything else in this template is optional quality-of-life.
"""

from core.parameter_types import BoolParameter, FloatParameter, IntParameter, StringParameter
from core.protocol_base import BaseProtocol
from core.tracker import TrackerDefinition, Trial


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

    @classmethod
    def get_tracker_definitions(cls) -> dict:
        """OPTIONAL: declare trackers keyed by the name you'll look them up by.

        For autotraining protocols, key by stage name. For simple protocols,
        key by whatever name you use in self.trackers["key"].
        """
        return {"trials": TrackerDefinition(name="trials", display_name="Trials")}

    def _run_protocol(self) -> None:
        """REQUIRED: main protocol body."""
        scales = self.scales
        tracker = self.trackers.get("trials")

        if tracker is None:
            self.log("ERROR: 'trials' tracker not available!")
            return
        tracker.reset()

        self.log("Template protocol started")
        self.log(f"Parameters: {self.parameters}")

        if scales is not None:
            weight = scales.get_weight()
            if weight is not None:
                self.log(f"Current weight: {weight:.2f} g")

        for trial_num in range(self.parameters["example_int"]):
            if self.check_stop():
                self.log("Stopped by user")
                return

            # Standard trial pattern: wrap each trial in a Trial context manager.
            # The lifecycle is enforced — every begin must be followed by an
            # outcome (success/failure/timeout) or the trial auto-abandons.
            target_port = 0
            with Trial(tracker, correct_port=target_port) as t:
                t.stimulus(port=target_port, modality="visual")
                # ... present cue, wait for response, etc. ...
                self.sleep(0.1)
                # Record one of: t.success() / t.failure(chosen_port=X) / t.timeout()
                t.success()

        self.log("Template protocol complete")
