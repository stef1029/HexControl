# Installation

The project is managed with [uv](https://docs.astral.sh/uv/), a fast Python package and project manager. uv handles the Python interpreter, the virtual environment, and all dependencies — including the local editable workspace libraries — in one step.

## 1. Install uv

=== "Windows (PowerShell)"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

See the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for other methods (Homebrew, pipx, etc.).

## 2. Clone the repositories

HexControl depends on the analysis library `hex_behav_analysis`, which lives in a **separate, private repository**. You will need to clone both side by side:

```bash
mkdir hex_behav
cd hex_behav
git clone https://github.com/stef1029/HexControl.git hex_behav_control
git clone https://github.com/stef1029/hex_behav_analysis.git
# Expected layout:
#   hex_behav/
#   ├── hex_behav_control/   (this repo — public)
#   └── hex_behav_analysis/  (private — access required)
```

!!! warning "Private dependency"
    `hex_behav_analysis` is a private repository. You must have been granted access by the repository owner ([@stef1029](https://github.com/stef1029)) before you can clone it. Without it, `uv sync` will fail because the editable path dependency cannot be resolved. If you need access, contact the maintainer.

!!! warning "Sibling directory layout matters"
    The `pyproject.toml` references `hex_behav_analysis` via the relative path `../hex_behav_analysis`. If the two folders are not siblings, `uv sync` will fail. The folder name on disk must be exactly `hex_behav_analysis`.

## 3. Sync the environment

```bash
cd hex_behav_control
uv sync
```

That single command will:

- Download the pinned Python version from `.python-version` (currently **3.10**) if you don't already have it
- Create a `.venv/` inside `hex_behav_control/`
- Install every dependency listed in `uv.lock` at exactly the locked version
- Install the workspace members (`BehavLink`, `DAQLink`, `ScalesLink`) and `hex_behav_analysis` as **editable** installs — edits to their source take effect immediately, with no reinstall

### Dependencies

Everything is in a single dependency list — there are no optional groups, so `uv sync` gives you everything needed to run, develop, test, and build the docs.

| Package | Purpose |
|---------|---------|
| `pyserial` | Serial communication with Arduino boards |
| `pyyaml` | Configuration file parsing |
| `matplotlib` | Live plots and post-session figures |
| `opencv-python` | Camera frame capture and processing |
| `mkdocs`, `mkdocs-material` | Building and previewing this documentation site |
| `pytest` | Test runner |
| `behavlink` (workspace) | Behaviour Arduino communication |
| `daqlink` (workspace) | Data acquisition subprocess management |
| `scaleslink` (workspace) | Weight measurement server/client |
| `hex-behav-analysis` (sibling, editable) | Offline analysis utilities (private repo) |

## 4. Run the system

The simplest way is `uv run`, which activates the venv for the duration of the command:

```bash
uv run python behaviour_rig_system/main.py
```

Or activate the venv yourself and use `python` directly:

=== "Windows"

    ```powershell
    .venv\Scripts\activate
    python behaviour_rig_system/main.py
    ```

=== "macOS / Linux"

    ```bash
    source .venv/bin/activate
    python behaviour_rig_system/main.py
    ```

You should see the launcher window appear. If running without hardware, check the **Simulate** checkbox to test with virtual rigs — see [Simulation Mode](simulation.md).

!!! note "First-run configuration"
    The first time you run, you'll need to point `main.py` at your `rigs.yaml` and `board_registry.json` files. See [Configuration](configuration.md).

## 5. (Optional) Set up VSCode

VSCode auto-discovers `.venv` folders inside the workspace. Open `hex_behav_control/` as the workspace root, then:

1. `Ctrl+Shift+P` → **Python: Select Interpreter**
2. Pick the `.venv` interpreter (labelled something like `Python 3.10.x ('.venv': venv)`)

New terminals opened in VSCode will then auto-activate the venv.

## Working with dependencies

Use uv to add or remove packages — it updates `pyproject.toml`, `uv.lock`, and `.venv` in one step:

```bash
uv add numpy        # add a dep
uv remove pyserial  # remove a dep
uv sync             # bring .venv in line with the lockfile
uv lock --upgrade   # bump everything to latest allowed versions
```

Never hand-edit `uv.lock` — it's generated. Hand-edits to `pyproject.toml` are fine, just run `uv sync` afterwards.

### Building the docs

`mkdocs` and `mkdocs-material` are part of the default install, so you can build the docs site with no extra steps:

```bash
uv run mkdocs serve   # local preview at http://127.0.0.1:8000
uv run mkdocs build   # static site → site/
```

## Alternative install (without uv)

If you can't use uv — for example, you need to install into an existing conda env that has system-level packages you can't replace — fall back to plain pip:

```bash
cd hex_behav_control
pip install -e ./BehavLink -e ./DAQLink -e ./ScalesLink -e ../hex_behav_analysis -e .
```

This is the manual equivalent of what `uv sync` does. You won't get the locked dependency versions from `uv.lock`, only the version ranges declared in `pyproject.toml`. Otherwise it's equivalent.

## Arduino firmware

Each rig requires three Arduino boards, each flashed with the corresponding hex behav Arduino project:

- **Behaviour Arduino (Giga R1)** — Flash with the hex behav behaviour Arduino project. Handles LEDs, valves, sensors, speaker, and GPIO
- **DAQ Arduino (Mega 2560)** — Flash with the hex behav DAQ Arduino project. Records rig state as binary events
- **Scales Arduino (Mega 2560)** — Flash with the hex behav scales Arduino project. Reads the load cell and streams weight data

Ensure the correct project is flashed to the correct board before connecting to the rig system.

On Linux, you may also need to add your user to the `dialout` group for serial access:

```bash
sudo usermod -aG dialout $USER
# Log out and back in for the change to take effect
```

## Project layout

After installation, the key directories are:

```
hex_behav/
├── hex_behav_control/              # ← run uv sync here
│   ├── pyproject.toml              # workspace root, dependencies
│   ├── uv.lock                     # locked dependency versions (committed)
│   ├── .python-version             # pinned Python version (committed)
│   ├── .venv/                      # virtual environment (gitignored)
│   ├── behaviour_rig_system/       # main application
│   │   ├── main.py                 # entry point
│   │   ├── core/                   # business logic
│   │   ├── protocols/              # experiment protocols
│   │   ├── autotraining/           # stage progression engine
│   │   ├── gui/                    # GUI code
│   │   └── config/                 # template configs
│   ├── BehavLink/                  # workspace member — behaviour Arduino library
│   ├── DAQLink/                    # workspace member — DAQ recording library
│   └── ScalesLink/                 # workspace member — scales measurement library
└── hex_behav_analysis/             # sibling repo — offline analysis library
```
