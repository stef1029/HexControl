"""
Tracker definition: the declarative structure protocols return from
``get_tracker_definitions()``.

A single dataclass that covers both the simple (single sub-tracker)
and multi-sub cases. Protocols build a list of these in their
classmethod ``get_tracker_definitions()`` and the session controller
turns each one into a runtime :class:`Tracker`.
"""

from dataclasses import dataclass


@dataclass
class TrackerDefinition:
    """
    Declarative definition of a tracker.

    A tracker covers one or more autotraining stages and contains one or
    more named sub-trackers (e.g. "visual", "audio") for different trial
    types. Simple trackers omit ``sub_trackers`` and get a single
    "default" sub created automatically.

    Attributes:
        name:         Internal key for the tracker (e.g. "interleaved_phase")
        display_name: GUI label (e.g. "Interleaved Phase")
        sub_trackers: List of sub-tracker names (e.g. ["visual", "audio"]).
                      ``None`` means create a single "default" sub-tracker.
        stages:       Set of stage names this tracker covers. When the
                      autotraining engine enters any of these stages, this
                      tracker is the active one. ``None`` means the tracker
                      name itself is the sole stage.

    Examples:

        Simple single-sub tracker::

            TrackerDefinition(name="trials", display_name="Trials")

        Multi-sub tracker covering several stages::

            TrackerDefinition(
                name="audio_phase",
                display_name="Audio Phase",
                sub_trackers=["visual", "audio"],
                stages={"audio_only", "interleaved_2_6"},
            )
    """
    name: str
    display_name: str
    sub_trackers: list[str] | None = None
    stages: set[str] | None = None

    @property
    def effective_sub_trackers(self) -> list[str]:
        """Resolve ``sub_trackers`` to a concrete list, defaulting to ``["default"]``."""
        return list(self.sub_trackers) if self.sub_trackers else ["default"]

    @property
    def effective_stages(self) -> set[str]:
        """Resolve ``stages`` to a concrete set, defaulting to ``{name}``."""
        return set(self.stages) if self.stages else {self.name}
