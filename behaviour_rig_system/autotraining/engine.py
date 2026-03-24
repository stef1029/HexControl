"""
Autotraining Engine

The core state machine that:
1. Loads stage definitions and the transition graph
2. Manages the current active parameter set
3. Evaluates transition rules after each trial
4. Handles the warm-up -> saved-stage handoff at session start
5. Tracks autotraining-specific counters (trials in stage, streaks, etc.)

The engine is protocol-agnostic -- it doesn't run trials itself. Instead,
the protocol calls engine.get_active_params() before each trial and
engine.on_trial_complete() after each trial.
"""

import time
from typing import Any, Callable, Optional

from .stage import Stage
from .transitions import Transition, TransitionContext


class AutotrainingEngine:
    """
    Manages training stage progression.

    Usage in a protocol's run() function:

        engine = AutotrainingEngine(stages, transitions, persistence_state)
        engine.initialise_session(perf_tracker, log)

        while running:
            params = engine.get_active_params()
            # ... run trial with params ...
            engine.on_trial_complete(outcome, correct_port, chosen_port, trial_duration)
    """

    def __init__(
        self,
        stages: dict[str, Stage],
        transitions: list[Transition],
        saved_stage_name: Optional[str] = None,
        saved_trials_in_stage: int = 0,
    ):
        """
        Args:
            stages:              Dict of stage_name -> Stage
            transitions:         List of Transition rules (will be sorted by priority)
            saved_stage_name:    The stage the mouse was on at end of last session
                                 (None = first non-warmup stage)
            saved_trials_in_stage: Cumulative trial count in the saved stage
        """
        self._stages = stages
        self._transitions = sorted(transitions, key=lambda t: t.priority)

        # Find the warm-up stage
        self._warmup_stage: Optional[Stage] = None
        for stage in stages.values():
            if stage.is_warmup:
                self._warmup_stage = stage
                break

        # Determine the "real" stage the mouse should be on after warm-up
        self._saved_stage_name = saved_stage_name
        self._saved_trials_in_stage = saved_trials_in_stage

        # If no saved stage, use first non-warmup stage
        if self._saved_stage_name is None or self._saved_stage_name not in stages:
            for s in stages.values():
                if not s.is_warmup:
                    self._saved_stage_name = s.name
                    break

        # Runtime state
        self._current_stage: Optional[Stage] = None
        self._active_params: dict[str, Any] = {}
        self._trials_in_stage: int = 0                 # This session only
        self._total_trials_in_stage: int = 0           # Across sessions
        self._consecutive_correct: int = 0
        self._consecutive_timeout: int = 0
        self._in_warmup: bool = False
        self._session_start_time: float = 0.0
        self._stage_start_trial_index: int = 0         # perf_tracker index when stage started

        # Callbacks
        self._perf_tracker: Any = None
        self._log: Callable[[str], None] = lambda msg: None

        # Transition history for this session
        self._transition_log: list[dict[str, Any]] = []

    # =========================================================================
    # Session lifecycle
    # =========================================================================

    def initialise_session(
        self,
        perf_tracker: Any,
        log: Callable[[str], None],
    ) -> None:
        """
        Set up the engine for a new session.

        If a warm-up stage exists, start there. Otherwise go directly
        to the saved/first stage.

        Args:
            perf_tracker: PerformanceTracker instance from the protocol framework
            log:          Logging function (prints to GUI)
        """
        self._perf_tracker = perf_tracker
        self._log = log
        self._session_start_time = time.time()

        if self._warmup_stage is not None and self._should_warmup():
            self._set_stage(self._warmup_stage, is_warmup_entry=True)
            self._log(f"Starting warm-up stage: {self._warmup_stage.display_name}")
            self._log(f"  After warm-up, will resume: {self._saved_stage_name}")
        else:
            stage = self._stages[self._saved_stage_name]
            self._set_stage(stage)
            self._log(f"Starting at saved stage: {stage.display_name}")

    def _should_warmup(self) -> bool:
        """
        Check whether warmup should run this session.

        If the warmup stage has a ``warmup_after`` stage set, warmup is
        only used when the mouse's saved stage is at or past that stage
        in the stage ordering.  Otherwise warmup always runs.
        """
        if self._warmup_stage is None:
            return False

        gate = self._warmup_stage.warmup_after
        if gate is None:
            return True  # no gate — always warm up

        stage_names = list(self._stages.keys())
        if gate not in stage_names:
            self._log(f"WARNING: warmup_after stage '{gate}' not found, skipping warm-up")
            return False

        gate_idx = stage_names.index(gate)
        saved_idx = stage_names.index(self._saved_stage_name)
        if saved_idx < gate_idx:
            self._log(
                f"Skipping warm-up: mouse is on '{self._saved_stage_name}' "
                f"which is before warmup gate '{gate}'"
            )
            return False

        return True

    def _set_stage(self, stage: Stage, is_warmup_entry: bool = False) -> None:
        """
        Switch to a new stage.

        Resets session-level counters. If entering a non-warmup stage that
        matches the saved stage, restores the cumulative trial count.
        """
        self._current_stage = stage
        self._active_params = stage.get_params()
        self._trials_in_stage = 0
        self._consecutive_correct = 0
        self._consecutive_timeout = 0
        self._in_warmup = is_warmup_entry

        # Record the perf_tracker trial index so rolling_accuracy
        # only considers trials from this stage onwards
        if self._perf_tracker is not None:
            self._stage_start_trial_index = self._perf_tracker.total_trials
        else:
            self._stage_start_trial_index = 0

        # Restore cumulative trial count if resuming saved stage
        if not is_warmup_entry and stage.name == self._saved_stage_name:
            self._total_trials_in_stage = self._saved_trials_in_stage
        else:
            self._total_trials_in_stage = 0

    # =========================================================================
    # Trial interface -- called by the protocol
    # =========================================================================

    def get_active_params(self) -> dict[str, Any]:
        """
        Get the current parameter set for the next trial.

        The protocol should call this before each trial to pick up
        any parameter changes from stage transitions.
        """
        return self._active_params

    @property
    def current_stage_name(self) -> str:
        """Name of the currently active stage."""
        return self._current_stage.name if self._current_stage else "unknown"

    @property
    def current_stage_display(self) -> str:
        """Display name of the currently active stage."""
        return self._current_stage.display_name if self._current_stage else "Unknown"

    @property
    def in_warmup(self) -> bool:
        """True if currently in the warm-up stage."""
        return self._in_warmup

    @property
    def trials_in_stage(self) -> int:
        """Number of trials completed in the current stage this session."""
        return self._trials_in_stage

    @property
    def total_trials_in_stage(self) -> int:
        """Total trials in the current stage across all sessions."""
        return self._total_trials_in_stage

    def on_trial_complete(
        self,
        outcome: str,
        correct_port: int,
        chosen_port: Optional[int] = None,
        trial_duration: float = 0.0,
    ) -> Optional[str]:
        """
        Notify the engine that a trial has completed.

        Updates internal counters and evaluates transition rules.

        Args:
            outcome:       "success", "failure", or "timeout"
            correct_port:  The correct port for this trial
            chosen_port:   The port the mouse chose (None for timeout)
            trial_duration: Trial duration in seconds

        Returns:
            Name of the new stage if a transition occurred, None otherwise.
        """
        # Update counters
        self._trials_in_stage += 1
        self._total_trials_in_stage += 1

        if outcome == "success":
            self._consecutive_correct += 1
            self._consecutive_timeout = 0
        elif outcome == "failure":
            self._consecutive_correct = 0
            self._consecutive_timeout = 0
        elif outcome == "timeout":
            self._consecutive_timeout += 1
            # Don't reset consecutive_correct on timeout (matches rolling_accuracy logic)

        # Evaluate transitions
        new_stage_name = self._evaluate_transitions()
        return new_stage_name

    # =========================================================================
    # Transition evaluation
    # =========================================================================

    def _evaluate_transitions(self) -> Optional[str]:
        """
        Check all transition rules and fire the first matching one.

        Transitions are evaluated in priority order (lowest number first).
        The first transition whose conditions are ALL met will fire.

        Returns:
            Name of the new stage if a transition fired, None otherwise.
        """
        if self._current_stage is None or self._perf_tracker is None:
            return None

        session_minutes = (time.time() - self._session_start_time) / 60.0

        context = TransitionContext(
            perf_tracker=self._perf_tracker,
            trials_in_stage=self._trials_in_stage,
            total_trials_in_stage=self._total_trials_in_stage,
            consecutive_correct=self._consecutive_correct,
            consecutive_timeout=self._consecutive_timeout,
            session_time_minutes=session_minutes,
            stage_start_trial_index=self._stage_start_trial_index,
        )

        for transition in self._transitions:
            if transition.can_fire(self._current_stage.name, context):
                return self._fire_transition(transition)

        return None

    def _fire_transition(self, transition: Transition) -> str:
        """
        Execute a transition: switch to the target stage.

        Handles the special "$saved" target for warm-up exit.

        Returns:
            Name of the new stage.
        """
        target_name = transition.to_stage

        # Special target: warm-up exit goes to the mouse's saved stage
        if target_name == "$saved":
            target_name = self._saved_stage_name

        if target_name not in self._stages:
            self._log(f"WARNING: Transition target '{target_name}' not found, staying on current stage")
            return self._current_stage.name

        old_stage = self._current_stage
        new_stage = self._stages[target_name]

        # Log the transition
        desc = f" ({transition.description})" if transition.description else ""
        self._log(f">>> STAGE TRANSITION: {old_stage.display_name} -> {new_stage.display_name}{desc}")
        self._log(f"    Trials in previous stage: {self._trials_in_stage}")

        # Record in transition log
        self._transition_log.append({
            "timestamp": time.time(),
            "from_stage": old_stage.name,
            "to_stage": new_stage.name,
            "trigger": transition.description or str(transition),
            "trial_number": self._perf_tracker.total_trials if self._perf_tracker else 0,
        })

        # Apply the transition
        self._set_stage(new_stage)

        return new_stage.name

    # =========================================================================
    # State for persistence
    # =========================================================================

    def get_session_end_state(self) -> dict[str, Any]:
        """
        Get the state to persist at session end.

        Returns a dict that can be passed to persistence.save_training_state().
        """
        return {
            "current_stage": self._current_stage.name if self._current_stage else self._saved_stage_name,
            "trials_in_stage": self._total_trials_in_stage,
            "in_warmup": self._in_warmup,
        }

    def get_transition_log(self) -> list[dict[str, Any]]:
        """Get the list of transitions that occurred this session."""
        return list(self._transition_log)
