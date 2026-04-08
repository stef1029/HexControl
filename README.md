# Hex Behaviour Control

Behaviour rig control system for the hex maze, with peripheral libraries:

- **BehavLink** — protocol for the behaviour rig microcontroller (LEDs, valves, sensors, GPIO)
- **DAQLink** — DAQ board interface for high-rate data acquisition
- **ScalesLink** — interface to the platform weighing scales

The three sub-packages live as a uv workspace inside this repo and are
installed editable, so you can edit them directly.

## Quick start

### 1. Install uv

[uv](https://docs.astral.sh/uv/) is a fast Python package and project manager.
It replaces pip + venv + pyenv.

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and sync

```bash
git clone https://github.com/<you>/hex_behav.git
cd hex_behav/hex_behav_control
uv sync
```

That's it. `uv sync` will:

- Download Python 3.10 if you don't have it (the version is pinned in `.python-version`)
- Create a `.venv/` in this directory
- Install all runtime + dev dependencies from `uv.lock`
- Install `BehavLink`, `DAQLink`, `ScalesLink`, and `hex-behav-control` as editable workspace members

### 3. Run the system

```bash
uv run python behaviour_rig_system/main.py
```

`uv run` activates the venv automatically for the duration of the command.

If you'd rather activate the venv yourself:

```bash
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

python behaviour_rig_system/main.py
```

## Hardware configuration

The rig system needs to know about your hardware. Edit:

- `behaviour_rig_system/config/rigs_template.yaml` — describes each rig and its peripherals
- `behaviour_rig_system/config/board_registry.json` — maps device serial numbers to roles

## Development

### Editing the sub-packages

`BehavLink/`, `DAQLink/`, and `ScalesLink/` are installed editable — edit the
source under `BehavLink/src/...` etc., and changes take effect immediately
without reinstalling.

### Adding a dependency

```bash
uv add numpy                    # runtime dep
uv add --group dev pytest-cov   # dev-only
uv add --group docs mkdocs-foo  # docs-only
```

These commands update `pyproject.toml` and `uv.lock` and install into `.venv`.

### Updating dependencies

```bash
uv sync             # bring .venv in line with the lockfile (fast, idempotent)
uv lock --upgrade   # bump everything to the latest allowed versions
```

### Running tests

```bash
uv run pytest
```

### Building docs

```bash
uv sync --group docs
uv run mkdocs serve
```

## Alternative install (without uv)

If you can't use uv — e.g. you need to install into an existing conda env —
you can fall back to plain pip:

```bash
pip install -e ./BehavLink -e ./DAQLink -e ./ScalesLink -e .
```

You won't get the locked dependency versions from `uv.lock`, only the version
ranges declared in each `pyproject.toml`. Otherwise it's equivalent.

## Project layout

```
hex_behav_control/
├── pyproject.toml          # workspace root
├── uv.lock                 # locked deps (commit this)
├── .python-version         # pinned Python version (commit this)
├── behaviour_rig_system/   # main application
├── BehavLink/              # workspace member
├── DAQLink/                # workspace member
├── ScalesLink/             # workspace member
└── docs/                   # mkdocs source
```
