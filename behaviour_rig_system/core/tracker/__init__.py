"""
Tracker — record and manage trial outcomes during behaviour protocols.
==========================================================================

A small package that handles trial-outcome tracking for behaviour
protocols. The runtime :class:`Tracker` is built from a declarative
:class:`TrackerDefinition` and enforces a mandatory trial lifecycle via
the :class:`Trial` context manager. Stimulus events captured during
each trial are persisted alongside the outcome in the trials CSV.

Public API:
    Tracker             — runtime tracker, one per TrackerDefinition
    TrackerDefinition   — declarative definition consumed by protocols
    Trial               — context manager for the trial lifecycle
    TrialState          — IDLE / IN_PROGRESS lifecycle enum
    TrialOutcome        — SUCCESS / FAILURE / TIMEOUT enum
    TrialRecord         — immutable record of one completed trial
    save_merged_trials  — write trials from multiple trackers to a CSV
    TrackerLifecycleError — raised on outcome calls without an active trial

Example:
    from core.tracker import Tracker, Trial, TrackerDefinition

    defn = TrackerDefinition(name="trials", display_name="Trials")
    tracker = Tracker(defn)
    tracker.reset()  # set session start time

    for i in range(num_trials):
        target = pick_target()
        with Trial(tracker, correct_port=target) as t:
            t.stimulus(port=target, modality="visual")
            present_cue(target)
            response = wait_for_response()
            if response is None:
                t.timeout()
            elif response == target:
                t.success()
            else:
                t.failure(chosen_port=response)
"""

from ._definition import TrackerDefinition
from ._lifecycle import Trial
from ._outcomes import TrialOutcome, TrialRecord, TrialState
from ._persistence import save_merged_trials
from ._tracker import Tracker, TrackerLifecycleError

__all__ = [
    # Core types
    "Tracker",
    "TrackerDefinition",
    # Trial lifecycle
    "Trial",
    "TrialState",
    "TrackerLifecycleError",
    # Outcomes
    "TrialOutcome",
    "TrialRecord",
    # Persistence
    "save_merged_trials",
]
