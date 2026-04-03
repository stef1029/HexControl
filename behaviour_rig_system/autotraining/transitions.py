"""
Transition Rules and Condition Evaluation

Defines how and when the autotraining engine should move between stages.
Each Transition has a source stage, a destination stage, a priority,
and one or more Conditions that must ALL be met for the transition to fire.

Conditions are structured data evaluated against a context object that
exposes performance metrics from the PerformanceTracker plus autotraining-
specific counters (trials in current stage, consecutive outcomes, etc.).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.performance_tracker import TrialOutcome


# =============================================================================
# Condition operators
# =============================================================================

class Operator(Enum):
    """Comparison operators for conditions."""
    GTE = ">="
    LTE = "<="
    GT = ">"
    LT = "<"
    EQ = "=="
    NEQ = "!="


# =============================================================================
# Available metrics
# =============================================================================

METRIC_DESCRIPTIONS = {
    "rolling_accuracy":     "Accuracy (%) over last N non-timeout trials",
    "trials_in_stage":      "Number of completed trials in the current stage (this session)",
    "total_trials_in_stage": "Total trials in current stage across all sessions",
    "consecutive_correct":  "Current streak of consecutive correct responses",
    "consecutive_timeout":  "Current streak of consecutive timeouts",
    "total_trials":         "Total trials this session (all stages)",
    "session_time_minutes": "Minutes elapsed since session start",
    "rolling_trial_duration": "Average trial duration (s) over last N trials",
}


# =============================================================================
# Condition dataclass
# =============================================================================

@dataclass
class Condition:
    """
    A single condition that can be evaluated against performance metrics.

    Examples:
        Condition("rolling_accuracy", ">=", 80, window=10)
        Condition("rolling_accuracy", "<", 50, window=20, tracker="audio")
        Condition("trials_in_stage", ">=", 20)
        Condition("consecutive_correct", ">=", 5)

    Attributes:
        metric:   Name of the metric to evaluate (see METRIC_DESCRIPTIONS)
        operator: Comparison operator (e.g. ">=", "<=", ">", "<", "==", "!=")
        value:    Threshold value to compare against
        window:   Rolling window size (only used for rolling_accuracy)
        tracker:  If set, evaluate against this named tracker instead of the
                  per-stage tracker. Named trackers use no stage isolation
                  (last N trials from the tracker's full history).
    """
    metric: str
    operator: str | Operator
    value: float
    window: int = 10
    tracker: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.operator, str):
            self.operator = Operator(self.operator)

    def evaluate(self, context: "TransitionContext") -> bool:
        """
        Evaluate this condition against the given context.

        Returns True if the condition is met.
        """
        actual = context.get_metric(self.metric, self.window, self.tracker)
        if actual is None:
            return False

        op = self.operator
        if op == Operator.GTE:
            return actual >= self.value
        elif op == Operator.LTE:
            return actual <= self.value
        elif op == Operator.GT:
            return actual > self.value
        elif op == Operator.LT:
            return actual < self.value
        elif op == Operator.EQ:
            return actual == self.value
        elif op == Operator.NEQ:
            return actual != self.value
        return False

    def __repr__(self) -> str:
        w = f"(window={self.window})" if self.metric == "rolling_accuracy" else ""
        t = f" @{self.tracker}" if self.tracker else ""
        return f"{self.metric}{w} {self.operator.value} {self.value}{t}"


# =============================================================================
# Transition dataclass
# =============================================================================

@dataclass
class Transition:
    """
    A directed edge in the training graph.

    Attributes:
        from_stage:  Source stage name, or "*" for any stage
        to_stage:    Destination stage name, or "$saved" for the mouse's
                     persisted stage (used by warm-up exit)
        conditions:  ALL conditions must be True for this transition to fire
        priority:    Lower number = evaluated first. Useful when multiple
                     transitions could fire from the same stage.
        description: Human-readable explanation of this transition
    """
    from_stage: str
    to_stage: str
    conditions: list[Condition] = field(default_factory=list)
    priority: int = 10
    description: str = ""

    def can_fire(self, current_stage: str, context: "TransitionContext") -> bool:
        """
        Check if this transition should fire.

        Args:
            current_stage: Name of the current active stage
            context:       Performance metrics context

        Returns:
            True if from_stage matches and ALL conditions are met.
        """
        # Check source stage match
        if self.from_stage != "*" and self.from_stage != current_stage:
            return False

        # All conditions must be met
        return all(c.evaluate(context) for c in self.conditions)

    def __repr__(self) -> str:
        conds = " AND ".join(str(c) for c in self.conditions)
        return f"Transition({self.from_stage} -> {self.to_stage} | {conds})"


# =============================================================================
# Transition Context -- the bag of metrics conditions evaluate against
# =============================================================================

class TransitionContext:
    """
    Provides metric values for condition evaluation.

    Built from a dict of named PerformanceTrackers plus autotraining-
    specific counters maintained by the engine.

    Conditions can optionally specify a ``tracker`` name to evaluate
    against a specific tracker (e.g. "audio" or "visual") without stage
    isolation. When no tracker is specified, the per-stage tracker
    (looked up by ``current_stage_name``) is used with stage isolation.
    """

    def __init__(
        self,
        perf_trackers: dict[str, Any],
        current_stage_name: str,
        stage_start_trial_index: int = 0,
        trials_in_stage: int = 0,
        total_trials_in_stage: int = 0,
        consecutive_correct: int = 0,
        consecutive_timeout: int = 0,
        session_time_minutes: float = 0.0,
    ):
        self._perf_trackers = perf_trackers
        self._current_stage_name = current_stage_name
        self._stage_start_trial_index = stage_start_trial_index
        self._trials_in_stage = trials_in_stage
        self._total_trials_in_stage = total_trials_in_stage
        self._consecutive_correct = consecutive_correct
        self._consecutive_timeout = consecutive_timeout
        self._session_time_minutes = session_time_minutes

    def _get_stage_tracker(self) -> Any | None:
        """Get the per-stage tracker for the current stage (may be None)."""
        return self._perf_trackers.get(self._current_stage_name)

    def get_metric(
        self,
        metric: str,
        window: int = 10,
        tracker_name: str | None = None,
    ) -> float | None:
        """
        Look up a metric value by name.

        Args:
            metric:       Name of the metric (see METRIC_DESCRIPTIONS)
            window:       Rolling window size (for rolling_accuracy)
            tracker_name: If set, evaluate using this named tracker
                          without stage isolation. If None, use the
                          per-stage tracker with stage isolation.

        Returns None if the metric is unknown or if no suitable tracker
        is available (condition will not fire).
        """
        if metric == "rolling_accuracy":
            if tracker_name is not None:
                return self._rolling_accuracy_named(window, tracker_name)
            return self._rolling_accuracy_in_stage(window)
        elif metric == "trials_in_stage":
            return float(self._trials_in_stage)
        elif metric == "total_trials_in_stage":
            return float(self._total_trials_in_stage)
        elif metric == "consecutive_correct":
            return float(self._consecutive_correct)
        elif metric == "consecutive_timeout":
            return float(self._consecutive_timeout)
        elif metric == "total_trials":
            tracker = self._get_stage_tracker()
            return float(tracker.total_trials) if tracker else None
        elif metric == "session_time_minutes":
            return self._session_time_minutes
        elif metric == "rolling_trial_duration":
            if tracker_name is not None:
                return self._rolling_trial_duration_named(window, tracker_name)
            return self._rolling_trial_duration_in_stage(window)
        return None

    def _rolling_accuracy_in_stage(self, window: int) -> float | None:
        """
        Compute rolling accuracy using only trials from the current stage.

        Uses the per-stage tracker (looked up by current_stage_name) with
        stage isolation via stage_start_trial_index. This prevents trials
        from a previous stage bleeding into the window.

        Returns None if the per-stage tracker doesn't exist or there are
        fewer non-timeout trials than the window size.
        """
        tracker = self._get_stage_tracker()
        if tracker is None:
            return None
        stage_trials = tracker.get_trials_since(self._stage_start_trial_index)
        recent = [t for t in stage_trials if t.outcome != TrialOutcome.TIMEOUT][-window:]
        if len(recent) < window:
            return None
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def _rolling_accuracy_named(self, window: int, tracker_name: str) -> float | None:
        """
        Compute rolling accuracy from a named tracker without stage isolation.

        Uses the last N non-timeout trials from the tracker's full history,
        regardless of stage boundaries. This is used for general-purpose
        trackers (e.g. "audio", "visual") that span multiple stages.

        Returns None if the tracker doesn't exist or there are fewer
        non-timeout trials than the window size.
        """
        tracker = self._perf_trackers.get(tracker_name)
        if tracker is None:
            return None
        recent = [t for t in tracker.get_trials() if t.outcome != TrialOutcome.TIMEOUT][-window:]
        if len(recent) < window:
            return None
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def _rolling_trial_duration_in_stage(self, window: int) -> float | None:
        """
        Average trial_duration (s) over the last N trials in the current stage.

        Includes all trial outcomes (success, failure, timeout).
        Returns None if the tracker doesn't exist or there are fewer
        trials than the window size.
        """
        tracker = self._get_stage_tracker()
        if tracker is None:
            return None
        stage_trials = tracker.get_trials_since(self._stage_start_trial_index)
        recent = stage_trials[-window:]
        if len(recent) < window:
            return None
        return sum(t.trial_duration for t in recent) / len(recent)

    def _rolling_trial_duration_named(self, window: int, tracker_name: str) -> float | None:
        """
        Average trial_duration (s) over the last N trials from a named tracker.

        No stage isolation -- uses the tracker's full history.
        Returns None if the tracker doesn't exist or there are fewer
        trials than the window size.
        """
        tracker = self._perf_trackers.get(tracker_name)
        if tracker is None:
            return None
        recent = tracker.get_trials()[-window:]
        if len(recent) < window:
            return None
        return sum(t.trial_duration for t in recent) / len(recent)
