# GUI Walkthrough

The application has two main windows: the **Launcher** (rig selector) and the **Rig Window** (per-rig control). The Rig Window has three modes that it switches between during a session.

---

## Launcher

The Launcher is the first window you see when running `python main.py`. It displays a clock, a decorative generative-art background (different each launch), and all rigs defined in your `rigs.yaml` configuration. The colour palette is set by the `global.palette` key in your config.

### Rig selection

Rigs are shown as toggle buttons in a 2×2 grid. Click a rig button to select or deselect it. Disabled rigs (`enabled: false` in config) are greyed out and cannot be selected.

### Controls

- **Launch Selected** -- Opens a Rig Window for every selected rig. Each rig gets its own independent window
- **Simulate** -- When checked, launched rigs run in simulation mode (no physical hardware required)
- **Link Sessions** -- When checked, all rigs launched together save their session data under a shared timestamped parent folder. Useful when running multiple rigs with the same cohort

### Utility buttons

- **Zero All Scales** -- Sends a zero/tare command to all configured scales and reports the result
- **Post Processing** -- Opens the post-processing tool for offline analysis of saved sessions (only available when no rig windows are open)
- **Mock Rig** -- Opens a simulated rig window using the first rig's config, without requiring any hardware. Useful for testing protocols
- **Docs** -- Starts a local MkDocs server and opens the documentation in your browser

You can open multiple rigs simultaneously -- each gets its own independent Rig Window. A mouse ID selected in one rig window cannot be selected in another to prevent duplicate assignments.

---

## Rig Window -- Setup Mode

When a Rig Window opens, it starts in **Setup Mode** where you configure the session before starting.

### Save location

A dropdown populated from the `cohort_folders` list in your `rigs.yaml`. Selects where session data will be saved. Each session creates a timestamped subfolder inside the selected directory.

### Mouse ID

A dropdown populated from the `mice` list in your `rigs.yaml`. The selected mouse ID is included in the session folder name and metadata.

### Protocol tabs

Each protocol discovered in the `protocols/` folder gets its own tab. The tab shows:

- **Protocol description** -- From the protocol's `get_description()` method
- **Parameter form** -- Dynamically generated from the protocol's `get_parameters()` method. Each parameter type renders as an appropriate widget:

    | Parameter type | Widget |
    |---------------|--------|
    | `IntParameter` | Spinbox with min/max bounds and step |
    | `FloatParameter` | Spinbox with min/max bounds, step, and precision |
    | `BoolParameter` | Checkbox |
    | `ChoiceParameter` | Dropdown menu |
    | `StringParameter` | Text entry field |

- **Reset to Defaults** -- Restores all parameters to their default values

Parameters are organized by group (defined in the parameter's `group` field) and sorted by `order`.

### Start button

Validates all parameters before starting. If any parameter fails validation (out of range, wrong type), an error message appears next to the offending field and the session won't start.

---

## Rig Window -- Running Mode

Displayed while the protocol is executing. All updates arrive via events from the controller running on a background thread.

### Session summary bar

Shows the protocol name, mouse ID, save directory, and a live elapsed timer that updates every second.

### Performance display

Real-time statistics from the protocol's performance trackers:

- **Accuracy** -- `successes / (successes + failures) * 100%` (timeouts excluded)
- **Rolling accuracy** -- Accuracy over the last 10 and 20 non-timeout trials
- **Counts** -- Total successes, failures, and timeouts
- **Trials per minute** -- Average trial rate

If the protocol declares multiple named trackers (via `get_tracker_definitions()`), each tracker gets its own tab. This is used by autotraining protocols where each training stage has its own tracker. A **Lock** toggle prevents the view from auto-switching when the active stage changes.

### Trial log

A scrolling text pane showing protocol messages (`self.log()` calls), trial outcomes, and stage transitions. New entries appear at the bottom.

### Scales plot

A live matplotlib chart showing weight readings from the platform scales over time. Useful for monitoring mouse activity and verifying platform detection.

### Stop button

Sends a stop request to the protocol. The protocol checks `self.check_stop()` on its next iteration and exits gracefully. The protocol's `_cleanup()` method always runs.

---

## Rig Window -- Post-Session Mode

Displayed after the protocol completes (or is stopped) and hardware cleanup finishes.

### Session summary

- **Status** -- Completed, Stopped, or Error
- **Protocol** and **Mouse ID**
- **Elapsed time** -- Total session duration
- **Save path** -- Where the session data was saved

### Performance report

Final statistics for each tracker: total trials, successes, failures, timeouts, accuracy, timeout rate, trials per minute, and rolling accuracies.

### New Session button

Returns to Setup Mode with the previous configuration preserved, ready for the next session.

---

## Startup Overlay

During the startup sequence (between clicking Start and the protocol beginning), a modal overlay covers the Rig Window showing:

- Progress messages for each startup step (DAQ connection, camera launch, Arduino handshake, etc.)
- A **Cancel** button to abort the startup
- Error messages if any step fails

The overlay disappears automatically when startup completes successfully.
