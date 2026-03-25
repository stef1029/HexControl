# Persistence & Progress

Training state is saved between sessions so mice resume where they left off. Each mouse has its own progress directory with a JSON state file and a CSV transition log.

## Storage layout

```
autotraining_progress/
├── M001/
│   ├── training_state.json     # Current state
│   └── training_log.csv        # Append-only transition history
├── M002/
│   ├── training_state.json
│   └── training_log.csv
└── ...
```

The `autotraining_progress/` folder lives inside the cohort save directory by default. Protocols can override this with the `progress_folder_override` parameter.

## Training state (JSON)

The `training_state.json` file contains the mouse's current training state:

```json
{
  "mouse_id": "M001",
  "current_stage": "phase_3_two_ports",
  "trials_in_stage": 150,
  "sessions_in_stage": 3,
  "last_session_date": "2025-03-25",
  "stage_history": [
    {
      "stage": "phase_1_platform_reward",
      "entered": "2025-03-20",
      "exited": "2025-03-22",
      "sessions": 2
    },
    {
      "stage": "phase_1_rearing",
      "entered": "2025-03-22",
      "exited": "2025-03-23",
      "sessions": 1
    },
    {
      "stage": "phase_2_cue_no_punish",
      "entered": "2025-03-23",
      "exited": "2025-03-23",
      "sessions": 1
    },
    {
      "stage": "phase_3_two_ports",
      "entered": "2025-03-25",
      "exited": null,
      "sessions": 1
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `mouse_id` | Mouse identifier |
| `current_stage` | Stage name the mouse was on when the last session ended |
| `trials_in_stage` | Cumulative number of trials at the current stage (across all sessions) |
| `sessions_in_stage` | Number of sessions spent at the current stage |
| `last_session_date` | Date of the most recent session |
| `stage_history` | List of all stages visited, with entry/exit dates and session counts |

## Transition log (CSV)

The `training_log.csv` file is an append-only record of every stage transition:

```csv
timestamp,session_id,from_stage,to_stage,trigger,trial_number
2025-03-22 14:30:15,20250322_143000,phase_1_platform_reward,phase_1_rearing,"Reliable platform-port alternation",52
2025-03-23 10:15:42,20250323_101500,warm_up,phase_2_cue_no_punish,"Warm-up complete",12
2025-03-23 10:45:30,20250323_101500,phase_2_cue_no_punish,phase_2_cue_with_punish,"Evidence of understanding cue",35
```

Each row records when and why a transition occurred. This provides a complete audit trail of the mouse's training progression.

## API reference

### Loading state

```python
from autotraining.persistence import load_training_state

state = load_training_state(
    progress_root="D:\\behaviour_data\\cohort\\autotraining_progress",
    mouse_id="M001",
    default_stage="phase_1_platform_reward",
)

print(state.current_stage)      # "phase_3_two_ports"
print(state.trials_in_stage)    # 150
```

If no state file exists (first session for this mouse), a fresh `TrainingState` is returned with `current_stage` set to `default_stage`.

### Saving state

```python
from autotraining.persistence import save_training_state

save_training_state(
    progress_root="D:\\behaviour_data\\cohort\\autotraining_progress",
    mouse_id="M001",
    current_stage=end_state["current_stage"],
    trials_in_stage=end_state["trials_in_stage"],
    previous_state=saved_state,
    transition_log=engine.get_transition_log(),
)
```

The function replays the transition log to update the stage history, so all stages visited during the session appear in the history (not just the start and end).

### Appending to the transition log

```python
from autotraining.persistence import append_transition_log

append_transition_log(
    progress_root="D:\\behaviour_data\\cohort\\autotraining_progress",
    mouse_id="M001",
    session_id="20250325_140000",
    transitions=engine.get_transition_log(),
)
```

Appends transitions to `training_log.csv`. Creates the file with headers if it doesn't exist.

## Warm-up and persistence

If a session ends while the mouse is still in the warm-up stage, the training state is **not updated**. This prevents the warm-up from counting as real training progress. The mouse will resume at the same saved stage in the next session.

```python
end_state = engine.get_session_end_state()
if not end_state.get("in_warmup", False):
    save_training_state(...)
else:
    log("Session ended during warm-up — training state NOT updated")
```

## Manual overrides

The autotraining protocols provide parameters for manually overriding the saved state:

- **Skip Warm-Up** -- Boolean parameter to skip the warm-up stage entirely
- **Override Start Stage** -- String parameter to force-start at a specific stage (blank = use saved state)
- **Progress Folder Override** -- String parameter to use a different progress folder

These are useful for:

- Resetting a mouse to an earlier stage after equipment issues
- Testing specific stages during development
- Separating training progress for different experimental groups
