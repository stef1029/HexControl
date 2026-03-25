# BehavLink

BehavLink is a serial communication library for controlling Arduino-based behaviour rigs. It provides a reliable binary protocol with CRC16 checksums, sequence-numbered commands with automatic retry, and asynchronous event handling for IR sensor triggers.

## Hardware capabilities

The behaviour rig has 6 reward ports. Each port has:

| Component | Control | Range |
|-----------|---------|-------|
| LED | Software PWM brightness | 0-255 |
| Spotlight | Hardware PWM (flicker-free) | 0-255 |
| IR sensor | Debounced beam-break detection | Activation/deactivation events |
| Solenoid valve | Timed pulse | 1-65535 ms |
| Buzzer | On/off | True/False |

Plus shared components:

| Component | Control |
|-----------|---------|
| Overhead I2C speaker | Preset frequencies (1-7 kHz) and durations |
| IR illuminator | Hardware PWM brightness (0-255) |
| 6 GPIO pins | Configurable as input (with events) or output |

## Guides

- [Quick Start](quickstart.md) -- Standalone usage example
- [Command Reference](commands.md) -- All hardware commands with signatures and examples
- [Events & Sensors](events.md) -- Sensor and GPIO event system
- [Simulation](simulation.md) -- SimulatedRig, VirtualRigState, MockSerial for testing
