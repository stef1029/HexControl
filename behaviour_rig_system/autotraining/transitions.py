"""
Transition Rules and Condition Evaluation

Defines how and when the autotraining engine should move between stages.
Each Transition has a source stage, a destination stage, a priority,
and one or more Conditions that must ALL be met for the transition to fire.

Conditions are structured data evaluated against a context object that
exposes performance metrics from the active :class:`Tracker` plus
autotraining-specific counters (trials in current stage, consecutive
outcomes, etc.).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.tracker import TrialOutcome


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

    Built from the engine's runtime state. All accuracy queries are
    stage-isolated via ``stage_start_indices``. A Condition with no
    ``tracker`` queries the active tracker's aggregate (across all
    sub-trackers); a Condition with ``tracker="audio"`` queries the
    named sub-tracker within the active tracker.
    """

    def __init__(
        self,
        current_stage_name: str,
        trials_in_stage: int = 0,
        total_trials_in_stage: int = 0,
        consecutive_correct: int = 0,
        consecutive_timeout: int = 0,
        session_time_minutes: float = 0.0,
        active_tracker: Any = None,
        stage_start_indices: dict[str, int] | None = None,
    ):
        self._current_stage_name = current_stage_name
        self._trials_in_stage = trials_in_stage
        self._total_trials_in_stage = total_trials_in_stage
        self._consecutive_correct = consecutive_correct
        self._consecutive_timeout = consecutive_timeout
        self._session_time_minutes = session_time_minutes
        self._active_tracker = active_tracker
        self._stage_start_indices = stage_start_indices or {}

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
            tracker_name: If set, queries the named sub-tracker within
                          the active tracker (stage-isolated). If None,
                          queries the active tracker aggregate.

        Returns None if the metric is unknown or if no active tracker
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
            if self._active_tracker is not None:
                return float(self._active_tracker.total_trials)
            return None
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

        Merges all sub-trackers of the active tracker, isolated by
        ``stage_start_indices``. Returns None if no active tracker or
        fewer than ``window`` non-timeout trials.
        """
        if self._active_tracker is None:
            return None
        return self._active_tracker.rolling_accuracy_since(
            window, self._stage_start_indices
        )

    def _rolling_accuracy_named(self, window: int, tracker_name: str) -> float | None:
        """
        Compute rolling accuracy from a named sub-tracker, stage-isolated.

        Queries the named sub-tracker within the active tracker, using
        ``stage_start_indices`` for stage isolation. Returns None if the
        sub-tracker doesn't exist or there are fewer non-timeout trials
        than the window size.
        """
        if self._active_tracker is None:
            return None
        sub = self._active_tracker.get_sub_tracker(tracker_name)
        if sub is None:
            return None
        start_idx = self._stage_start_indices.get(tracker_name, 0)
        stage_trials = sub.get_trials_since(start_idx)
        recent = [t for t in stage_trials if t.outcome != TrialOutcome.TIMEOUT][-window:]
        if len(recent) < window:
            return None
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def _rolling_trial_duration_in_stage(self, window: int) -> float | None:
        """
        Average trial_duration (s) over the last N trials in the current stage.

        Includes all trial outcomes (success, failure, timeout). Returns
        None if no active tracker or fewer trials than the window size.
        """
        if self._active_tracker is None:
            return None
        trials = self._active_tracker.get_all_trials_since(self._stage_start_indices)
        recent = trials[-window:]
        if len(recent) < window:
            return None
        return sum(t.trial_duration for t in recent) / len(recent)

    def _rolling_trial_duration_named(self, window: int, tracker_name: str) -> float | None:
        """
        Average trial_duration (s) over the last N trials from a named sub-tracker.

        Stage-isolated via ``stage_start_indices``. Returns None if the
        sub-tracker doesn't exist or there are fewer trials than the
        window size.
        """
        if self._active_tracker is None:
            return None
        sub = self._active_tracker.get_sub_tracker(tracker_name)
        if sub is None:
            return None
        start_idx = self._stage_start_indices.get(tracker_name, 0)
        stage_trials = sub.get_trials_since(start_idx)
        recent = stage_trials[-window:]
        if len(recent) < window:
            return None
        return sum(t.trial_duration for t in recent) / len(recent)
