# First Session

This walkthrough covers running a complete experiment session from launch to results.

## 1. Launch the system

```bash
cd behaviour_rig_system
python main.py
```

The **Launcher** window appears showing all configured rigs. Each rig displays its name, connection status, and controls.

## 2. Select a rig

In the Launcher:

- **Test Connection** -- Click to verify the behaviour Arduino is connected and responding. The system resolves the board name to a COM port, opens the serial connection, resets the Arduino via DTR, and performs a handshake (HELLO/HELLO_ACK)
- **Simulate** -- Check this box to run without physical hardware (useful for testing protocols)
- **Link Sessions** -- When opening multiple rigs, check this to group their session data in a shared parent folder

Click **Open** on the rig you want to use. This opens the **Rig Window**.

## 3. Configure the session (Setup Mode)

The Rig Window starts in **Setup Mode** with these controls:

### Save location
Select a cohort folder from the dropdown. This is where all session data will be saved. Folders are defined in `rigs.yaml` under `cohort_folders`.

### Mouse ID
Select the mouse from the dropdown. Mouse IDs are defined in `rigs.yaml` under `mice`.

### Protocol selection
Each available protocol appears as a tab. The system automatically discovers all protocols in the `protocols/` folder. Select the tab for the protocol you want to run.

Each protocol tab shows:

- **Description** -- What the protocol does
- **Parameter form** -- Configurable settings with defaults, validation, and tooltips. Parameters are auto-generated from the protocol's `get_parameters()` definition
- **Reset to Defaults** -- Restore all parameters to their default values

### Common protocols

| Protocol | Description |
|----------|-------------|
| Full Task with Wait | Complete behavioural task: mouse waits on platform, responds to visual/audio cue at one of 6 ports |
| Autotraining (Audio) | Adaptive protocol that progresses through training stages based on performance, using audio cues |
| Autotraining (Visual) | Same as audio autotraining but with visual cues only |
| Hardware Test | Diagnostic protocol for testing rig components |
| Scales Training | Simple platform-reward association training |

## 4. Start the session

Click **Start**. The system validates all parameters and begins the **startup sequence**:

1. Creates the session folder (timestamped, inside the selected cohort folder)
2. Starts the DAQ subprocess and waits for it to connect to the DAQ Arduino
3. Starts the camera executable
4. Starts the scales server subprocess
5. Opens the serial port to the behaviour Arduino
6. Resets the Arduino via DTR and performs the HELLO handshake
7. Writes session metadata (mouse ID, protocol, parameters) to a JSON file
8. Creates the protocol instance and performance trackers

A **Startup Overlay** shows progress messages during this sequence. If anything fails, an error message is displayed and the session is cancelled.

## 5. Monitor the session (Running Mode)

Once startup completes, the window switches to **Running Mode**:

### Session summary
Shows the protocol name, mouse ID, save path, and elapsed time (updating every second).

### Performance display
Real-time statistics for each performance tracker:

- **Accuracy** -- Percentage of correct responses (excluding timeouts)
- **Rolling accuracy** -- Accuracy over the last 10 and 20 trials
- **Trial counts** -- Successes, failures, and timeouts
- **Trials per minute** -- Current trial rate

If the protocol declares multiple trackers (e.g. one per autotraining stage), each gets its own tab.

### Trial log
A scrolling log of trial outcomes, stage transitions, and protocol messages.

### Scales plot
Live weight reading from the platform scales (matplotlib plot embedded in the GUI).

### Stopping
Click **Stop** to end the session. The protocol's `check_stop()` method returns `True`, allowing it to exit gracefully. The protocol's `_cleanup()` method always runs, even on stop.

## 6. Review results (Post-Session Mode)

After the protocol finishes (or is stopped), the system:

1. Gathers performance reports from all trackers
2. Saves merged trial data as CSV to the session folder
3. Shuts down the behaviour Arduino connection
4. Stops the DAQ, camera, and scales subprocesses
5. Displays the **Post-Session Mode**

The results screen shows:

- **Session status** -- Completed, Stopped, or Error
- **Elapsed time**
- **Save path** -- Click to navigate to the session folder
- **Performance report** -- Final accuracy, trial counts, timeout rate, trials per minute, rolling accuracies

Click **New Session** to return to Setup Mode for another session.

## Session output files

Each session creates a timestamped folder containing:

```
YYMMDD_HHMMSS_MouseID/
├── YYMMDD_HHMMSS_MouseID-metadata.json    # Session configuration
├── YYMMDD_HHMMSS_MouseID-trials.csv       # Trial-by-trial data
├── YYMMDD_HHMMSS_MouseID-ArduinoDAQ.h5    # DAQ recording (HDF5)
└── (camera output files)
```

### Metadata JSON

Contains the full session configuration: mouse ID, protocol name, all parameter values, rig info, peripheral settings, and start timestamp.

### Trials CSV

One row per trial with columns:

| Column | Description |
|--------|-------------|
| `tracker` | Which performance tracker recorded this trial |
| `trial_number` | Global trial number (chronological order) |
| `outcome` | `success`, `failure`, or `timeout` |
| `time_since_start_s` | Seconds since session start |
| `trial_duration_s` | Duration of this trial |
| `correct_port` | The correct port for this trial |
| `chosen_port` | The port the mouse chose (empty for timeouts) |
| `timestamp` | Unix timestamp |
