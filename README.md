# HexControl

Behaviour rig control system for the hex maze, with peripheral libraries:

- **BehavLink** — protocol for the behaviour rig microcontroller (LEDs, valves, sensors, GPIO)
- **DAQLink** — DAQ board interface for high-rate data acquisition
- **ScalesLink** — interface to the platform weighing scales

The three sub-packages live as a uv workspace inside this repo and are
installed editable, so you can edit them directly.

> **Private dependency required.** HexControl depends on
> [`hex_behav_analysis`](https://github.com/stef1029/hex_behav_analysis), which is a
> **private repository**. You must be granted access by the maintainer
> ([@stef1029](https://github.com/stef1029)) before you can install or run the system.
> Without it, `uv sync` will fail.

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

### 2. Clone the repos

Clone HexControl and the private `hex_behav_analysis` library as **siblings** in the same parent folder. The `pyproject.toml` references the analysis library via the relative path `../hex_behav_analysis`, so the layout matters.

```bash
mkdir hex_behav
cd hex_behav
git clone https://github.com/stef1029/HexControl.git hex_behav_control
git clone https://github.com/stef1029/hex_behav_analysis.git
cd hex_behav_control
uv sync
```

That's it. `uv sync` will:

- Download Python 3.10 if you don't have it (the version is pinned in `.python-version`)
- Create a `.venv/` in this directory
- Install every dependency listed in `uv.lock` (everything needed to run, develop, and build the docs — there are no optional groups)
- Install `BehavLink`, `DAQLink`, `ScalesLink`, and `hex-behav-control` as editable workspace members, plus `hex_behav_analysis` as an editable path dependency

### 3. Run the system

```bash
uv run python hexcontrol/main.py
```

`uv run` activates the venv automatically for the duration of the command.

If you'd rather activate the venv yourself:

```bash
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

python hexcontrol/main.py
```

## Hardware configuration

The rig system needs to know about your hardware. Edit:

- `hexcontrol/config/rigs_template.yaml` — describes each rig and its peripherals
- `hexcontrol/config/board_registry.json` — maps device serial numbers to roles

## GUI Overview

The GUI is built with [DearPyGui](https://github.com/hoffstadt/DearPyGui) and uses a VSCode-inspired layout:

- **Activity bar** (left edge) — icon buttons to toggle sidebar panels
- **Sidebar** (left) — Rigs, Tools, Post-Processing, and Docs panels
- **Main content** (center) — rig panels arranged horizontally, auto-scaling to fit
- **Info bar** (bottom) — clock and status text

Multiple rigs can be open simultaneously as side-by-side panels. Each rig panel contains the full session workflow: Setup → Running → Post-Session.

A **Preferences** menu in the menu bar provides UI scaling options (75%–150%).

## Development

### Editing the sub-packages

`BehavLink/`, `DAQLink/`, and `ScalesLink/` are installed editable — edit the
source under `BehavLink/src/...` etc., and changes take effect immediately
without reinstalling.

### Adding a dependency

```bash
uv add numpy        # adds to pyproject.toml, updates uv.lock, installs into .venv
uv remove pyserial  # removes a dep
```

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

`mkdocs` and `mkdocs-material` are installed by default with `uv sync`, so you
can build the docs straight away:

```bash
uv run mkdocs serve   # local preview at http://127.0.0.1:8000
uv run mkdocs build   # static site → site/
```

## Alternative install (without uv)

If you can't use uv — e.g. you need to install into an existing conda env —
you can fall back to plain pip:

```bash
pip install -e ./BehavLink -e ./DAQLink -e ./ScalesLink -e ../hex_behav_analysis -e .
```

You won't get the locked dependency versions from `uv.lock`, only the version
ranges declared in each `pyproject.toml`. Otherwise it's equivalent.

## Project layout

```
hex_behav_control/
├── pyproject.toml          # workspace root
├── uv.lock                 # locked deps (commit this)
├── .python-version         # pinned Python version (commit this)
├── hexcontrol/             # main application
│   ├── main.py             # entry point
│   ├── core/               # business logic (no GUI dependency)
│   ├── gui/                # DearPyGui interface
│   │   ├── app_layout.py   # root layout (activity bar, sidebar, panels)
│   │   ├── rig_window.py   # per-rig view (setup/running/post-session)
│   │   ├── theme.py        # palette system and DPG themes
│   │   ├── fonts/          # bundled TTF fonts
│   │   └── ...
│   ├── protocols/          # behaviour protocol implementations
│   ├── autotraining/       # adaptive training engine
│   └── simulation/         # virtual rig for testing
├── BehavLink/              # workspace member
├── DAQLink/                # workspace member
├── ScalesLink/             # workspace member
└── docs/                   # mkdocs source
```
