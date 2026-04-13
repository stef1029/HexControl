# Simulation Mode

Simulation mode lets you run protocols without physical hardware. This is useful for:

- Testing new protocols before deploying to real rigs
- Debugging protocol logic
- Training new users on the GUI
- Developing and testing autotraining stage definitions

## Enabling simulation

In the sidebar **Tools** panel, click the **Mock Rig** button. Each click opens a new simulated rig panel (Mock Rig 1, Mock Rig 2, etc.) using virtual hardware instead of connecting to real Arduinos.

## What gets simulated

### Virtual rig (SimulatedRig)

A drop-in replacement for `BehaviourRigLink` that:

- Accepts all hardware commands (LED, valve, spotlight, buzzer, speaker, GPIO)
- Tracks the state of all hardware outputs in a `VirtualRigState` object
- Can be set to **interactive mode** (manual events) or **passive mode** (no automatic events)

### Mock serial (MockSerial)

Replaces `pyserial` with a no-op stub. No serial ports are opened or required.

### Simulated mouse (SimulatedMouse)

An optional component that runs on a background thread and autonomously interacts with the virtual rig:

- Detects when LEDs turn on (simulating the mouse seeing a cue)
- Generates sensor events after a configurable reaction time
- Can be tuned with `MouseParameters` to model different performance levels (accuracy, reaction time, timeout probability)

### Behaviour clock (BehaviourClock)

A virtual clock that can run faster than real time. When set to 5x speed, a 10-second wait completes in 2 seconds. Protocols use `self.sleep()` and `self.now()` which automatically respect the clock.

This allows you to run through a full session of hundreds of trials in minutes rather than hours.

### Virtual rig window

When a mock session is started, a **Virtual Rig Window** opens as a floating DPG panel within the viewport. It displays:

- Interactive hex rig schematic with clickable nose-poke ports
- Platform weight slider and quick-toggle mouse button
- GPIO pin toggles for simulating external inputs
- DAQ link pin status indicators
- Real-time visual feedback for LEDs, spotlights, valves, speaker, and IR state

The virtual rig window is automatically closed when the session ends.

## Simulated peripherals

- **DAQ** — No DAQ subprocess is started. Data acquisition is skipped
- **Camera** — No camera executable is launched
- **Scales** — Weight readings return simulated values. If a simulated mouse is active, weight changes reflect virtual platform occupation

## Multiple mock rigs

You can open multiple mock rigs simultaneously. Each opens as a separate panel in the main content area, side by side with any other open rigs. This is useful for testing multi-rig workflows and verifying that mouse claims work correctly across rigs.

## Using simulation for protocol development

A typical workflow for developing a new protocol:

1. Write your protocol class (see [Writing Protocols](../user-guide/protocols/index.md))
2. Click **Mock Rig** in the Tools sidebar panel
3. Select your protocol from the dropdown and configure parameters
4. Optionally enable the simulated mouse and accelerated time (BehaviourClock)
5. Start the session and check the trial log and performance statistics
6. Iterate on parameters and logic
7. Deploy to a real rig once the protocol behaves correctly

!!! tip
    Simulation mode is also useful for testing autotraining stage definitions. You can run through the full training sequence in minutes to verify that transitions fire correctly and the stage progression makes sense.
