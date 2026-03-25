# Threading Model

The system uses multiple threads to keep the GUI responsive while running blocking operations. This page documents every thread, why it exists, and how they communicate safely.

## Thread inventory

```mermaid
graph TB
    subgraph Main["Main Thread (tkinter)"]
        GUI[GUI Event Loop]
    end

    subgraph Background["Background Threads"]
        ST[Startup Thread]
        PT[Protocol Thread]
        CT[Cleanup Thread]
        RT[BehavLink Receiver]
        SR[Scales Reader]
    end

    subgraph Subprocesses["Subprocesses"]
        DAQ[DAQ Process]
        CAM[Camera Process]
        SS[Scales Server]
    end

    GUI -.->|root.after| ST
    GUI -.->|root.after| PT
    GUI -.->|root.after| CT
    RT -->|event buffer| PT
```

### Main thread

**Owner:** tkinter event loop

**Responsibilities:**

- All GUI rendering and widget updates
- User input handling
- Event dispatch from `root.after()` callbacks

**Rule:** No blocking operations. No serial I/O. No subprocess management. Everything that blocks goes on a background thread.

### Startup thread

**Created by:** `SessionController.start_session()`

**Lifetime:** From Start button click to startup complete/error

**Does:**

- Opens serial ports
- Resets Arduino via DTR
- Launches DAQ, camera, scales subprocesses
- Performs BehavLink handshake
- Creates protocol and tracker instances

**Communicates via:** `_emit("startup_status")`, `_emit("startup_complete")`, `_emit("startup_error")`

### Protocol thread

**Created by:** `SessionController.run_protocol()`

**Lifetime:** From startup complete to protocol finish

**Does:**

- Executes `protocol.run()` (`_setup` -> `_run_protocol` -> `_cleanup`)
- All trial logic, hardware commands, and performance recording

**Communicates via:** `protocol._emit("log")`, `tracker._emit("update")`, `tracker._emit("stimulus")`

### Cleanup thread

**Created by:** `SessionController` after protocol completes

**Lifetime:** Brief -- shutdown sequence only

**Does:**

- Sends `shutdown()` to BehaviourRigLink
- Closes serial port
- Stops PeripheralManager (DAQ, camera, scales)

**Communicates via:** `_emit("cleanup_log")`, `_emit("cleanup_complete")`

### BehavLink receiver thread

**Created by:** `BehaviourRigLink.start()`

**Lifetime:** From link start to link stop

**Does:**

- Continuously reads frames from the serial port
- Parses incoming messages (ACKs, sensor events, GPIO events)
- Places ACKs in a threading queue for command retry logic
- Places events in deque buffers for `wait_for_event()` to consume
- Uses `threading.Condition` to wake `wait_for_event()` when events arrive

**Named:** `"BehaviourRigReceiver"` (daemon thread)

### Scales reader thread

**Created by:** `Scales.start()` (inside the ScalesServer subprocess)

**Lifetime:** While scales are active

**Does:**

- Continuously reads from the serial port
- Parses wired/wireless messages
- Updates the cached weight value (thread-safe via lock)

## Thread safety mechanisms

### `root.after(0, fn)` -- GUI marshalling

All controller events fire on background threads. The RigWindow wraps callbacks to schedule them on the main thread:

```python
self.root.after(0, lambda: self._on_protocol_log(message=msg))
```

This is the **single marshalling point** for all cross-thread GUI updates.

### Threading locks

| Lock | Location | Protects |
|------|----------|----------|
| Event buffer lock | BehaviourRigLink | Sensor/GPIO event deques |
| ACK queue lock | BehaviourRigLink | Command acknowledgement tracking |
| Weight lock | Scales | Cached weight value |
| State lock | VirtualRigState | All simulated hardware state |
| Dirty flag | VirtualRigState | Snapshot change tracking |

### Threading conditions

| Condition | Location | Purpose |
|-----------|----------|---------|
| Event condition | BehaviourRigLink | Wakes `wait_for_event()` when event arrives |
| Sensor inject condition | VirtualRigState | Wakes SimulatedRig when GUI injects events |
| Cue event | VirtualRigState | Wakes SimulatedMouse when LED/buzzer activates |

### Event deques

Sensor and GPIO events are stored in `collections.deque` with `maxlen=1024`. This provides:

- Thread-safe append/pop (CPython GIL)
- Bounded memory usage
- Automatic eviction of oldest events when full

## Subprocess isolation

Three components run as separate **processes** (not threads):

| Process | Manager | Communication |
|---------|---------|---------------|
| DAQ acquisition | `DAQManager` | Signal files (filesystem) |
| Camera recording | `CameraManager` | Signal files + subprocess args |
| Scales server | `ScalesManager` | TCP sockets |

Subprocess isolation prevents:

- Serial port blocking from affecting the GUI
- Crashes in one component from bringing down the whole system
- GIL contention with CPU-intensive tasks

## Typical thread timeline

```
Time →

Main thread:    [Setup GUI] [Overlay] [Running Mode........] [Post Mode]
Startup thread: ............[startup]
Protocol thread:........................[_run_protocol........]
Cleanup thread: ................................................[cleanup]
Receiver thread:...........[serial read loop...........................]
```

The startup, protocol, and cleanup threads run sequentially (never overlapping). The receiver thread runs in parallel with all of them.
