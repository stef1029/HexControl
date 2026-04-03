"""
Audio Spatial Autotraining Stage Definitions

Trains mice to respond to both visual (LED) and spatial audio (white noise)
cues at individual ports. Progresses from combined simultaneous presentation
to separated interleaved cues, with automatic remedial routing for the
weaker modality.

Training progression:

  warm_up
    |-> (mouse's saved stage from previous session)

  Phase 1: Platform-reward association
    scales_training               - Platform -> immediate reward at port 1

  Phase 2: Combined cue introduction
    combined_single_port          - LED + noise simultaneously at port 1

  Phase 3: Spatial discrimination with combined cues
    combined_two_ports_lenient    - LED + noise at ports 1 or 5, ignore incorrect
    combined_two_ports            - LED + noise at ports 1 or 5, with punishment

  Phase 4: Cue separation (which modality are they following?)
    separated_two_ports           - Visual OR audio cue at ports 1/5, interleaved

  Phase 5: Remedial for the weaker modality
    visual_only_two_ports         - Visual only at ports 1/5 (if visual was weak)
    audio_only_two_ports          - Audio only at ports 1/5 (if audio was weak)

  Phase 6: Full generalisation
    interleaved_6_ports           - All 6 ports, visual or audio interleaved

  Phase 7: Cue duration ladder (both modalities)
    cue_duration_1000ms -> 750ms -> 500ms -> 250ms -> 100ms

Stage parameter: cue_type
    "combined"     - LED + noise simultaneously on the target port
    "visual"       - LED only
    "audio"        - Noise only
    "interleaved"  - Randomly pick visual or audio per trial
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


# --- Shared override fragment for standard timing/punishment ----------------

_STANDARD_PUNISHMENT = {
    "incorrect_timeout": 5.0,
    "spotlight_duration": 1.0,
    "spotlight_brightness": 128,
}

_STANDARD_TIMING = {
    "weight_offset": 3.0,
    "platform_settle_time": 1.0,
    "response_timeout": 5.0,
    "wait_duration": 0.0,
    "iti": 1.0,
}


# -----------------------------------------------------------------------------
# Warm-up: runs at session start for mice past 6-port stage
# -----------------------------------------------------------------------------

_register(Stage(
    name="warm_up",
    display_name="Warm-Up",
    description=(
        "Start-of-day warm-up. All 6 ports with interleaved visual/audio cues, "
        "continuous presentation. Only runs for mice that have previously "
        "reached the 6-port interleaved stage."
    ),
    is_warmup=True,
    warmup_after="interleaved_6_ports",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_type": "interleaved",
        "cue_duration": 0.0,
        "led_brightness": 255,
        **_STANDARD_TIMING,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 1: Platform-reward association (scales training)
# -----------------------------------------------------------------------------

_register(Stage(
    name="scales_training",
    display_name="Scales Training",
    description=(
        "Platform-reward association. Mouse stands on the platform and "
        "reward is immediately delivered at port 1."
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
# Phase 2: Combined cue at a single port
# -----------------------------------------------------------------------------

_register(Stage(
    name="combined_single_port",
    display_name="Combined cue (1 port)",
    description=(
        "LED and white noise presented simultaneously at port 1. "
        "Teaches the mouse that both visual and auditory signals "
        "indicate the same reward location."
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


# -----------------------------------------------------------------------------
# Phase 3: Combined cues at two ports (spatial discrimination)
# -----------------------------------------------------------------------------

_register(Stage(
    name="combined_two_ports_lenient",
    display_name="Combined cue (2 ports, lenient)",
    description=(
        "LED + noise at ports 1 or 5 with incorrect touches ignored. "
        "Lets the mouse explore spatial discrimination with combined cues."
    ),
    restart_stage="combined_single_port",
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
        "ignore_incorrect": True,
        **_STANDARD_TIMING,
        **_STANDARD_PUNISHMENT,
    },
))

_register(Stage(
    name="combined_two_ports",
    display_name="Combined cue (2 ports)",
    description=(
        "LED + noise at ports 1 or 5 with punishment for incorrect touches."
    ),
    restart_stage="combined_single_port",
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
        **_STANDARD_TIMING,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 4: Separated cues at two ports (which modality are they following?)
# -----------------------------------------------------------------------------

_register(Stage(
    name="separated_two_ports",
    display_name="Separated cues (2 ports)",
    description=(
        "Visual OR audio cue at ports 1/5, randomly interleaved. "
        "Reveals which modality the mouse is relying on."
    ),
    restart_stage="combined_two_ports",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_type": "interleaved",
        "cue_duration": 0.0,
        "led_brightness": 255,
        **_STANDARD_TIMING,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 5: Remedial stages for the weaker modality
# -----------------------------------------------------------------------------

_register(Stage(
    name="visual_only_two_ports",
    display_name="Visual only (2 ports, remedial)",
    description=(
        "Visual-only cues at ports 1/5. Used when the mouse learned audio "
        "but not visual discrimination in the separated stage."
    ),
    restart_stage="separated_two_ports",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_type": "visual",
        "cue_duration": 0.0,
        "led_brightness": 255,
        **_STANDARD_TIMING,
        **_STANDARD_PUNISHMENT,
    },
))

_register(Stage(
    name="audio_only_two_ports",
    display_name="Audio only (2 ports, remedial)",
    description=(
        "Audio-only (noise) cues at ports 1/5. Used when the mouse learned "
        "visual but not audio discrimination in the separated stage."
    ),
    restart_stage="separated_two_ports",
    overrides={
        "port_0_enabled": False,
        "port_1_enabled": True,
        "port_2_enabled": False,
        "port_3_enabled": False,
        "port_4_enabled": False,
        "port_5_enabled": True,
        "cue_type": "audio",
        "cue_duration": 0.0,
        "led_brightness": 255,
        **_STANDARD_TIMING,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 6: Full 6-port generalisation with interleaved cues
# -----------------------------------------------------------------------------

_register(Stage(
    name="interleaved_6_ports",
    display_name="6 ports interleaved",
    description=(
        "All 6 ports, visual or audio cue randomly interleaved per trial."
    ),
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_type": "interleaved",
        "cue_duration": 0.0,
        "led_brightness": 255,
        **_STANDARD_TIMING,
        **_STANDARD_PUNISHMENT,
    },
))


# -----------------------------------------------------------------------------
# Phase 7: Cue duration ladder (both modalities, all 6 ports)
# -----------------------------------------------------------------------------

def _cue_duration_stage(duration_ms: int, description: str, is_final: bool = False) -> Stage:
    name = f"cue_duration_{duration_ms}ms"
    return Stage(
        name=name,
        display_name=f"Cue duration {duration_ms}ms",
        description=description,
        overrides={
            "port_0_enabled": True,
            "port_1_enabled": True,
            "port_2_enabled": True,
            "port_3_enabled": True,
            "port_4_enabled": True,
            "port_5_enabled": True,
            "cue_type": "interleaved",
            "cue_duration": duration_ms / 1000.0,
            "led_brightness": 255,
            **_STANDARD_TIMING,
            **_STANDARD_PUNISHMENT,
        },
    )


_register(_cue_duration_stage(1000, "All 6 ports, interleaved cues limited to 1000ms."))
_register(_cue_duration_stage(750, "All 6 ports, interleaved cues limited to 750ms."))
_register(_cue_duration_stage(500, "All 6 ports, interleaved cues limited to 500ms."))
_register(_cue_duration_stage(250, "All 6 ports, interleaved cues limited to 250ms."))
_register(_cue_duration_stage(100, "All 6 ports, interleaved cues limited to 100ms (final stage).", is_final=True))
