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
class TrackerGroupDefinition:
    """
    Declaration of a tracker group for a protocol.

    A tracker group covers one or more training stages and contains one or
    more named sub-trackers (e.g., "visual", "audio") for different trial
    types. Simple groups with no sub_trackers get a single "default"
    sub-tracker automatically.

    Attributes:
        name:          Internal key for the group (e.g., "interleaved_phase")
        display_name:  GUI label (e.g., "Interleaved Phase")
        sub_trackers:  List of sub-tracker names (e.g., ["visual", "audio"]).
                       If None, a single "default" sub-tracker is created.
        stages:        Set of stage names this group covers. When the engine
                       enters any of these stages, this group becomes active.
                       If None, the group name itself is used as the sole stage.
    """
    name: str
    display_name: str
    sub_trackers: list[str] | None = None
    stages: set[str] | None = None


def TrackerDefinition(name: str, display_name: str) -> TrackerGroupDefinition:
    """
    Backwards-compatible factory that creates a simple TrackerGroupDefinition.

    Equivalent to a group with a single "default" sub-tracker covering one
    stage whose name matches the group name. Existing protocols that return
    TrackerDefinition(...) from get_tracker_definitions() continue to work.
    """
    return TrackerGroupDefinition(
        name=name,
        display_name=display_name,
        sub_trackers=None,
        stages={name},
    )


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
    trial_type: str = ""  # Sub-tracker / modality name (e.g., "visual", "audio")
    details: dict = field(default_factory=dict)  # Optional extra data


class PerformanceTracker:
    """
    Tracks trial outcomes and provides statistics.
    
    Emits events when trials are recorded so the GUI can update.
    """
    
    def __init__(self, clock=None):
        self._trials: list[TrialRecord] = []
        self._listeners: dict[str, list[Callable]] = {}
        self._start_time: Optional[float] = None
        self._clock = clock  # Optional BehaviourClock for accelerated simulation

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
            except Exception as e:
                print(f"Warning: listener error in '{event_name}': {e}")
    
    def reset(self) -> None:
        """Clear all trial records."""
        self._trials.clear()
        self._successes = 0
        self._failures = 0
        self._timeouts = 0
        self._start_time = self._clock.time() if self._clock else datetime.now().timestamp()
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
        current_time = self._clock.time() if self._clock else datetime.now().timestamp()
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
            "stage",
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
                    "stage": trial.details.get("stage", ""),
                }
                writer.writerow(row)
        
        return file_path


# =============================================================================
# Tracker Group
# =============================================================================


