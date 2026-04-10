"""
Internal sub-tracker — owns the per-modality trial list and stats.

Not part of the public API. Consumers interact with the parent
:class:`Tracker` instance, which delegates to the appropriate
``_SubTracker`` based on the ``sub`` argument. The leading underscore
on the class name signals "internal — touch at your own risk."

Each sub-tracker holds:
- An ordered list of TrialRecord objects
- Cached running counters (successes / failures / timeouts) for O(1)
  stats lookups instead of repeatedly scanning the list
"""

from typing import Optional

from ._outcomes import TrialOutcome, TrialRecord


class _SubTracker:
    """Per-sub-tracker storage and statistics. Not part of the public API."""

    def __init__(self, name: str):
        self._name = name
        self._trials: list[TrialRecord] = []

        # Cached running counters — O(1) instead of O(n) list scans
        self._successes: int = 0
        self._failures: int = 0
        self._timeouts: int = 0

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all trial records and counters."""
        self._trials.clear()
        self._successes = 0
        self._failures = 0
        self._timeouts = 0

    def append(self, record: TrialRecord) -> None:
        """
        Append a fully-constructed TrialRecord and update counters.

        Called by the parent Tracker once it has computed the timing
        and stimulus list for the trial. The trial_number on ``record``
        should already be set to ``len(self._trials) + 1``.
        """
        self._trials.append(record)
        if record.outcome == TrialOutcome.SUCCESS:
            self._successes += 1
        elif record.outcome == TrialOutcome.FAILURE:
            self._failures += 1
        elif record.outcome == TrialOutcome.TIMEOUT:
            self._timeouts += 1

    # ------------------------------------------------------------------
    # Properties (used to build TrialRecord and compute stats)
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def total_trials(self) -> int:
        return len(self._trials)

    @property
    def successes(self) -> int:
        return self._successes

    @property
    def failures(self) -> int:
        return self._failures

    @property
    def timeouts(self) -> int:
        return self._timeouts

    @property
    def responses(self) -> int:
        return self._successes + self._failures

    @property
    def accuracy(self) -> float:
        """Percentage of responses (excluding timeouts) that were successful."""
        responses = self.responses
        if responses == 0:
            return 0.0
        return (self._successes / responses) * 100

    # ------------------------------------------------------------------
    # Trial access
    # ------------------------------------------------------------------

    def get_trials(self) -> list[TrialRecord]:
        """Return a shallow copy of all trial records."""
        return list(self._trials)

    def get_trials_since(self, index: int) -> list[TrialRecord]:
        """Return trials from ``index`` onwards (no copy)."""
        return self._trials[index:]

    def first_timestamp(self) -> Optional[float]:
        """Timestamp of the first recorded trial, or None."""
        return self._trials[0].timestamp if self._trials else None

    def last_timestamp(self) -> Optional[float]:
        """Timestamp of the most recent trial, or None."""
        return self._trials[-1].timestamp if self._trials else None

    # ------------------------------------------------------------------
    # Rolling statistics
    # ------------------------------------------------------------------

    def rolling_accuracy(self, n: int = 20) -> float:
        """
        Accuracy over the last ``n`` non-timeout trials.

        Returns 0.0 if there are no responses yet.
        """
        recent = [t for t in self._trials if t.outcome != TrialOutcome.TIMEOUT][-n:]
        if not recent:
            return 0.0
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def rolling_stats(self, n: int = 20) -> dict:
        """Get detailed stats for the last ``n`` trials."""
        recent = self._trials[-n:] if self._trials else []
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        failures = sum(1 for t in recent if t.outcome == TrialOutcome.FAILURE)
        timeouts = sum(1 for t in recent if t.outcome == TrialOutcome.TIMEOUT)
        responses = successes + failures
        return {
            "successes": successes,
            "failures": failures,
            "timeouts": timeouts,
            "total": len(recent),
            "responses": responses,
            "accuracy": (successes / responses * 100) if responses > 0 else 0.0,
        }
