"""
Performance Tracker

A simple system for tracking trial outcomes (success/failure/timeout) during
behaviour protocols. Provides rolling statistics and emits events for GUI updates.

Usage in protocols:
    def run(link, params, log, check_stop, scales, tracker):
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

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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
    time_since_start: float  # Seconds since session start
    correct_port: Optional[int] = None  # The correct port for this trial
    chosen_port: Optional[int] = None  # The port the mouse chose (None if timeout)
    trial_duration: float = 0.0  # Duration of the trial in seconds
    details: dict = field(default_factory=dict)  # Optional extra data


class PerformanceTracker:
    """
    Tracks trial outcomes and provides statistics.
    
    Emits events when trials are recorded so the GUI can update.
    """
    
    def __init__(self):
        self._trials: list[TrialRecord] = []
        self._listeners: dict[str, list[Callable]] = {}
        self._start_time: Optional[float] = None

        # Cached running counters — O(1) instead of O(n) list scans
        self._successes: int = 0
        self._failures: int = 0
        self._timeouts: int = 0

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a callback for a named event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def _emit(self, event_name: str, **kwargs) -> None:
        """Fire an event to registered listeners."""
        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception:
                pass  # Don't let GUI errors crash the protocol
    
    def reset(self) -> None:
        """Clear all trial records."""
        self._trials.clear()
        self._successes = 0
        self._failures = 0
        self._timeouts = 0
        self._start_time = datetime.now().timestamp()
        self._notify_update()
    
    def stimulus(self, target_port: int) -> None:
        """
        Signal that a stimulus has been presented.

        This is for display purposes only and is not saved to the trials log.

        Args:
            target_port: The port that is the correct response for this trial.
        """
        self._emit("stimulus", port=target_port)
    
    # -------------------------------------------------------------------------
    # Recording Outcomes
    # -------------------------------------------------------------------------
    
    def success(
        self,
        correct_port: int,
        trial_duration: float = 0.0,
        **details
    ) -> None:
        """
        Record a successful trial.
        
        Args:
            correct_port: The correct port number (which the mouse chose)
            trial_duration: How long the trial lasted in seconds
            **details: Any additional data to store
        """
        # On success, chosen_port equals correct_port
        self._record(TrialOutcome.SUCCESS, correct_port, correct_port, trial_duration, details)
    
    def failure(
        self,
        correct_port: int,
        chosen_port: int,
        trial_duration: float = 0.0,
        **details
    ) -> None:
        """
        Record a failed trial.
        
        Args:
            correct_port: The correct port number
            chosen_port: The port the mouse actually chose
            trial_duration: How long the trial lasted in seconds
            **details: Any additional data to store
        """
        self._record(TrialOutcome.FAILURE, correct_port, chosen_port, trial_duration, details)
    
    def timeout(
        self,
        correct_port: int,
        trial_duration: float = 0.0,
        **details
    ) -> None:
        """
        Record a timeout trial.
        
        Args:
            correct_port: The correct port number (mouse didn't choose)
            trial_duration: How long the trial lasted in seconds
            **details: Any additional data to store
        """
        self._record(TrialOutcome.TIMEOUT, correct_port, None, trial_duration, details)
    
    def _record(
        self,
        outcome: TrialOutcome,
        correct_port: Optional[int],
        chosen_port: Optional[int],
        trial_duration: float,
        details: dict
    ) -> None:
        """Record a trial with the given outcome."""
        trial_number = len(self._trials) + 1
        current_time = datetime.now().timestamp()
        time_since_start = current_time - self._start_time if self._start_time else 0.0
        
        record = TrialRecord(
            trial_number=trial_number,
            outcome=outcome,
            timestamp=current_time,
            time_since_start=time_since_start,
            correct_port=correct_port,
            chosen_port=chosen_port,
            trial_duration=trial_duration,
            details=details,
        )
        self._trials.append(record)
        
        # Update cached counters
        if outcome == TrialOutcome.SUCCESS:
            self._successes += 1
        elif outcome == TrialOutcome.FAILURE:
            self._failures += 1
        elif outcome == TrialOutcome.TIMEOUT:
            self._timeouts += 1
        
        self._notify_update()
    
    def _notify_update(self) -> None:
        """Notify listener of update."""
        self._emit("update", tracker=self)
    
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
        return self._successes
    
    @property
    def failures(self) -> int:
        """Number of failed trials."""
        return self._failures
    
    @property
    def timeouts(self) -> int:
        """Number of timeout trials."""
        return self._timeouts
    
    @property
    def responses(self) -> int:
        """Number of trials with a response (success + failure, excluding timeouts)."""
        return self._successes + self._failures
    
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
    
    def get_trials_since(self, index: int) -> list[TrialRecord]:
        """Get trial records from the given index onwards (avoids copying entire list)."""
        return self._trials[index:]
    
    def get_report(self) -> dict:
        """
        Get a detailed performance report for the session.
        
        Returns:
            Dict containing comprehensive session statistics:
                - total_trials: Total number of trials
                - successes: Number of successful trials
                - failures: Number of failed trials
                - timeouts: Number of timeout trials
                - responses: Trials with responses (successes + failures)
                - accuracy: Success rate excluding timeouts (successes / responses)
                - accuracy_with_timeouts: Success rate including timeouts (successes / total)
                - timeout_rate: Percentage of trials that were timeouts
                - rolling_accuracy_10: Accuracy over last 10 trials
                - rolling_accuracy_20: Accuracy over last 20 trials
                - session_duration: Duration in seconds (if start time was set)
                - trials_per_minute: Average trial rate
        """
        # Calculate accuracy including timeouts in denominator
        accuracy_with_timeouts = (self.successes / self.total_trials * 100) if self.total_trials > 0 else 0.0
        
        report = {
            "total_trials": self.total_trials,
            "successes": self.successes,
            "failures": self.failures,
            "timeouts": self.timeouts,
            "responses": self.responses,
            "accuracy": self.accuracy,
            "accuracy_with_timeouts": accuracy_with_timeouts,
            "timeout_rate": (self.timeouts / self.total_trials * 100) if self.total_trials > 0 else 0.0,
            "rolling_accuracy_10": self.rolling_accuracy(10),
            "rolling_accuracy_20": self.rolling_accuracy(20),
            "session_duration": 0.0,
            "trials_per_minute": 0.0,
        }
        
        # Calculate session duration and trial rate
        if self._trials and self._start_time:
            last_trial_time = self._trials[-1].timestamp
            report["session_duration"] = last_trial_time - self._start_time
            if report["session_duration"] > 0:
                report["trials_per_minute"] = self.total_trials / (report["session_duration"] / 60)
        
        return report
    
    def save_trials_to_file(self, save_path: str | Path, session_id: str = "") -> Path | None:
        """
        Save trial data to a CSV file.
        
        Args:
            save_path: Directory path where the file should be saved
            session_id: Optional session identifier for the filename
            
        Returns:
            Path to the saved file, or None if no trials to save
        """
        if not self._trials:
            return None
        
        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename
        filename = f"{session_id}-trials.csv" if session_id else "trials.csv"
        file_path = save_dir / filename
        
        # Define CSV columns
        fieldnames = [
            "trial_number",
            "outcome",
            "time_since_start_s",
            "trial_duration_s",
            "correct_port",
            "chosen_port",
            "timestamp",
        ]
        
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for trial in self._trials:
                row = {
                    "trial_number": trial.trial_number,
                    "outcome": trial.outcome.value,
                    "time_since_start_s": f"{trial.time_since_start:.3f}",
                    "trial_duration_s": f"{trial.trial_duration:.3f}",
                    "correct_port": trial.correct_port if trial.correct_port is not None else "",
                    "chosen_port": trial.chosen_port if trial.chosen_port is not None else "",
                    "timestamp": f"{trial.timestamp:.3f}",
                }
                writer.writerow(row)
        
        return file_path