class TrackerGroup:
    """
    A group of sub-trackers with aggregate query support.

    Each group covers one or more training stages and contains named
    sub-trackers for different trial types (e.g., "visual", "audio").
    Simple groups with a single "default" sub-tracker behave identically
    to a plain PerformanceTracker.

    Protocols record to a specific sub-tracker; the group can compute
    aggregate statistics across all sub-trackers for group-level queries.
    """

    DEFAULT_SUB = "default"

    def __init__(self, definition: TrackerGroupDefinition, clock=None):
        self._definition = definition
        self._clock = clock
        self._listeners: dict[str, list[Callable]] = {}

        sub_names = definition.sub_trackers or [self.DEFAULT_SUB]
        self._sub_trackers: dict[str, PerformanceTracker] = {}
        for sub_name in sub_names:
            tracker = PerformanceTracker(clock=clock)
            self._sub_trackers[sub_name] = tracker
            # Forward sub-tracker update events as group-level events
            tracker.on("update", lambda tracker=tracker, _name=sub_name, **kw: self._on_sub_update(_name))

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def display_name(self) -> str:
        return self._definition.display_name

    @property
    def stages(self) -> set[str]:
        return self._definition.stages or {self._definition.name}

    @property
    def sub_tracker_names(self) -> list[str]:
        return list(self._sub_trackers.keys())

    @property
    def is_simple(self) -> bool:
        """True if this group has only a 'default' sub-tracker."""
        return list(self._sub_trackers.keys()) == [self.DEFAULT_SUB]

    @property
    def total_trials(self) -> int:
        return sum(st.total_trials for st in self._sub_trackers.values())

    @property
    def successes(self) -> int:
        return sum(st.successes for st in self._sub_trackers.values())

    @property
    def failures(self) -> int:
        return sum(st.failures for st in self._sub_trackers.values())

    @property
    def timeouts(self) -> int:
        return sum(st.timeouts for st in self._sub_trackers.values())

    @property
    def responses(self) -> int:
        return self.successes + self.failures

    @property
    def accuracy(self) -> float:
        responses = self.responses
        if responses == 0:
            return 0.0
        return (self.successes / responses) * 100

    # -------------------------------------------------------------------------
    # Sub-tracker access
    # -------------------------------------------------------------------------

    def get_sub_tracker(self, name: str) -> Optional[PerformanceTracker]:
        return self._sub_trackers.get(name)

    def get_default_tracker(self) -> PerformanceTracker:
        """Get the default sub-tracker (first one if no 'default' exists)."""
        if self.DEFAULT_SUB in self._sub_trackers:
            return self._sub_trackers[self.DEFAULT_SUB]
        return next(iter(self._sub_trackers.values()))

    # -------------------------------------------------------------------------
    # Recording (delegates to a specific sub-tracker)
    # -------------------------------------------------------------------------

    def stimulus(self, target_port: int) -> None:
        """Signal stimulus presentation (emits event for GUI)."""
        self._emit("stimulus", port=target_port)

    def success(
        self,
        correct_port: int,
        trial_duration: float = 0.0,
        sub_tracker: str = DEFAULT_SUB,
        **details,
    ) -> None:
        st = self._sub_trackers.get(sub_tracker)
        if st is None:
            st = self.get_default_tracker()
        st.success(correct_port=correct_port, trial_duration=trial_duration, **details)

    def failure(
        self,
        correct_port: int,
        chosen_port: int,
        trial_duration: float = 0.0,
        sub_tracker: str = DEFAULT_SUB,
        **details,
    ) -> None:
        st = self._sub_trackers.get(sub_tracker)
        if st is None:
            st = self.get_default_tracker()
        st.failure(correct_port=correct_port, chosen_port=chosen_port,
                   trial_duration=trial_duration, **details)

    def timeout(
        self,
        correct_port: int,
        trial_duration: float = 0.0,
        sub_tracker: str = DEFAULT_SUB,
        **details,
    ) -> None:
        st = self._sub_trackers.get(sub_tracker)
        if st is None:
            st = self.get_default_tracker()
        st.timeout(correct_port=correct_port, trial_duration=trial_duration, **details)

    def reset(self) -> None:
        for st in self._sub_trackers.values():
            st.reset()

    # -------------------------------------------------------------------------
    # Aggregate queries (merge all sub-trackers)
    # -------------------------------------------------------------------------

    def get_all_trials(self) -> list[TrialRecord]:
        """Get all trials from all sub-trackers, sorted by timestamp."""
        trials = []
        for sub_name, st in self._sub_trackers.items():
            for trial in st.get_trials():
                trials.append(trial)
        trials.sort(key=lambda t: t.timestamp)
        return trials

    def get_all_trials_since(self, start_indices: dict[str, int]) -> list[TrialRecord]:
        """
        Get trials from all sub-trackers since given start indices, sorted.

        Args:
            start_indices: Dict mapping sub-tracker name to trial index.
                           Trials at or after the index are included.
        """
        trials = []
        for sub_name, st in self._sub_trackers.items():
            idx = start_indices.get(sub_name, 0)
            for trial in st.get_trials_since(idx):
                trials.append(trial)
        trials.sort(key=lambda t: t.timestamp)
        return trials

    def rolling_accuracy(self, n: int = 20) -> float:
        """
        Group-level rolling accuracy across all sub-trackers.

        Merges all trials, sorts by timestamp, takes last N non-timeout.
        """
        all_trials = self.get_all_trials()
        recent = [t for t in all_trials if t.outcome != TrialOutcome.TIMEOUT][-n:]
        if not recent:
            return 0.0
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def rolling_accuracy_since(
        self, n: int, start_indices: dict[str, int]
    ) -> Optional[float]:
        """
        Group-level rolling accuracy, stage-isolated.

        Returns None if fewer than n non-timeout trials since start_indices.
        """
        trials = self.get_all_trials_since(start_indices)
        recent = [t for t in trials if t.outcome != TrialOutcome.TIMEOUT][-n:]
        if len(recent) < n:
            return None
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def get_summary(self) -> str:
        if self.total_trials == 0:
            return "No trials yet"
        return (
            f"{self.successes}/{self.responses} correct ({self.accuracy:.0f}%) | "
            f"{self.timeouts} timeouts | "
            f"Last 20: {self.rolling_accuracy(20):.0f}%"
        )

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    def on(self, event_name: str, callback: Callable) -> None:
        self._listeners.setdefault(event_name, []).append(callback)

    def _emit(self, event_name: str, **kwargs) -> None:
        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception as e:
                print(f"Warning: TrackerGroup listener error in '{event_name}': {e}")

    def _on_sub_update(self, sub_name: str) -> None:
        """Called when a sub-tracker records a trial."""
        self._emit("update", group=self, sub_tracker=sub_name)


# =============================================================================
# Multi-tracker helpers
# =============================================================================

def save_merged_trials(
    trackers: dict[str, "PerformanceTracker | TrackerGroup"],
    save_path: str | Path,
    session_id: str = "",
) -> Path | None:
    """
    Merge trials from multiple trackers or tracker groups into a single CSV.

    Accepts either a dict of PerformanceTrackers (legacy) or a dict of
    TrackerGroups (new). Each row includes ``group`` and ``trial_type``
    columns. The ``trial_number`` column is global order after sorting.

    Returns:
        Path to the saved file, or None if no trials across all trackers.
    """
    # Collect (group_name, sub_name, trial) tuples
    all_trials: list[tuple[str, str, TrialRecord]] = []

    for name, obj in trackers.items():
        if isinstance(obj, TrackerGroup):
            for sub_name, sub_tracker in obj._sub_trackers.items():
                for trial in sub_tracker.get_trials():
                    all_trials.append((name, sub_name, trial))
        else:
            # Legacy PerformanceTracker
            for trial in obj.get_trials():
                all_trials.append((name, "", trial))

    if not all_trials:
        return None

    # Sort by timestamp for true chronological order
    all_trials.sort(key=lambda t: t[2].timestamp)

    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{session_id}-trials.csv" if session_id else "trials.csv"
    file_path = save_dir / filename

    fieldnames = [
        "group",
        "trial_type",
        "trial_number",
        "outcome",
        "time_since_start_s",
        "trial_duration_s",
        "correct_port",
        "chosen_port",
        "stage",
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for global_num, (group_name, sub_name, trial) in enumerate(all_trials, start=1):
            row = {
                "group": group_name,
                "trial_type": sub_name or trial.trial_type,
                "trial_number": global_num,
                "outcome": trial.outcome.value,
                "time_since_start_s": f"{trial.time_since_start:.3f}",
                "trial_duration_s": f"{trial.trial_duration:.3f}",
                "correct_port": trial.correct_port if trial.correct_port is not None else "",
                "chosen_port": trial.chosen_port if trial.chosen_port is not None else "",
                "stage": trial.details.get("stage", ""),
            }
            writer.writerow(row)

    return file_path
