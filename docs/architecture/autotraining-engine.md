# Autotraining Engine Internals

The `AutotrainingEngine` is a protocol-agnostic state machine that manages training stage progression. This page covers the internal mechanics that aren't visible from the user-facing API.

## Engine state

The engine tracks these internal counters:

| Counter | Scope | Description |
|---------|-------|-------------|
| `_trials_in_stage` | Session | Trials in the current stage this session only |
| `_total_trials_in_stage` | Cross-session | Cumulative trials in the current stage |
| `_consecutive_correct` | Session | Current streak of correct responses |
| `_consecutive_timeout` | Session | Current streak of timeouts |
| `_stage_start_trial_index` | Session | PerformanceTracker trial index when stage started |
| `_in_warmup` | Session | Whether currently in warm-up |

### Counter behaviour on trial completion

```python
def on_trial_complete(self, outcome, ...):
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
        # Note: consecutive_correct is NOT reset on timeout
```

!!! note
    Timeouts don't reset `consecutive_correct`. This matches the rolling accuracy logic where timeouts are excluded from accuracy calculations. A mouse that is performing well but occasionally times out shouldn't lose its streak.

### Counter behaviour on stage change

When `_set_stage()` is called:

- `_trials_in_stage` resets to 0
- `_consecutive_correct` resets to 0
- `_consecutive_timeout` resets to 0
- `_stage_start_trial_index` is set to the current tracker trial count
- `_total_trials_in_stage` is either reset to 0 (new stage) or restored from `_saved_trials_in_stage` (resuming saved stage)

## TransitionContext

The `TransitionContext` is the metric bag that conditions evaluate against. It wraps the PerformanceTracker plus the engine's internal counters:

```python
context = TransitionContext(
    perf_tracker=self._perf_tracker,
    trials_in_stage=self._trials_in_stage,
    total_trials_in_stage=self._total_trials_in_stage,
    consecutive_correct=self._consecutive_correct,
    consecutive_timeout=self._consecutive_timeout,
    session_time_minutes=session_minutes,
    stage_start_trial_index=self._stage_start_trial_index,
)
```

### Stage-scoped rolling accuracy

The most important metric is `rolling_accuracy`, computed by `TransitionContext._rolling_accuracy_in_stage()`:

```python
def _rolling_accuracy_in_stage(self, window: int) -> float | None:
    # Only consider trials from the CURRENT stage
    stage_trials = self._perf_tracker.get_trials_since(self._stage_start_trial_index)

    # Filter out timeouts
    recent = [t for t in stage_trials if t.outcome != TrialOutcome.TIMEOUT][-window:]

    # Return None if insufficient data (condition won't fire)
    if len(recent) < window:
        return None

    successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
    return (successes / len(recent)) * 100
```

Key design decisions:

1. **Stage-scoped** -- Only uses trials from after the stage started. Prevents old trials from bleeding into the window and causing premature transitions
2. **Timeout exclusion** -- Timeouts don't count as either correct or incorrect
3. **None on insufficient data** -- If there aren't enough non-timeout trials to fill the window, returns `None`. This causes `Condition.evaluate()` to return `False`, preventing both forward and regression transitions from firing before enough data exists

## Transition evaluation

After each trial, `_evaluate_transitions()` checks all rules:

```python
def _evaluate_transitions(self):
    context = TransitionContext(...)

    # Transitions are sorted by priority (lowest first)
    for transition in self._transitions:
        if transition.can_fire(self._current_stage.name, context):
            return self._fire_transition(transition)

    return None  # No transition fired
```

The first matching transition wins. Since transitions are sorted by priority:

1. Emergency rules (0-4) are checked first
2. Regression rules (5-9) are checked next
3. Forward rules (10-19) are checked last

This ensures a struggling mouse falls back before the system tries to advance it.

## Warm-up handoff

The warm-up mechanism:

1. On session start, if a warm-up stage exists and `_should_warmup()` returns `True`, the engine starts in warm-up
2. The warm-up exit transition uses `to_stage="$saved"`, which resolves to `_saved_stage_name`
3. When `_fire_transition()` sees `"$saved"`, it replaces it with the actual saved stage name
4. The engine calls `_set_stage()` for the saved stage, which restores `_total_trials_in_stage` from `_saved_trials_in_stage`

### The `warmup_after` gate

```python
def _should_warmup(self):
    gate = self._warmup_stage.warmup_after
    if gate is None:
        return True  # No gate, always warm up

    # Compare positions in the stage ordering
    stage_names = list(self._stages.keys())
    gate_idx = stage_names.index(gate)
    saved_idx = stage_names.index(self._saved_stage_name)

    return saved_idx >= gate_idx  # Only warm up if past the gate
```

This prevents early-stage mice from doing warm-up with parameters they haven't encountered yet.

## Per-stage tracker switching

When the engine switches stages, it also switches to the matching performance tracker:

```python
def _set_stage(self, stage):
    # ...
    if stage.name in self._perf_trackers:
        self._perf_tracker = self._perf_trackers[stage.name]
```

This means each stage writes to its own tracker, which appears as a separate tab in the GUI. The `_stage_start_trial_index` is updated to the new tracker's current trial count, ensuring rolling accuracy only considers this stage's trials.

## Session end state

```python
def get_session_end_state(self) -> dict:
    return {
        "current_stage": self._current_stage.name,
        "trials_in_stage": self._total_trials_in_stage,
        "in_warmup": self._in_warmup,
    }
```

The `in_warmup` flag is critical: if the session ended during warm-up, the protocol should **not** save the training state, preserving the mouse's previous progress.
