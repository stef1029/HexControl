# Session Lifecycle

The `SessionController` manages the complete lifecycle of an experiment session through a state machine.

## Session states

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> STARTING: start_session()
    STARTING --> RUNNING: startup_complete
    STARTING --> IDLE: startup_error / cancel
    RUNNING --> STOPPING: stop_session()
    RUNNING --> CLEANING_UP: protocol_complete
    STOPPING --> CLEANING_UP: protocol exits
    CLEANING_UP --> CLEANING_UP: finalize_complete
    CLEANING_UP --> COMPLETED: cleanup_complete
    COMPLETED --> IDLE: new_session()
```

The lifecycle is split into four phases. Each phase is its own public method on the controller that spawns one short-lived worker thread, emits a single `*_complete` event when done, and exits. The GUI listens for that event and triggers the next phase by calling the next controller method. This keeps every transition consistent: phase finishes → emit → listener handles GUI → listener calls next phase.

| State | Description | Thread |
|-------|-------------|--------|
| `IDLE` | Setup Mode displayed. Waiting for user to configure and start | Main |
| `STARTING` | Startup sequence running. Overlay shown | Startup worker |
| `RUNNING` | Protocol executing. Running Mode shown | Protocol worker |
| `STOPPING` | Stop requested. Waiting for protocol to check `check_stop()` | Protocol worker |
| `CLEANING_UP` | Building `SessionResult` then shutting down hardware | Finalize worker, then cleanup worker |
| `COMPLETED` | Post-Session Mode shown. Results displayed | Main |

## Startup sequence

When the user clicks Start, `controller.start_session(config)` spawns a background thread that executes:

1. **Create session folder** -- Timestamped subfolder inside the selected cohort directory
2. **Load peripheral config** -- Build `PeripheralConfig` from rig settings
3. **Create BehaviourClock** -- If simulation mode with time acceleration
4. **Create VirtualRigState** -- If simulation mode
5. **Create PeripheralManager** -- Manages DAQ, camera, and scales subprocesses
6. **Start DAQ** -- Launch DAQ subprocess
7. **Wait for DAQ connection** -- Poll for signal file (up to `connection_timeout` seconds)
8. **Start camera** -- Launch camera executable with session arguments
9. **Start scales** -- Launch scales server subprocess, connect client
10. **Open serial port** -- Connect to behaviour Arduino (or create MockSerial for simulation)
11. **Reset Arduino** -- DTR pin toggle + startup wait
12. **Create BehaviourRigLink** -- Or SimulatedRig for simulation
13. **Handshake** -- `send_hello()` / `wait_hello()` with 3-second timeout
14. **Write metadata** -- Save session configuration as JSON
15. **Create protocol instance** -- Instantiate the selected protocol class with parameters
16. **Create performance trackers** -- One per `TrackerDefinition` from the protocol
17. **Wire events** -- Connect protocol and tracker events to controller events
18. **Set runtime context** -- Attach scales, trackers, rig number, clock, reward durations to the protocol
19. **Emit `startup_complete`** -- GUI switches from overlay to Running Mode

If any step fails, the controller emits `startup_error` with the error message and reverts to IDLE.

## Protocol execution

After startup completes, the `_on_startup_complete` listener calls `controller.run_protocol()`, which spawns the protocol worker:

1. Set status to `RUNNING`
2. Call `protocol.run()` which executes:
    - `_setup()` (if overridden)
    - `_run_protocol()` (main experiment loop)
    - `_cleanup()` (always runs, even on error/stop)
3. Capture the final `ProtocolStatus`
4. Emit `protocol_complete` with the final status, then exit

The worker does **not** chain into the next phase itself — it just exits. The GUI listener decides what happens next.

## Stop handling

When the user clicks Stop:

1. `controller.stop_session()` sets status to `STOPPING`
2. `protocol.request_stop()` sets the internal `_stop_requested` flag
3. The protocol checks `self.check_stop()` in its next loop iteration
4. `check_stop()` returns `True`, the protocol returns early
5. `_cleanup()` runs (always)
6. The protocol worker emits `protocol_complete` and exits — the rest of the lifecycle continues from the GUI listener as in the normal path

## Finalize sequence

The `_on_protocol_complete` listener stops the timer + scales plot, sets the final status label, logs "Finalising results...", then calls `controller.finalize_protocol(final_status)`. This spawns the finalize worker:

1. Set status to `CLEANING_UP`
2. Gather performance reports from all trackers
3. Save merged trial data as CSV
4. Build `SessionResult` with status, reports, and an elapsed-time placeholder (the GUI fills this in)
5. Emit `finalize_complete` with the result, then exit

## Cleanup sequence

The `_on_finalize_complete` listener fills in the elapsed time, stashes the result, logs "Cleaning up...", then calls `controller.cleanup_session()`. This spawns the cleanup worker:

1. Send `shutdown()` command to BehaviourRigLink
2. Stop the receive thread (`link.stop()`)
3. Close serial port
4. Stop PeripheralManager (DAQ, camera, scales subprocesses) — emits `cleanup_log` messages along the way
5. Emit `cleanup_complete`, then exit

The `_on_cleanup_complete` listener tears down the simulated mouse and virtual rig window, then schedules the switch to Post-Session Mode after a short delay so the user can read the final cleanup log lines.

## SessionResult

The result object passed to the GUI after protocol completion:

```python
@dataclass
class SessionResult:
    status: str              # "completed", "stopped", or "error"
    elapsed_time: float      # Total session duration in seconds
    save_path: str           # Path to session folder
    performance_reports: dict # {tracker_name: report_dict}
    error_message: str       # Error details (if status == "error")
```

## New session

When the user clicks New Session in Post-Session Mode:

1. `controller.new_session()` resets internal state
2. Status returns to `IDLE`
3. GUI switches to Setup Mode with the previous configuration preserved
