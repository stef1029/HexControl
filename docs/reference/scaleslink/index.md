# ScalesLink

ScalesLink provides weight measurement from load cells connected to behavioural rigs. It supports both wired and wireless scale configurations through a TCP client-server architecture that isolates blocking serial reads from the GUI.

## Key features

- **Wired and wireless** scale protocols with automatic parsing
- **Linear calibration** with per-scale scale/intercept values
- **TCP client-server** architecture for subprocess isolation
- **Background reading** thread for non-blocking weight access
- **CSV logging** of all readings with timestamps
- **Calibration utility** for two-point calibration procedure

## Guides

- [Quick Start](quickstart.md) -- Direct and subprocess usage examples
- [Wired vs Wireless](wired-wireless.md) -- Protocol differences between scale types
- [Calibration](calibration.md) -- Two-point calibration procedure and zeroing utilities
- [Client-Server Architecture](client-server.md) -- TCP server, client, and manager
