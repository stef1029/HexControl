# Autotraining Concepts

## The mental model

Think of autotraining as a **directed graph** where:

- **Nodes** are training stages (parameter configurations)
- **Edges** are transitions (rules that move between stages)
- The mouse starts at a node and traverses edges based on performance

The engine is protocol-agnostic -- it doesn't run trials. Instead, the protocol:

1. Asks the engine for the current parameter set before each trial
2. Runs the trial using those parameters
3. Reports the outcome back to the engine
4. The engine evaluates transitions and possibly switches stages

## BASE_DEFAULTS and overrides

Every stage inherits from a common set of default parameters called `BASE_DEFAULTS`:

```python
BASE_DEFAULTS = {
    "port_0_enabled": False,
    "port_1_enabled": False,
    # ... (all 6 ports default to disabled)
    "cue_duration": 0.0,
    "led_brightness": 255,
    "weight_offset": 3.0,
    "platform_settle_time": 1.0,
    "response_timeout": 5.0,
    "wait_duration": 0.0,
    "iti": 1.0,
    "punishment_duration": 0.0,
    "punishment_enabled": False,
    "audio_enabled": False,
    "audio_proportion": 6,
}
```

A stage only specifies what is **different** from these defaults. When the engine activates a stage, it merges `BASE_DEFAULTS` with the stage's `overrides` dict.

For example, a stage that enables port 0 with a generous timeout:

```python
Stage(
    name="phase_1",
    display_name="Phase 1",
    overrides={
        "port_0_enabled": True,
        "response_timeout": 60.0,
    },
)
```

The full parameter set for this stage is all of `BASE_DEFAULTS` with `port_0_enabled` changed to `True` and `response_timeout` changed to `60.0`.

## Forward and regression transitions

Transitions have a **priority** that determines evaluation order:

| Priority range | Purpose |
|---------------|---------|
| 0-4 | Global/emergency rules (e.g. warm-up exit) |
| 5-9 | Regression rules (falling back to easier stages) |
| 10-19 | Forward progression (advancing to harder stages) |

Lower priority numbers are evaluated first. This means regression rules are checked before forward rules, so a mouse that is struggling will fall back before the system tries to advance it.

### Why regression matters

Without regression, a mouse could get stuck on a stage it was accidentally promoted to. Regression transitions provide a safety net: if performance drops significantly (e.g. below 30-40%), the mouse reverts to an easier stage to rebuild confidence before trying again.

## Warm-up

The warm-up stage is a simple, easy task that runs at the start of every session. Its purpose is to engage the mouse and verify it's ready to perform before resuming the real training stage.

### How warm-up works

1. If a warm-up stage exists and the mouse meets the warm-up gate (see below), the session starts in warm-up
2. After meeting the warm-up exit conditions (e.g. 5 consecutive correct, 10+ trials), the engine switches to the mouse's **saved stage** from the previous session
3. If the session ends during warm-up, training state is **not updated** -- the mouse will resume at the same saved stage next time

### The `warmup_after` gate

The warm-up stage can have a `warmup_after` field specifying a stage name. Warm-up only runs if the mouse's saved stage is at or past that point in the training sequence. This prevents early-stage mice from doing warm-up with parameters they haven't learned yet.

### The `$saved` target

The special transition target `"$saved"` means "go to whatever stage the mouse was on at the end of the last session". This is used exclusively by the warm-up exit transition.

## Rolling accuracy

Rolling accuracy is the key metric for most transitions. It measures accuracy over the last N non-timeout trials, where N is the `window` parameter.

### Stage-scoped windows

Rolling accuracy is computed using **only trials from the current stage**. This prevents a problem where:

1. Mouse is at 90% accuracy on Stage A
2. Mouse transitions to Stage B
3. The first few trials on Stage B are included in the rolling window alongside Stage A trials
4. The inflated accuracy causes a premature forward transition from Stage B

By scoping to stage-only trials, the engine requires the mouse to demonstrate competence at the *current* stage before advancing.

### Minimum window requirement

If there are fewer non-timeout trials in the current stage than the window size, rolling accuracy returns `None` and the condition evaluates as "not met". This prevents transitions from firing before enough data has been collected.

## Per-stage trackers

Autotraining protocols typically declare one performance tracker per stage (via `get_tracker_definitions()`). The engine automatically switches to the tracker matching the current stage name. This gives each stage its own performance tab in the GUI.

## Persistence across sessions

Training progress is saved after each session and loaded at the start of the next one. The saved state includes:

- **Current stage** -- Which stage the mouse was on when the session ended
- **Trials in stage** -- Cumulative trial count in the current stage (across all sessions)
- **Stage history** -- Record of all stages visited with entry/exit dates

This allows training to span weeks or months, with each session picking up where the last one left off. See [Persistence & Progress](persistence.md) for details.
