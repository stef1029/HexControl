"""
Trial outcome enum, lifecycle state enum, and trial record dataclass.

These are the small data types that the rest of the tracker package
builds on. They have no dependencies on other tracker modules so they
can sit at the bottom of the dependency graph.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TrialOutcome(Enum):
    """Possible outcomes for a single trial."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


class TrialState(Enum):
    """Lifecycle state of the trial currently in progress on a Tracker."""
    IDLE = "idle"
    IN_PROGRESS = "in_progress"


@dataclass
class TrialRecord:
    """Immutable record of a single completed trial.

    Created by the tracker when an outcome is recorded. The ``stimuli``
    list captures any stimulus events that fired between ``begin_trial``
    and the outcome call, in the order they occurred.

    Attributes:
        trial_number:     1-indexed sequence number within the sub-tracker
        outcome:          SUCCESS / FAILURE / TIMEOUT
        timestamp:        Unix time at the moment the outcome was recorded
        time_since_start: Seconds elapsed since the tracker session start
        correct_port:     The correct port for this trial (set at begin_trial)
        chosen_port:      The port the mouse chose (None on timeout)
        trial_duration:   Auto-computed: outcome_time - begin_trial_time
        trial_type:       Sub-tracker name (e.g. "visual", "audio", "default")
        stimuli:          Stimulus events that fired during this trial
        details:          Arbitrary additional metadata from the protocol
    """
    trial_number: int
    outcome: TrialOutcome
    timestamp: float
    time_since_start: float
    correct_port: Optional[int] = None
    chosen_port: Optional[int] = None
    trial_duration: float = 0.0
    trial_type: str = ""
    stimuli: list[dict] = field(default_factory=list)
    details: dict = field(default_factory=dict)
