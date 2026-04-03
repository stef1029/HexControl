"""
Stage Definition

A Stage is a named set of parameter overrides that define how the behaviour
task should run during a particular phase of training. Stages only specify
what is DIFFERENT from the base defaults — unspecified parameters inherit
from the default parameter set.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


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
    "response_timeout": 5.0,
    "wait_duration": 0.0,
    "iti": 1.0,

    # Incorrect trial consequences
    "ignore_incorrect": False,      # If True, wrong port touches are ignored; trial continues until correct or timeout
    "incorrect_timeout": 0.0,       # s — forced wait after incorrect touch (0 = no timeout)
    "spotlight_duration": 0.0,      # s — how long spotlights stay on during incorrect timeout (0 = no spotlight)
    "spotlight_brightness": 255,    # 0-255 — brightness of spotlights during punishment

    # Audio
    "audio_enabled": False,
    "audio_proportion": 6,

    # Scales mode (only used when trial_mode == "scales")
    "trial_mode": "visual",          # "visual" or "scales"
    "scales_reward_port": 0,         # Fixed port for reward delivery in scales mode
    "collection_timeout": 30.0,      # Time (s) to wait for mouse to visit reward port
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
        warmup_after: If set, warmup is only used when the mouse's saved stage
                      is at or past this stage in the stage ordering. If the
                      mouse hasn't reached this stage yet, warmup is skipped.
        restart_stage: Stage name to persist at session end instead of this
                       stage's own name. If None (default), the stage's own
                       name is used. Use this when a session ending on this
                       stage should restart from an earlier stage next time.
    """
    name: str
    display_name: str
    description: str = ""
    overrides: dict[str, Any] = field(default_factory=dict)
    is_warmup: bool = False
    warmup_after: Optional[str] = None
    restart_stage: Optional[str] = None

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
