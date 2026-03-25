# Performance Trackers

Performance trackers record trial outcomes (success, failure, timeout) and provide real-time statistics. The GUI displays tracker data during sessions and includes it in the post-session report.

## Declaring trackers

Protocols declare their trackers by overriding `get_tracker_definitions()`:

```python
from core.performance_tracker import TrackerDefinition

class MyProtocol(BaseProtocol):
    @classmethod
    def get_tracker_definitions(cls) -> list:
        return [
            TrackerDefinition(name="trials", display_name="Trials"),
        ]
```

Each `TrackerDefinition` has:

- **`name`** -- Internal key, used to access the tracker via `self.perf_trackers["trials"]`
- **`display_name`** -- Label shown in the GUI

If `get_tracker_definitions()` returns an empty list (the default), no trackers are created and the GUI shows a placeholder message.

### Multiple trackers

Protocols can declare multiple trackers. This is common in autotraining protocols where each training stage gets its own tracker:

```python
@classmethod
def get_tracker_definitions(cls) -> list:
    return [
        TrackerDefinition(name="easy", display_name="Easy Trials"),
        TrackerDefinition(name="hard", display_name="Hard Trials"),
    ]
```

Each tracker gets its own tab in the GUI's Running Mode.

## Recording outcomes

Access trackers in `_run_protocol()` via `self.perf_trackers`:

```python
def _run_protocol(self) -> None:
    tracker = self.perf_trackers.get("trials")
    if tracker is not None:
        tracker.reset()  # Initialise timing

    for trial in range(num_trials):
        if self.check_stop():
            return

        # Signal which port is the target (for display only)
        tracker.stimulus(target_port)

        # ... run trial logic ...

        if mouse_chose_correct_port:
            tracker.success(
                correct_port=target_port,
                trial_duration=elapsed,
            )
        elif mouse_chose_wrong_port:
            tracker.failure(
                correct_port=target_port,
                chosen_port=event.port,
                trial_duration=elapsed,
            )
        else:  # no response
            tracker.timeout(
                correct_port=target_port,
                trial_duration=elapsed,
            )
```

### Outcome methods

All three methods share the same signature pattern:

| Method | Parameters | Description |
|--------|-----------|-------------|
| `tracker.success(correct_port, trial_duration, **details)` | `correct_port`: the correct port (which the mouse chose) | Record a correct response |
| `tracker.failure(correct_port, chosen_port, trial_duration, **details)` | `correct_port`: correct answer, `chosen_port`: what the mouse picked | Record an incorrect response |
| `tracker.timeout(correct_port, trial_duration, **details)` | `correct_port`: the port the mouse should have chosen | Record no response within the timeout window |

- `trial_duration` is in seconds
- `**details` accepts arbitrary keyword arguments stored in the trial record (useful for custom data)

### `stimulus(target_port)`

Call this when a stimulus is presented (before waiting for a response). It fires a `"stimulus"` event that the GUI uses to show a marker. This is for display only -- it does not create a trial record.

### `reset()`

Call `tracker.reset()` at the start of your protocol to clear any leftover state and initialise the session start time. This is important for accurate `time_since_start` values in trial records.

## Statistics

The tracker provides these properties and methods:

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `total_trials` | `int` | Total trials recorded |
| `successes` | `int` | Number of successful trials |
| `failures` | `int` | Number of failed trials |
| `timeouts` | `int` | Number of timeout trials |
| `responses` | `int` | Trials with a response (`successes + failures`) |
| `accuracy` | `float` | `successes / responses * 100` (0-100, timeouts excluded) |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `rolling_accuracy(n=20)` | `float` | Accuracy over the last `n` non-timeout trials |
| `rolling_stats(n=20)` | `dict` | Detailed stats for the last `n` trials (includes timeouts) |
| `get_summary()` | `str` | One-line summary (e.g. `"45/50 correct (90%) \| 5 timeouts \| Last 20: 95%"`) |
| `get_report()` | `dict` | Full session report with all statistics |
| `get_trials()` | `list[TrialRecord]` | All trial records |
| `get_trials_since(index)` | `list[TrialRecord]` | Trial records from the given index onwards |

### Trial records

Each recorded trial is a `TrialRecord` dataclass:

```python
@dataclass
class TrialRecord:
    trial_number: int                # Sequential trial number
    outcome: TrialOutcome            # SUCCESS, FAILURE, or TIMEOUT
    timestamp: float                 # Unix timestamp
    time_since_start: float          # Seconds since tracker.reset()
    correct_port: int | None         # The correct port
    chosen_port: int | None          # The port the mouse chose (None for timeout)
    trial_duration: float            # Duration in seconds
    details: dict                    # Extra data from **details kwargs
```

## Saving trial data

At session end, the system automatically calls `save_merged_trials()` which:

1. Collects trials from all trackers
2. Sorts them chronologically
3. Saves a single CSV file with a `tracker` column identifying which tracker recorded each trial

You don't need to call this manually -- the session controller handles it.

## Events

Trackers emit two events that the GUI subscribes to:

- `"update"` -- Fired after each outcome is recorded (triggers GUI stats update)
- `"stimulus"` -- Fired when `stimulus()` is called (triggers GUI marker)

These are wired automatically by the session controller.
