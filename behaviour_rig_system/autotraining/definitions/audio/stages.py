"""
Audio Autotraining Stage Definitions

Defines all stages for the audio/visual interleaved training sequence.
Mice progress through the same visual stages as the visual-only protocol
up to 6-port generalisation, then branch into audio training.

Training progression:

  warm_up
    └─> (mouse's saved stage from previous session)

  Phase 0: Platform-reward association (scales training)
    scales_training           - Mount platform -> immediate reward (no LED cue)

  Phase 1–4: Same as visual protocol
    introduce_1_led_no_wait -> introduce_1_led -> introduce_another_led_lenient
    -> introduce_another_led -> multiple_leds_2x -> multiple_leds_6x

  Phase 5: Audio introduction
    audio_only            - Pure audio trials, continuous tone, reward at port 0

  Phase 6: Interleaved audio/visual
    interleaved_2_6       - Target end stage (2 audio : 5 visual ports)
    interleaved_3_6       - More audio practice (regression from 2:6)
    interleaved_1_6       - Less audio, more visual (regression from 2:6)
    visual_only_remedial  - Pure visual at ports 1-5 (regression from interleaved)
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
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.0,
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
# Phase 1–4: Shared visual stages (identical to visual protocol)
# -----------------------------------------------------------------------------

_register(Stage(
    name="introduce_1_led_no_wait",
    display_name="Introduce 1 port + LED (no scales wait)",
    description="",
    restart_stage="scales_training",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": False,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 0.0,
        "response_timeout": 10.0,
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
    name="introduce_1_led",
    display_name="Introduce 1 port + LED",
    description="",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": False,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 10.0,
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
    name="introduce_another_led_lenient",
    display_name="2nd port (lenient)",
    description="LED at port 5 with incorrect touches ignored.",
    restart_stage="introduce_1_led",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": False,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 10.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "ignore_incorrect": True,
        "audio_enabled": False,
        "audio_proportion": 6,
    },
))

_register(Stage(
    name="introduce_another_led",
    display_name="Introduce a different port",
    description="",
    restart_stage="introduce_1_led",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": False,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 10.0,
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
    name="multiple_leds_2x",
    display_name="2 ports active",
    description="",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_duration": 0.0,
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
    name="multiple_leds_6x",
    display_name="6 ports active",
    description="",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.0,
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


# -----------------------------------------------------------------------------
# Phase 5: Audio introduction — pure audio trials
# -----------------------------------------------------------------------------

_register(Stage(
    name="audio_only",
    display_name="Audio Only",
    description=(
        "Pure audio trials. Continuous overhead tone, mouse must go to the "
        "landmarked port (port 0). No visual trials."
    ),
    restart_stage="interleaved_2_6",
    overrides={
        # No visual ports enabled — all trials are audio
        "port_0_enabled": False,
        "port_1_enabled": False,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": False,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": True,
        "audio_proportion": 0,   # 0 = all audio
    },
))


# -----------------------------------------------------------------------------
# Phase 6: Interleaved audio/visual stages
# Visual trials use ports 1–5 (non-landmarked); audio rewards at port 0.
# -----------------------------------------------------------------------------

_register(Stage(
    name="interleaved_2_6",
    display_name="Interleaved 2:5 audio:visual",
    description=(
        "Target interleaved stage. 2 audio entries mixed with 5 visual ports "
        "(ports 1-5). Audio trials reward at the landmarked port 0."
    ),
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": True,
        "audio_proportion": 2,
    },
))

_register(Stage(
    name="interleaved_3_6",
    display_name="Interleaved 3:5 audio:visual",
    description=(
        "More audio practice. 3 audio entries mixed with 5 visual ports. "
        "Used when audio performance drops below 50% in the 2:5 stage."
    ),
    restart_stage="interleaved_2_6",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": True,
        "audio_proportion": 3,
    },
))

_register(Stage(
    name="interleaved_1_6",
    display_name="Interleaved 1:5 audio:visual",
    description=(
        "Less audio, more visual practice. 1 audio entry mixed with 5 visual "
        "ports. Used when visual performance drops below 50% in the 2:5 stage."
    ),
    restart_stage="interleaved_2_6",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.0,
        "led_brightness": 255,
        "weight_offset": 3.0,
        "platform_settle_time": 1.0,
        "response_timeout": 5.0,
        "wait_duration": 0.0,
        "iti": 1.0,
        "incorrect_timeout": 5.0,
        "spotlight_duration": 1.0,
        "spotlight_brightness": 128,
        "audio_enabled": True,
        "audio_proportion": 1,
    },
))

_register(Stage(
    name="visual_only_remedial",
    display_name="Visual Only (remedial)",
    description=(
        "Remedial visual-only stage for when visual performance drops below 30% "
        "during interleaved training. Uses ports 1-5 (non-landmarked). "
        "Separate from multiple_leds_6x to allow independent transitions."
    ),
    restart_stage="interleaved_2_6",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.0,
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
