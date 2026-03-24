"""
Mouse Parameter Definitions — configurable settings for SimulatedMouse.

Uses the existing Parameter types from core.parameter_types so the GUI
can render these with ParameterFormBuilder (same widget system as
protocol parameters).

Parameters are organised into groups:
    General          — enable/disable, headless, speed factor
    V_platform       — "platform → things happen" learning
    V_patience       — "waiting → cue appears" learning
    V_engagement     — "responding to cue → reward" learning
    V_accuracy       — "follow cue → reward" learning
    V_inhibition     — "wrong port → punishment" learning
"""

from core.parameter_types import BoolParameter, FloatParameter

MOUSE_PARAMETERS = [
    # ── General ────────────────────────────────────────────────
    BoolParameter(
        name="mouse_enabled",
        display_name="Enable Simulated Mouse",
        default=False,
        group="General",
        order=0,
    ),
    BoolParameter(
        name="mouse_headless",
        display_name="Headless (no Virtual Rig Window)",
        default=False,
        description="Skip the visual rig window for faster testing",
        group="General",
        order=1,
    ),
    # ── V_platform: "platform → things happen" ────────────────
    FloatParameter(
        name="v_platform_alpha",
        display_name="Learning Rate",
        default=0.10,
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        group="Platform Learning (V_platform)",
        order=10,
    ),
    FloatParameter(
        name="v_platform_initial",
        display_name="Initial Value",
        default=0.1,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        group="Platform Learning (V_platform)",
        order=11,
    ),
    FloatParameter(
        name="mount_delay_min",
        display_name="Mount Delay Min (s)",
        default=1.0,
        min_value=0.1,
        max_value=10.0,
        step=0.5,
        description="Time to mount when V_platform is high (well-trained)",
        group="Platform Learning (V_platform)",
        order=12,
    ),
    FloatParameter(
        name="mount_delay_max",
        display_name="Mount Delay Max (s)",
        default=6.0,
        min_value=1.0,
        max_value=30.0,
        step=0.5,
        description="Time to mount when V_platform is low (untrained)",
        group="Platform Learning (V_platform)",
        order=13,
    ),

    # ── V_patience: "waiting → cue appears" ───────────────────
    FloatParameter(
        name="v_patience_alpha",
        display_name="Learning Rate",
        default=0.06,
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        group="Patience Learning (V_patience)",
        order=20,
    ),
    FloatParameter(
        name="v_patience_initial",
        display_name="Initial Value",
        default=0.1,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        group="Patience Learning (V_patience)",
        order=21,
    ),
    FloatParameter(
        name="patience_min",
        display_name="Patience Min",
        default=0.3,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        description="P(stay on platform) when V_patience is low",
        group="Patience Learning (V_patience)",
        order=22,
    ),
    FloatParameter(
        name="patience_max",
        display_name="Patience Max",
        default=0.95,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        description="P(stay on platform) when V_patience is high",
        group="Patience Learning (V_patience)",
        order=23,
    ),

    # ── V_engagement: "responding to cue → reward" ────────────
    FloatParameter(
        name="v_engagement_alpha",
        display_name="Learning Rate",
        default=0.08,
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        group="Engagement Learning (V_engagement)",
        order=30,
    ),
    FloatParameter(
        name="v_engagement_initial",
        display_name="Initial Value",
        default=0.95,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        group="Engagement Learning (V_engagement)",
        order=31,
    ),
    FloatParameter(
        name="timeout_prob_max",
        display_name="Max Timeout Probability",
        default=0.4,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        description="P(timeout) when V_engagement is low",
        group="Engagement Learning (V_engagement)",
        order=32,
    ),
    FloatParameter(
        name="response_time_min",
        display_name="Response Time Min (s)",
        default=0.8,
        min_value=0.1,
        max_value=10.0,
        step=0.1,
        description="Response speed when V_engagement is high (well-trained)",
        group="Engagement Learning (V_engagement)",
        order=33,
    ),
    FloatParameter(
        name="response_time_max",
        display_name="Response Time Max (s)",
        default=5.0,
        min_value=0.5,
        max_value=30.0,
        step=0.5,
        description="Response speed when V_engagement is low (untrained)",
        group="Engagement Learning (V_engagement)",
        order=34,
    ),
    FloatParameter(
        name="response_time_std",
        display_name="Response Time Std (s)",
        default=0.8,
        min_value=0.0,
        max_value=5.0,
        step=0.1,
        group="Engagement Learning (V_engagement)",
        order=35,
    ),

    # ── V_accuracy: "follow cue → reward" ─────────────────────
    FloatParameter(
        name="v_accuracy_alpha",
        display_name="Learning Rate",
        default=0.08,
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        group="Accuracy Learning (V_accuracy)",
        order=40,
    ),
    FloatParameter(
        name="v_accuracy_initial",
        display_name="Initial Value",
        default=0.1,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        group="Accuracy Learning (V_accuracy)",
        order=41,
    ),

    # ── V_inhibition: "wrong port → punishment" ───────────────
    FloatParameter(
        name="v_inhibition_alpha",
        display_name="Learning Rate",
        default=0.05,
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        group="Inhibition Learning (V_inhibition)",
        order=50,
    ),
    FloatParameter(
        name="v_inhibition_initial",
        display_name="Initial Value",
        default=0.0,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        description="Starts at 0 — learned purely from punishment",
        group="Inhibition Learning (V_inhibition)",
        order=51,
    ),
]
