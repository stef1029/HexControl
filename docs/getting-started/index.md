# Getting Started

This section covers everything you need to get the Behaviour Rig System up and running.

## Prerequisites

- **[uv](https://docs.astral.sh/uv/)** -- the project uses uv to manage Python, the virtual environment, and dependencies. uv will install Python 3.10 for you on first sync, so you don't need to install Python yourself.
- **Arduino hardware** -- or use [Simulation Mode](simulation.md) to run without physical rigs
- **Arduino hardware** with the appropriate hex behav Arduino projects flashed to each board (behaviour, DAQ, scales)

## Steps

1. [Installation](installation.md) -- Install uv, clone the repo, and run `uv sync`
2. [Configuration](configuration.md) -- Set up your rig definitions, board registry, cohort folders, and mice
3. [First Session](first-session.md) -- Walk through running your first experiment session end-to-end
4. [Simulation Mode](simulation.md) -- Test protocols without physical hardware
