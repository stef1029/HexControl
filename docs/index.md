# Hex Behav Control

A modular behaviour rig control system for running neuroscience experiments on Arduino-based hexagonal rigs. Built with Python and tkinter, designed for training mice on complex behavioural tasks with automatic stage progression, real-time performance monitoring, and multi-rig support.

## What it does

- **Multi-rig control** -- Run up to 4 behaviour rigs simultaneously from a single launcher, each in its own window
- **Protocol system** -- Define experiment protocols as Python classes with configurable parameters, automatic GUI generation, and hardware abstraction
- **Autotraining** -- Automatic stage progression based on mouse performance, with persistent progress tracking across sessions
- **Hardware abstraction** -- Control LEDs, solenoid valves, buzzers, speakers, GPIO, and IR sensors through the BehavLink serial library
- **Data acquisition** -- Parallel DAQ recording via DAQLink, weight measurement via ScalesLink, and camera integration
- **Simulation mode** -- Test protocols without physical hardware using virtual rigs and simulated mice
- **Live monitoring** -- Real-time performance statistics, trial logs, and weight plots during sessions

## Hardware

The system controls a hexagonal behaviour rig with 6 reward ports arranged in a circle. Each port has:

- An LED for visual cues
- A spotlight for illumination/punishment
- An IR sensor for detecting mouse nose-pokes
- A solenoid valve for delivering liquid reward

The rig also includes a central platform with a load cell (scales) for detecting when the mouse mounts, an overhead I2C speaker for audio cues, and an IR illuminator for camera recording.

## Getting started

- **New users**: Start with [Installation](getting-started/installation.md), then [Configuration](getting-started/configuration.md), then [First Session](getting-started/first-session.md)
- **Protocol authors**: Read the [Writing Protocols](user-guide/protocols/index.md) guide and the [Autotraining](user-guide/autotraining/index.md) section
- **Developers**: See the [Architecture](architecture/index.md) section for system internals

## Project structure

```
hex_behav_control/
├── behaviour_rig_system/       # Main application
│   ├── main.py                 # Entry point
│   ├── core/                   # Business logic (no GUI code)
│   ├── protocols/              # Experiment protocol implementations
│   ├── autotraining/           # Stage progression engine
│   ├── gui/                    # tkinter GUI layer
│   ├── config/                 # Configuration files
│   ├── simulation/             # Virtual rig for testing
│   └── post_processing/        # Offline analysis tools
├── BehavLink/                  # Serial communication library
├── DAQLink/                    # Data acquisition library
└── ScalesLink/                 # Weight measurement library
```
