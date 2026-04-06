"""
Audio Spatial Autotraining Stage Definitions

Trains mice to respond to combined visual (LED) + spatial audio (white noise)
cues at individual ports. Mirrors the visual autotraining introduction sequence
but with simultaneous LED + noise cues. Autotraining ends at 2-port
discrimination with combined cues.

Training progression:

  warm_up
    |-> (mouse's saved stage from previous session)

  Phase 0: Platform-reward association
    scales_training                 - Platform -> immediate reward at port 1

  Phase 1: Single port introduction (combined cue)
    combined_1_port_no_wait         - LED + noise at port 1, no platform settle
    combined_1_port                 - LED + noise at port 1, with platform settle

  Phase 2: Second port introduction (combined cue)
    combined_2nd_port_lenient       - LED + noise at port 5, ignore incorrect
    combined_2nd_port               - LED + noise at port 5, with punishment

  Phase 3: Two-port discrimination (final stage)
    combined_2_ports                - LED + noise at ports 1 or 5, with punishment

Stage parameter: cue_type
    "combined"  - LED + noise simultaneously on the target port
"""

from ...stage import Stage


# =============================================================================
# Stage definitions
# =============================================================================

STAGES: dict[str, Stage] = {}


def _register(stage: Stage) -> Stage:
    """Helper to add a stage to the STAGES dict."""
    STAGES[stage.name] = stage
    return stage


# --- Shared override fragments -----------------------------------------------

_STANDARD_PUNISHMENT = {
    "incorrect_timeout": 5.0,
    "spotlight_duration": 1.0,
    "spotlight_brightness": 128,
}


# -----------------------------------------------------------------------------
# Warm-up: runs at session start for mice past the 2-port stage
# -----------------------------------------------------------------------------

_register(Stage(
    name="warm_up",
    display_name="Warm-Up",
    description=(
        "Start-of-day warm-up. Ports 1 and 5 with combined LED + noise cues, "
        "continuous presentation. Only runs for mice that have previously "
        "reached the 2-port discrimination stage."
    ),
    is_warmup=True,
    warmup_after="combined_2_ports",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_type": "combined",
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 0: Platform-reward association (scales training)
# -----------------------------------------------------------------------------

_register(Stage(
    name="scales_training",
    display_name="Scales Training",
    description=(
        "Platform-reward association. Mouse stands on the platform and "
        "reward is immediately delivered at port 1. No cue, no choice."
    ),
    overrides={
        "trial_mode": "scales",
        "scales_reward_port": 1,
        "collection_timeout": 30.0,
        "weight_offset": 3.0,
        "platform_settle_time": 0.0,
        "iti": 1.0,
    },
))


# -----------------------------------------------------------------------------
# Phase 1: Single port introduction (combined LED + noise)
# -----------------------------------------------------------------------------

_register(Stage(
    name="combined_1_port_no_wait",
    display_name="Combined cue, 1 port (no scales wait)",
    description=(
        "LED + noise at port 1. No platform settle time required. "
        "Teaches the mouse to approach a combined cue for reward."
    ),
    restart_stage="scales_training",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": False,
        "cue_type": "combined",
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 0.0,
        "response_timeout": 10.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        **_STANDARD_PUNISHMENT,
    },
))

_register(Stage(
    name="combined_1_port",
    display_name="Combined cue, 1 port",
    description=(
        "LED + noise at port 1 with platform settle time. "
        "Mouse must settle on the platform before the cue is presented."
    ),
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": False,
        "cue_type": "combined",
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 10.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 2: Second port introduction (combined cue)
# -----------------------------------------------------------------------------

_register(Stage(
    name="combined_2nd_port_lenient",
    display_name="Combined cue, 2nd port (lenient)",
    description=(
        "LED + noise at port 5 with incorrect touches ignored. "
        "Lets the mouse explore the second port freely."
    ),
    restart_stage="combined_1_port",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": False,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_type": "combined",
        "cue_duration": 0.0,
        "led_brightness": 255,
        "ignore_incorrect": True,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 10.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        **_STANDARD_PUNISHMENT,
    },
))

_register(Stage(
    name="combined_2nd_port",
    display_name="Combined cue, 2nd port",
    description=(
        "LED + noise at port 5 with punishment for incorrect touches."
    ),
    restart_stage="combined_1_port",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": False,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_type": "combined",
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 3: Two-port discrimination (final autotraining stage)
# -----------------------------------------------------------------------------

_register(Stage(
    name="combined_2_ports",
    display_name="Combined cue, 2 ports",
    description=(
        "LED + noise at ports 1 or 5 randomly, with punishment for "
        "incorrect touches. Final autotraining stage."
    ),
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_type": "combined",
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        **_STANDARD_PUNISHMENT,
    },
))
