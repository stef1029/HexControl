"""
Stage Definition

A Stage is a named set of parameter overrides that define how the behaviour
task should run during a particular phase of training. Stages only specify
what is DIFFERENT from the base defaults — unspecified parameters inherit
from the default parameter set.
"""

from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# Base defaults — these apply to every stage unless overridden
# =============================================================================

BASE_DEFAULTS: dict[str, Any] = {
    # Port selection
    "port_0_enabled": False,
    "port_1_enabled": False,
    "port_2_enabled": False,
    "port_3_enabled": False,
    "port_4_enabled": False,
    "port_5_enabled": False,

    # Cue settings
    "cue_duration": 0.0,       # 0 = stay on until response
    "led_brightness": 255,

    # Platform settings
    "weight_offset": 3.0,
    "platform_settle_time": 1.0,

    # Trial timing
    "response_timeout": 10.0,
    "wait_duration": 0.0,
    "iti": 1.0,

    # Reward/punishment
    "reward_duration": 500,     # ms
    "punishment_duration": 0.0, # s — 0 means no punishment
    "punishment_enabled": False,

    # Audio
    "audio_enabled": False,
    "audio_proportion": 6,
}


# =============================================================================
# Stage dataclass
# =============================================================================

@dataclass
class Stage:
    """
    A training stage — a named set of parameter overrides.

    Attributes:
        name:        Unique identifier (e.g. "phase_1_platform_reward")
        display_name: Human-readable label for logging
        description: What this stage trains the mouse to do
        overrides:   Dict of parameter values that differ from BASE_DEFAULTS
        is_warmup:   If True, this stage is used as the session-start warm-up
    """
    name: str
    display_name: str
    description: str = ""
    overrides: dict[str, Any] = field(default_factory=dict)
    is_warmup: bool = False

    def get_params(self) -> dict[str, Any]:
        """
        Return the full parameter set for this stage.

        Merges BASE_DEFAULTS with this stage's overrides.
        """
        params = BASE_DEFAULTS.copy()
        params.update(self.overrides)
        return params

    def __repr__(self) -> str:
        return f"Stage('{self.name}', overrides={list(self.overrides.keys())})"
