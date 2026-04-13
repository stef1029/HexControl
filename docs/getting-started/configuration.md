# Configuration

The system uses two configuration files:

1. **`rigs.yaml`** -- Defines your rigs, mice, cohort folders, and external processes
2. **`board_registry.json`** -- Maps human-readable board names to USB device identifiers

Both files live in `hexcontrol/config/`. A template (`rigs_template.yaml`) is provided as a starting point.

## Setting config paths

Edit `hexcontrol/main.py` to point to your config files:

```python
CONFIG_PATH = Path(r"C:\path\to\your\rigs.yaml")
BOARD_REGISTRY_PATH = Path(r"C:\path\to\your\board_registry.json")
```

!!! tip
    Keep your actual config files outside the repository (e.g. `C:\Dev\projects\rigs.yaml`) so they aren't overwritten by git pulls. The template files in `config/` are reference examples.

---

## Rig configuration (rigs.yaml)

### Rig definitions

Each rig entry defines the hardware and settings for one physical rig:

```yaml
rigs:
  - name: "Rig 1"                        # Display name (must end in a number)
    board_name: "rig_1_behaviour"         # Key in board_registry.json
    board_type: "giga"                    # "giga" or "mega"
    enabled: true                         # Whether this rig appears in the launcher
    description: "Main behaviour rig"     # Optional description
    camera_serial: "24243513"             # Camera serial number
    daq_board_name: "rig_1_daq"           # DAQ Arduino board key
    scales:
      board_name: "rig_1_scales"          # Scales Arduino board key
      baud_rate: 115200
      is_wired: true                      # true for wired, false for wireless
      calibration_scale: 0.22375          # Calibration scale factor
      calibration_intercept: -5617.39     # Calibration intercept
    reward_durations: [500, 500, 500, 500, 500, 500]  # Per-port reward (ms)
```

Key points:

- **`board_name`** references a key in `board_registry.json` -- COM ports are resolved at runtime, never hardcoded
- **`board_type`** is `"giga"` for Arduino Giga R1 or `"mega"` for Arduino Mega 2560
- **`reward_durations`** is a list of 6 integers (one per port) specifying the solenoid pulse duration in milliseconds. Calibrate per solenoid to deliver consistent reward volumes
- **`scales.calibration_scale`** and **`scales.calibration_intercept`** are determined by the [calibration procedure](../reference/scaleslink/calibration.md)

### Global settings

```yaml
global:
  baud_rate: 115200          # Default baud rate for serial connections
  reset_on_connect: true     # Reset Arduino via DTR on connection
  log_level: "INFO"          # DEBUG, INFO, WARNING, or ERROR
  palette: "dark_red"        # GUI colour palette (see below)
```

#### Palette selection

The `palette` key sets the colour theme for the entire GUI. Available palettes:

| Name | Description |
|------|-------------|
| `light` | Modern blue, light background |
| `dark` | Dark theme for long sessions |
| `dark_green` | Hacker green / Matrix style |
| `dark_red` | Cyberpunk danger style |
| `dark_bw` | Clean monochrome (black & white) |
| `dark_magenta` | Magenta glow theme |
| `light_pink` | Soft pink tones |
| `boring` | Professional, no fun |

If the name does not match any palette, the system prints a warning listing the available names and falls back to `boring`.

### Cohort folders

Define save locations that appear in the GUI dropdown:

```yaml
cohort_folders:
  - name: "Test output"
    directory: "D:\\behaviour_data\\default"
    description: "Default folder for testing"
  - name: "March 2025 cohort"
    directory: "D:\\behaviour_data\\cohort_2025_03"
    description: "March 2025 training cohort"
```

Sessions are saved to the selected cohort folder. Each session gets its own timestamped subfolder containing metadata, trial data, DAQ recordings, and camera output.

### Mouse IDs

Define the mice available for selection in the GUI:

```yaml
mice:
  - id: "M001"
    description: "Photometry"
  - id: "M002"
    description: "Electrophysiology"
  - id: "M003"
    description: ""
```

### External processes

Configure paths to external executables and timeouts:

```yaml
processes:
  camera_executable: "C:\\path\\to\\Camera_to_binary.exe"
  connection_timeout: 30        # Seconds to wait for DAQ connection
  camera_fps: 30
  camera_window_width: 640
  camera_window_height: 512
```

---

## Board registry (board_registry.json)

The board registry maps human-readable board names to USB device identifiers. This allows rigs to be defined by name rather than COM port, so configs don't break when ports change.

```json
{
  "boards": {
    "rig_1_behaviour": {
      "description": "Rig 1 Behaviour Arduino Giga",
      "vid": "0x2341",
      "pid": "0x0266",
      "serial_number": "ABC123DEF456",
      "baudrate": 115200
    },
    "rig_1_daq": {
      "description": "Rig 1 DAQ Arduino",
      "vid": "0x2341",
      "pid": "0x0042",
      "serial_number": "DEF789GHI012",
      "baudrate": 115200
    },
    "rig_1_scales": {
      "description": "Rig 1 Scales Arduino",
      "vid": "0x2341",
      "pid": "0x0042",
      "serial_number": "GHI345JKL678",
      "baudrate": 115200
    }
  }
}
```

Each entry contains:

| Field | Description |
|-------|-------------|
| `description` | Human-readable description |
| `vid` | USB Vendor ID (hex string) |
| `pid` | USB Product ID (hex string) |
| `serial_number` | USB serial number (unique per device) |
| `baudrate` | Communication baud rate |

### Discovering board serial numbers

To find the serial numbers of your connected Arduino boards, run the board registry discovery tool:

```bash
cd hexcontrol
python -m core.board_registry
```

This scans all connected USB serial devices and prints their VID, PID, and serial number in a format you can copy directly into `board_registry.json`.

---

## Adding a new rig

1. Flash each Arduino with the appropriate hex behav Arduino project (behaviour, DAQ, scales), connect them, and run the discovery tool to get their serial numbers
2. Add entries to `board_registry.json` with keys like `rig_N_behaviour`, `rig_N_daq`, `rig_N_scales`
3. Add a rig entry to `rigs.yaml` referencing those board names
4. Run the scales [calibration procedure](../reference/scaleslink/calibration.md) and update the `calibration_scale` and `calibration_intercept` values
5. Calibrate each solenoid and set the `reward_durations` values
6. Launch the system, select the new rig in the launcher, and use **Launch Selected** to verify it connects correctly
