"""
Typed rig configuration — the single entry point for all config data.

``RigsFile.load(path)`` reads the YAML once at startup and returns a
frozen object tree. Nothing else in the codebase should open or parse
the YAML file directly. Downstream code receives typed objects:

- ``RigConfig`` — per-rig hardware settings + process settings
- ``CohortFolder`` / ``MouseEntry`` — GUI selection options
- ``GlobalConfig`` — app-wide settings (baud rate, palette, log level)

All dataclasses are frozen after construction — downstream code cannot
accidentally mutate config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass(frozen=True)
class ScalesConfig:
    """Per-rig scales hardware configuration."""
    board_name: str = ""
    baud_rate: int = 115200
    is_wired: bool = True
    calibration_scale: float = 1.0
    calibration_intercept: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> ScalesConfig:
        return cls(
            board_name=data.get("board_name", ""),
            baud_rate=int(data.get("baud_rate", 115200)),
            is_wired=bool(data.get("is_wired", True)),
            calibration_scale=float(data.get("calibration_scale", 1.0)),
            calibration_intercept=float(data.get("calibration_intercept", 0.0)),
        )


@dataclass(frozen=True)
class CohortFolder:
    """A save-directory entry from the config file."""
    name: str
    directory: str
    description: str = ""


@dataclass(frozen=True)
class MouseEntry:
    """A mouse ID entry from the config file."""
    id: str
    description: str = ""
    default_cohort: str = ""


@dataclass(frozen=True)
class ProcessesConfig:
    """External process paths and settings from the config file."""
    camera_executable: str = ""
    connection_timeout: int = 30
    camera_fps: int = 30
    camera_window_width: int = 960
    camera_window_height: int = 768

    @classmethod
    def from_dict(cls, data: dict) -> ProcessesConfig:
        return cls(
            camera_executable=data.get("camera_executable", ""),
            connection_timeout=int(data.get("connection_timeout", 30)),
            camera_fps=int(data.get("camera_fps", 30)),
            camera_window_width=int(data.get("camera_window_width", 960)),
            camera_window_height=int(data.get("camera_window_height", 768)),
        )


@dataclass(frozen=True)
class GlobalConfig:
    """Top-level global settings from the config file."""
    baud_rate: int = 115200
    reset_on_connect: bool = True
    log_level: str = "INFO"
    palette: str = "dark_green"

    @classmethod
    def from_dict(cls, data: dict) -> GlobalConfig:
        return cls(
            baud_rate=int(data.get("baud_rate", 115200)),
            reset_on_connect=bool(data.get("reset_on_connect", True)),
            log_level=str(data.get("log_level", "INFO")),
            palette=str(data.get("palette", "dark_green")),
        )


@dataclass(frozen=True)
class RigConfig:
    """
    Typed configuration for a single behaviour rig.

    Contains everything a rig window / session controller needs:
    hardware settings from the YAML, process settings (camera, DAQ
    timeouts), and runtime fields injected by the launcher.

    Frozen after construction.
    """
    # From YAML — per-rig hardware
    name: str = "Rig 1"
    board_name: str = ""
    board_type: str = "giga"
    enabled: bool = True
    description: str = ""
    camera_serial: str = ""
    daq_board_name: str = ""
    scales: Optional[ScalesConfig] = None
    reward_durations: tuple[int, ...] = (500, 500, 500, 500, 500, 500)

    # From YAML — shared process settings (injected by RigsFile.load)
    processes: ProcessesConfig = field(default_factory=ProcessesConfig)

    # Runtime-injected by the launcher (not from YAML)
    board_registry_path: str = ""
    simulate: bool = False
    shared_multi_session: str = ""

    @property
    def rig_number(self) -> int:
        """Extract the rig number from the name (e.g. 'Rig 3' -> 3)."""
        try:
            return int(self.name.split()[-1])
        except (ValueError, IndexError):
            return 1

    @classmethod
    def from_dict(
        cls,
        data: dict,
        processes: Optional[ProcessesConfig] = None,
        **runtime_fields,
    ) -> RigConfig:
        """Build a RigConfig from a YAML rig entry dict.

        Args:
            data:            The raw rig dict from the YAML.
            processes:       Shared ProcessesConfig (from the global
                             ``processes`` section). If omitted, defaults
                             are used.
            **runtime_fields: Extra fields set by the launcher at runtime
                             (e.g. ``board_registry_path``, ``simulate``).
        """
        scales_data = data.get("scales")
        scales = ScalesConfig.from_dict(scales_data) if scales_data else None

        reward_durations = data.get("reward_durations", [500] * 6)
        if isinstance(reward_durations, list):
            reward_durations = tuple(reward_durations)

        return cls(
            name=data.get("name", "Rig 1"),
            board_name=data.get("board_name", ""),
            board_type=data.get("board_type", "giga"),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            camera_serial=str(data.get("camera_serial", "")),
            daq_board_name=data.get("daq_board_name", ""),
            scales=scales,
            reward_durations=reward_durations,
            processes=processes or ProcessesConfig(),
            **runtime_fields,
        )


@dataclass(frozen=True)
class RigsFile:
    """
    The complete parsed config file.

    Load once at startup via ``RigsFile.load(path)``. Nothing else in
    the codebase should open the YAML directly.
    """
    rigs: tuple[RigConfig, ...]
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    processes: ProcessesConfig = field(default_factory=ProcessesConfig)
    cohort_folders: tuple[CohortFolder, ...] = ()
    mice: tuple[MouseEntry, ...] = ()

    @classmethod
    def load(cls, path: str | Path) -> RigsFile:
        """Load and validate a rigs YAML file."""
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        global_config = GlobalConfig.from_dict(data.get("global", {}))
        processes = ProcessesConfig.from_dict(data.get("processes", {}))

        # Each RigConfig gets the shared processes config baked in
        rigs = tuple(
            RigConfig.from_dict(r, processes=processes)
            for r in data.get("rigs", [])
        )

        cohort_folders = tuple(
            CohortFolder(
                name=c.get("name", ""),
                directory=c.get("directory", ""),
                description=c.get("description", ""),
            )
            for c in data.get("cohort_folders", [])
        )

        mice = tuple(
            MouseEntry(
                id=m.get("id", ""),
                description=m.get("description", ""),
                default_cohort=m.get("default_cohort", ""),
            )
            for m in data.get("mice", [])
        )

        return cls(
            rigs=rigs,
            global_config=global_config,
            processes=processes,
            cohort_folders=cohort_folders,
            mice=mice,
        )

    def get_rig(self, name: str) -> Optional[RigConfig]:
        """Look up a rig by name. Returns None if not found."""
        for rig in self.rigs:
            if rig.name == name:
                return rig
        return None
