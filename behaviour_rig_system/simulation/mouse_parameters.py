"""
Mouse Parameter Definitions — configurable settings for SimulatedMouse.

Uses the existing Parameter types from core.parameter_types so the GUI
can render these with ParameterFormBuilder (same widget system as
protocol parameters).

Parameters are organised into groups:
    General          — enable/disable, headless, speed factor
    Mounting         — fixed mount delay
    V_patience       — "waiting → cue appears" learning
    Responding       — fixed engagement / response time / inhibition
    V_accuracy       — "follow cue → reward" learning
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
    FloatParameter(
        name="sim_speed",
        display_name="Simulation Speed",
        default=1.0,
        min_value=1.0,
        max_value=50.0,
        step=1.0,
        description="Time multiplier when mouse is enabled (e.g. 10 = 10× faster)",
        group="General",
        order=2,
    ),
    # ── Mounting ──────────────────────────────────────────────
    FloatParameter(
        name="mount_delay",
        display_name="Mount Delay (s)",
        default=2.0,
        min_value=0.1,
        max_value=30.0,
        step=0.5,
        description="Fixed delay before the mouse mounts the platform",
        group="Mounting",
        order=10,
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
        default=1,
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

    # ── Responding ────────────────────────────────────────────
    FloatParameter(
        name="timeout_probability",
        display_name="Timeout Probability",
        default=0.05,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        description="Fixed probability the mouse ignores a cue",
        group="Responding",
        order=30,
    ),
    FloatParameter(
        name="response_time",
        display_name="Response Time (s)",
        default=1.5,
        min_value=0.1,
        max_value=30.0,
        step=0.1,
        description="Mean time to respond after cue appears",
        group="Responding",
        order=31,
    ),
    FloatParameter(
        name="response_time_std",
        display_name="Response Time Std (s)",
        default=0.8,
        min_value=0.0,
        max_value=5.0,
        step=0.1,
        group="Responding",
        order=32,
    ),
    FloatParameter(
        name="inhibition_probability",
        display_name="Inhibition Probability",
        default=0.3,
        min_value=0.0,
        max_value=1.0,
        step=0.05,
        description="P(withhold response) when the mouse would pick the wrong port",
        group="Responding",
        order=33,
    ),

    # ── V_accuracy: "follow cue → reward" ─────────────────────
    FloatParameter(
        name="v_accuracy_alpha",
        display_name="Learning Rate",
        default=1.0,
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

]
