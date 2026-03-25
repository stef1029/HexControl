# Installation

## 1. Clone the repository

```bash
git clone https://github.com/your-org/hex_behav_control.git
cd hex_behav_control
```

## 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

## 3. Install in editable mode

```bash
pip install -e .
```

This installs the main package along with all three peripheral libraries (BehavLink, DAQLink, ScalesLink) as local editable dependencies. The core dependencies are:

| Package | Purpose |
|---------|---------|
| `pyserial >= 3.5` | Serial communication with Arduino boards |
| `pyyaml >= 6.0` | Configuration file parsing |
| `behavlink` | Arduino behaviour board communication (local) |
| `daqlink` | Data acquisition subprocess management (local) |
| `scaleslink` | Weight measurement server/client (local) |

The build system uses [Hatchling](https://hatch.pypa.io/).

## 4. Verify the installation

```bash
cd behaviour_rig_system
python main.py
```

You should see the launcher window appear. If running without hardware, check the **Simulate** checkbox to test with virtual rigs.

!!! note
    The first time you run, you'll need to configure the paths in `main.py` to point to your `rigs.yaml` and `board_registry.json` files. See [Configuration](configuration.md) for details.

## Arduino firmware

Each rig requires three Arduino boards, each flashed with the corresponding hex behav Arduino project:

- **Behaviour Arduino (Giga R1)** -- Flash with the hex behav behaviour Arduino project. Handles LEDs, valves, sensors, speaker, and GPIO
- **DAQ Arduino (Mega 2560)** -- Flash with the hex behav DAQ Arduino project. Records rig state as binary events
- **Scales Arduino (Mega 2560)** -- Flash with the hex behav scales Arduino project. Reads the load cell and streams weight data

Ensure the correct project is flashed to the correct board before connecting to the rig system.

On Linux, you may also need to add your user to the `dialout` group for serial access:

```bash
sudo usermod -aG dialout $USER
# Log out and back in for the change to take effect
```

## Project layout

After installation, the key directories are:

```
hex_behav_control/
├── behaviour_rig_system/       # Main application (run from here)
│   ├── main.py                 # Entry point -- edit CONFIG_PATH here
│   ├── core/                   # Business logic
│   ├── protocols/              # Your experiment protocols
│   ├── autotraining/           # Stage progression engine
│   ├── gui/                    # GUI code
│   └── config/                 # Template configs
├── BehavLink/                  # Behaviour Arduino serial library
├── DAQLink/                    # DAQ recording library
├── ScalesLink/                 # Scales measurement library
└── pyproject.toml              # Package definition
```
