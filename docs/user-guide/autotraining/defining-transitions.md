# Defining Transitions

Transitions are the rules that move mice between training stages. Each transition is a directed edge in the training graph with conditions that must all be met for the transition to fire.

## The Transition dataclass

```python
from autotraining.transitions import Transition, Condition

Transition(
    from_stage="multiple_leds_2x",
    to_stage="multiple_leds_6x",
    conditions=[
        Condition("rolling_accuracy", ">=", 90, window=40),
    ],
    priority=10,
    description="2-port discrimination mastered (>90% over 40 trials)",
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `from_stage` | `str` | required | Source stage name, or `"*"` for any stage |
| `to_stage` | `str` | required | Target stage name, or `"$saved"` for the mouse's saved stage |
| `conditions` | `list[Condition]` | `[]` | ALL conditions must be `True` for this transition to fire |
| `priority` | `int` | `10` | Evaluation order -- lower numbers are checked first |
| `description` | `str` | `""` | Human-readable explanation (logged when transition fires) |

### Special values

- **`from_stage="*"`** -- Matches any current stage (useful for global rules)
- **`to_stage="$saved"`** -- Resolves to the mouse's persisted stage from the last session (used by warm-up exit)

## The Condition dataclass

```python
Condition(
    metric="rolling_accuracy",
    operator=">=",
    value=80,
    window=20,
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | `str` | required | Name of the metric to evaluate |
| `operator` | `str` | required | Comparison operator |
| `value` | `float` | required | Threshold to compare against |
| `window` | `int` | `10` | Window size (only used for `rolling_accuracy`) |

### Available metrics

| Metric | Description |
|--------|-------------|
| `rolling_accuracy` | Accuracy (%) over the last N non-timeout trials **in the current stage only** |
| `trials_in_stage` | Number of trials completed in the current stage this session |
| `total_trials_in_stage` | Total trials in the current stage across all sessions |
| `consecutive_correct` | Current streak of consecutive correct responses |
| `consecutive_timeout` | Current streak of consecutive timeouts |
| `total_trials` | Total trials this session (all stages combined) |
| `session_time_minutes` | Minutes elapsed since session start |

!!! important
    `rolling_accuracy` is stage-scoped: it only considers trials from the current stage, not from previous stages. If fewer non-timeout trials exist in the current stage than the window size, the condition evaluates as "not met" (returns `None`).

### Available operators

| Operator | Meaning |
|----------|---------|
| `>=` | Greater than or equal |
| `<=` | Less than or equal |
| `>` | Greater than |
| `<` | Less than |
| `==` | Equal |
| `!=` | Not equal |

## Priority conventions

| Range | Purpose | Example |
|-------|---------|---------|
| 0-4 | Global/emergency rules | Warm-up exit |
| 5-9 | Regression rules | Performance drop fallbacks |
| 10-19 | Forward progression | Main training path |

Lower numbers are evaluated first. This means:

1. Warm-up exit is checked first
2. If the mouse is struggling (regression conditions met), it falls back before forward rules can fire
3. Forward rules are only evaluated if no regression rule triggered

## Example transitions

### Warm-up exit

```python
Transition(
    from_stage="warm_up",
    to_stage="$saved",
    conditions=[
        Condition("consecutive_correct", ">=", 5),
        Condition("trials_in_stage", ">=", 10),
    ],
    priority=1,
    description="Warm-up complete (5 consecutive correct, 10+ trials)",
)
```

After 10+ trials with 5 consecutive correct responses, exit warm-up and resume the mouse's saved stage.

### Forward progression

```python
Transition(
    from_stage="introduce_1_led",
    to_stage="introduce_another_led",
    conditions=[
        Condition("rolling_accuracy", ">=", 90, window=30),
    ],
    priority=10,
    description="Single LED mastered (>90% over 30 trials)",
)
```

Requires 90% accuracy over the last 30 non-timeout trials before advancing to a second port.

### Forward progression (cue duration ladder)

```python
Transition(
    from_stage="cue_duration_1000ms",
    to_stage="cue_duration_750ms",
    conditions=[
        Condition("rolling_accuracy", ">=", 75, window=30),
    ],
    priority=10,
    description="1000ms cue mastered (>=75% over 30 trials)",
)
```

Note how the accuracy threshold decreases as the cue gets shorter (90% for port introduction, 75% for 1000ms, 60% for 750ms, etc.), reflecting the increasing difficulty.

### Regression

```python
Transition(
    from_stage="multiple_leds_6x",
    to_stage="multiple_leds_2x",
    conditions=[
        Condition("rolling_accuracy", "<", 30, window=20),
    ],
    priority=5,
    description="Performance regression at 6-port (<30% over 20 trials)",
)
```

If accuracy drops below 30% over 20 trials, revert to the easier 2-port stage. The priority of 5 ensures this is checked before any forward transition from the same stage.

## Organising transitions

Transitions are collected in a list called `TRANSITIONS`, typically in a `graph.py` file:

```python
TRANSITIONS: list[Transition] = [
    # Warm-up exit
    Transition(from_stage="warm_up", to_stage="$saved", ...),

    # Port introduction forward
    Transition(from_stage="introduce_1_led", to_stage="introduce_another_led", ...),
    Transition(from_stage="introduce_another_led", to_stage="multiple_leds_2x", ...),
    Transition(from_stage="multiple_leds_2x", to_stage="multiple_leds_6x", ...),

    # Port introduction regression
    Transition(from_stage="phase_2_cue_with_punish", to_stage="phase_2_cue_no_punish", ...),

    # ... etc
]
```

The engine sorts transitions by priority at initialization, so the order in the list doesn't matter for evaluation (but keeping them logically ordered helps readability).

## Tips for writing good transitions

1. **Always include a minimum trial count** -- Prevents transitions from firing before enough data is collected. Use `trials_in_stage >= N` alongside accuracy conditions
2. **Set regression thresholds well below forward thresholds** -- Forward might require 80%, regression triggers at 30%. This hysteresis prevents oscillation
3. **Use `total_trials_in_stage` for cross-session requirements** -- If a mouse should spend at least 200 cumulative trials at a stage before advancing, use `total_trials_in_stage`
4. **Keep descriptions clear** -- They appear in the GUI log and transition CSV when transitions fire
