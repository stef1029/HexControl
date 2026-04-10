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

    Defines *what* to track, not *when* to use it. The mapping from
    autotraining stages to trackers is written by the protocol author
    in their protocol code — it is not part of the tracker definition.

    Simple trackers omit ``sub_trackers`` and get a single ``"default"``
    sub created automatically. Multi-sub trackers list named sub-types
    (e.g. ``["visual", "audio"]``) so trials can be categorised by
    modality.

    Attributes:
        name:         Internal key for the tracker (e.g. "audio_phase")
        display_name: GUI label (e.g. "Audio Phase")
        sub_trackers: List of sub-tracker names (e.g. ["visual", "audio"]).
                      ``None`` means create a single "default" sub-tracker.

    Examples:

        Simple single-sub tracker::

            TrackerDefinition(name="trials", display_name="Trials")

        Multi-sub tracker::

            TrackerDefinition(
                name="audio_phase",
                display_name="Audio Phase",
                sub_trackers=["visual", "audio"],
            )
    """
    name: str
    display_name: str
    sub_trackers: list[str] | None = None

    @property
    def effective_sub_trackers(self) -> list[str]:
        """Resolve ``sub_trackers`` to a concrete list, defaulting to ``["default"]``."""
        return list(self.sub_trackers) if self.sub_trackers else ["default"]
