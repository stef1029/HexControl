"""
Visual Autotraining Stage Definitions

Defines all stages in the visual (LED-only) mouse training autotraining sequence.
Each stage is a named set of parameter overrides applied on top of
the BASE_DEFAULTS from stage.py.

Training progression:

  warm_up
    └─> (mouse's saved stage from previous session)

  Phase 0: Platform-reward association (scales training)
    scales_training           - Mount platform -> immediate reward (no LED cue)

  Phase 1: Platform association & rearing
    introduce_1_led_no_wait   - Single port LED training (no platform wait)
    introduce_1_led           - Single port LED training (with platform wait)

  Phase 2: Cue-response training
    phase_2_cue_no_punish     - Rear -> LED at port 0 -> go to port 0 (no punishment)
    phase_2_cue_with_punish   - Same but errors trigger punishment

  Phase 3: Spatial flexibility
    phase_3_port3_no_punish   - LED at port 2 only (no punishment)
    phase_3_port3_with_punish - LED at port 2 (with punishment)
    phase_3_two_ports         - Alternating ports 0 and 2

  Phase 4: Generalisation
    phase_4_three_ports       - Randomised across ports 0, 2, 4
    phase_4_all_ports         - Full 6-port randomisation (final stage)
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


# -----------------------------------------------------------------------------
# Warm-up: runs at session start only for mice that have reached 6-port stage
# -----------------------------------------------------------------------------

_register(Stage(
    name="warm_up",
    display_name="Warm-Up",
    description=(
        "Start-of-day warm-up. All 6 ports with continuous cue, no punishment. "
        "Only runs for mice that have previously reached the 6-port stage."
    ),
    is_warmup=True,
    warmup_after="multiple_leds_6x",
    overrides={
        # Port selection
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,

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

        # Reward/punishment
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,

        # Audio
        "audio_enabled": False,
        "audio_proportion": 6,
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
        "reward is immediately delivered at a fixed port. No LED cue, "
        "no choice — just learn that platform = reward."
    ),
    overrides={
        "trial_mode": "scales",
        "scales_reward_port": 0,
        "collection_timeout": 30.0,
        "weight_offset": 3.0,
        "platform_settle_time": 0.0,
        "iti": 1.0,
    },
))


# -----------------------------------------------------------------------------
# Phase 1: Platform association and rearing
# -----------------------------------------------------------------------------

_register(Stage(
    name="introduce_1_led_no_wait",
    display_name="Introduce 1 port + LED (no scales wait)",
    description=(
        ""
    ),
    restart_stage="scales_training",
    overrides={
        # Port selection
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": False,

        # Cue settings
        "cue_duration": 0.0,       # 0 = stay on until response
        "led_brightness": 255,

        # Platform settings
        "weight_offset": 3.0,
        "platform_settle_time": 0.0,

        # Trial timing
        "response_timeout": 10.0,
        "wait_duration": 0.0,
        "iti": 1.0,

        # Reward/punishment
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,

        # Audio
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="introduce_1_led",
    display_name="Introduce 1 port + LED",
    description=(
        ""
    ),
    overrides={
        # Port selection
        "port_0_enabled": False,
        "port_1_enabled": True,
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
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,

        # Audio
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="introduce_another_led_lenient",
    display_name="2nd port (lenient)",
    description=(
        "LED at port 3 with incorrect touches ignored — lets the mouse explore freely."
    ),
    restart_stage="introduce_1_led",
    overrides={
        # Port selection
        "port_0_enabled": False,
        "port_1_enabled": False,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,

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
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "ignore_incorrect": True,

        # Audio
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="introduce_another_led",
    display_name="Introduce a different port",
    description=(
        ""
    ),
    restart_stage="introduce_1_led",
    overrides={
        # Port selection
        "port_0_enabled": False,
        "port_1_enabled": False,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,

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
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,

        # Audio
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="multiple_leds_2x",
    display_name="2 ports active",
    description=(
        ""
    ),
    overrides={
        # Port selection
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,

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

        # Reward/punishment
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,

        # Audio
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="multiple_leds_6x",
    display_name="6 ports active",
    description=(
        ""
    ),
    overrides={
        # Port selection
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,

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

        # Reward/punishment
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,

        # Audio
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))


# -----------------------------------------------------------------------------
# Phase 5: Cue duration ladder (all 6 ports, decreasing LED on-time)
# -----------------------------------------------------------------------------

_register(Stage(
    name="cue_duration_1000ms",
    display_name="Cue duration 1000ms",
    description="All 6 ports, LED cue limited to 1000ms.",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 1.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="cue_duration_750ms",
    display_name="Cue duration 750ms",
    description="All 6 ports, LED cue limited to 750ms.",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.75,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="cue_duration_500ms",
    display_name="Cue duration 500ms",
    description="All 6 ports, LED cue limited to 500ms.",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.5,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="cue_duration_250ms",
    display_name="Cue duration 250ms",
    description="All 6 ports, LED cue limited to 250ms.",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.25,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="cue_duration_100ms",
    display_name="Cue duration 100ms",
    description="All 6 ports, LED cue limited to 100ms (final stage).",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.1,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))