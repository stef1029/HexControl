"""
Performance Tracker

A simple system for tracking trial outcomes (success/failure/timeout) during
behaviour protocols. Provides rolling statistics and emits events for GUI updates.

Usage in protocols:
    def run(link, params, log, check_abort, scales, tracker):
        for trial in range(num_trials):
            # ... run trial ...
            if correct:
                tracker.success()
            elif timeout:
                tracker.timeout()
            else:
                tracker.failure()
        
        # Stats are automatically displayed in the GUI
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional
from enum import Enum


class TrialOutcome(Enum):
    """Possible outcomes for a single trial."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


@dataclass
class TrialRecord:
    """Record of a single trial."""
    trial_number: int
    outcome: TrialOutcome
    timestamp: float  # Unix timestamp
    details: dict = field(default_factory=dict)  # Optional extra data


class PerformanceTracker:
    """
    Tracks trial outcomes and provides statistics.
    
    Emits events when trials are recorded so the GUI can update.
    """
    
    def __init__(self, on_update: Optional[Callable[["PerformanceTracker"], None]] = None):
        """
        Args:
            on_update: Callback called after each trial is recorded.
                       Receives the tracker instance for querying stats.
        """
        self._trials: list[TrialRecord] = []
        self._on_update = on_update
        self._start_time: Optional[float] = None
    
    def reset(self) -> None:
        """Clear all trial records."""
        self._trials.clear()
        self._start_time = datetime.now().timestamp()
        self._notify_update()
    
    # -------------------------------------------------------------------------
    # Recording Outcomes
    # -------------------------------------------------------------------------
    
    def success(self, **details) -> None:
        """Record a successful trial."""
        self._record(TrialOutcome.SUCCESS, details)
    
    def failure(self, **details) -> None:
        """Record a failed trial."""
        self._record(TrialOutcome.FAILURE, details)
    
    def timeout(self, **details) -> None:
        """Record a timeout trial."""
        self._record(TrialOutcome.TIMEOUT, details)
    
    def _record(self, outcome: TrialOutcome, details: dict) -> None:
        """Record a trial with the given outcome."""
        trial_number = len(self._trials) + 1
        record = TrialRecord(
            trial_number=trial_number,
            outcome=outcome,
            timestamp=datetime.now().timestamp(),
            details=details,
        )
        self._trials.append(record)
        self._notify_update()
    
    def _notify_update(self) -> None:
        """Notify listener of update."""
        if self._on_update:
            try:
                self._on_update(self)
            except Exception:
                pass  # Don't let GUI errors crash the protocol
    
    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------
    
    @property
    def total_trials(self) -> int:
        """Total number of trials recorded."""
        return len(self._trials)
    
    @property
    def successes(self) -> int:
        """Number of successful trials."""
        return sum(1 for t in self._trials if t.outcome == TrialOutcome.SUCCESS)
    
    @property
    def failures(self) -> int:
        """Number of failed trials."""
        return sum(1 for t in self._trials if t.outcome == TrialOutcome.FAILURE)
    
    @property
    def timeouts(self) -> int:
        """Number of timeout trials."""
        return sum(1 for t in self._trials if t.outcome == TrialOutcome.TIMEOUT)
    
    @property
    def responses(self) -> int:
        """Number of trials with a response (success + failure, excluding timeouts)."""
        return self.successes + self.failures
    
    @property
    def accuracy(self) -> float:
        """
        Overall accuracy as a percentage (0-100).
        
        Calculated as successes / (successes + failures).
        Timeouts are excluded from the calculation.
        Returns 0.0 if no responses yet.
        """
        responses = self.responses
        if responses == 0:
            return 0.0
        return (self.successes / responses) * 100
    
    def rolling_accuracy(self, n: int = 20) -> float:
        """
        Accuracy over the last N trials (excluding timeouts).
        
        Args:
            n: Number of recent trials to consider.
            
        Returns:
            Accuracy as a percentage (0-100), or 0.0 if no responses.
        """
        # Get last n trials that had a response (not timeout)
        recent = [t for t in self._trials if t.outcome != TrialOutcome.TIMEOUT][-n:]
        if not recent:
            return 0.0
        
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100
    
    def rolling_stats(self, n: int = 20) -> dict:
        """
        Get detailed stats for the last N trials.
        
        Args:
            n: Number of recent trials to consider.
            
        Returns:
            Dict with successes, failures, timeouts, total, accuracy for last N.
        """
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
    
    def get_summary(self) -> str:
        """Get a one-line summary string."""
        if self.total_trials == 0:
            return "No trials yet"
        
        return (
            f"{self.successes}/{self.responses} correct ({self.accuracy:.0f}%) | "
            f"{self.timeouts} timeouts | "
            f"Last 20: {self.rolling_accuracy(20):.0f}%"
        )
    
    def get_trials(self) -> list[TrialRecord]:
        """Get all trial records."""
        return list(self._trials)
