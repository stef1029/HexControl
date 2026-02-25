"""
Training Stage Definitions

Defines all stages in the standard mouse training autotraining sequence.
Each stage is a named set of parameter overrides applied on top of
the BASE_DEFAULTS from stage.py.

Training progression (based on the 4-phase shaping procedure):

  warm_up
    └─> (mouse's saved stage from previous session)

  Phase 1: Platform association & rearing
    phase_1_platform_reward   - Mount platform -> immediate reward at port 0
    phase_1_rearing           - Mount + rear -> reward at port 0

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

from ..stage import Stage


# =============================================================================
# Stage definitions
# =============================================================================

STAGES: dict[str, Stage] = {}


def _register(stage: Stage) -> Stage:
    """Helper to add a stage to the STAGES dict."""
    STAGES[stage.name] = stage
    return stage


# -----------------------------------------------------------------------------
# Warm-up: always runs at session start
# -----------------------------------------------------------------------------

_register(Stage(
    name="warm_up",
    display_name="Warm-Up",
    description=(
        "Start-of-day warm-up. Single port, no punishment, "
        "gives the mouse a few easy wins to get going."
    ),
    is_warmup=True,
    overrides={
        "port_0_enabled": True,
        "punishment_duration": 0.0,
        "punishment_enabled": False,
        "wait_duration": 0.0,
        "response_timeout": 30.0,   # generous timeout for warm-up
    },
))


# -----------------------------------------------------------------------------
# Phase 1: Platform association and rearing
# -----------------------------------------------------------------------------

_register(Stage(
    name="phase_1_platform_reward",
    display_name="Phase 1a: Platform Reward",
    description=(
        "Mouse mounts platform -> immediate reward at port 0. "
        "No cue, no rearing required. Establishes platform as "
        "reward-predictive location."
    ),
    overrides={
        "port_0_enabled": True,
        "cue_duration": 0.0,       # LED stays on (acts as beacon)
        "punishment_duration": 0.0,
        "punishment_enabled": False,
        "wait_duration": 0.0,
        "response_timeout": 60.0,  # very generous - mouse is just learning
    },
))

_register(Stage(
    name="phase_1_rearing",
    display_name="Phase 1b: Rearing Required",
    description=(
        "Mouse mounts platform + rears -> reward at port 0. "
        "Introduces the rearing initiation signal."
    ),
    overrides={
        "port_0_enabled": True,
        "cue_duration": 0.0,
        "punishment_duration": 0.0,
        "punishment_enabled": False,
        "wait_duration": 1.0,      # requires brief wait (rearing stand-in)
        "response_timeout": 30.0,
    },
))


# -----------------------------------------------------------------------------
# Phase 2: Cue-response training
# -----------------------------------------------------------------------------

_register(Stage(
    name="phase_2_cue_no_punish",
    display_name="Phase 2a: Cue-Response (No Punishment)",
    description=(
        "Rear on platform -> LED at port 0 -> go to port 0 for reward. "
        "No punishment for incorrect responses yet."
    ),
    overrides={
        "port_0_enabled": True,
        "cue_duration": 0.0,       # LED stays on until response
        "punishment_duration": 0.0,
        "punishment_enabled": False,
        "wait_duration": 1.0,
        "response_timeout": 20.0,
    },
))

_register(Stage(
    name="phase_2_cue_with_punish",
    display_name="Phase 2b: Cue-Response (With Punishment)",
    description=(
        "Same as Phase 2a but incorrect port visits now trigger "
        "overhead lighting and a 10-second timeout."
    ),
    overrides={
        "port_0_enabled": True,
        "cue_duration": 0.0,
        "punishment_duration": 10.0,
        "punishment_enabled": True,
        "wait_duration": 1.0,
        "response_timeout": 15.0,
    },
))


# -----------------------------------------------------------------------------
# Phase 3: Spatial flexibility
# -----------------------------------------------------------------------------

_register(Stage(
    name="phase_3_port3_no_punish",
    display_name="Phase 3a: Port 3 Only (No Punishment)",
    description=(
        "LED switches to port 2 (physical port 3). "
        "No punishment to allow exploratory learning."
    ),
    overrides={
        "port_2_enabled": True,    # port index 2 = physical port 3
        "cue_duration": 0.0,
        "punishment_duration": 0.0,
        "punishment_enabled": False,
        "wait_duration": 1.0,
        "response_timeout": 20.0,
    },
))

_register(Stage(
    name="phase_3_port3_with_punish",
    display_name="Phase 3b: Port 3 (With Punishment)",
    description=(
        "Port 2 only with punishment for errors."
    ),
    overrides={
        "port_2_enabled": True,
        "cue_duration": 0.0,
        "punishment_duration": 10.0,
        "punishment_enabled": True,
        "wait_duration": 1.0,
        "response_timeout": 15.0,
    },
))

_register(Stage(
    name="phase_3_two_ports",
    display_name="Phase 3c: Ports 1 & 3 Alternating",
    description=(
        "LED alternates between ports 0 and 2 within the session. "
        "Mouse must follow the cue rather than using spatial strategy."
    ),
    overrides={
        "port_0_enabled": True,
        "port_2_enabled": True,
        "cue_duration": 0.0,
        "punishment_duration": 10.0,
        "punishment_enabled": True,
        "wait_duration": 1.0,
        "response_timeout": 15.0,
    },
))


# -----------------------------------------------------------------------------
# Phase 4: Generalisation
# -----------------------------------------------------------------------------

_register(Stage(
    name="phase_4_three_ports",
    display_name="Phase 4a: 3-Port Randomisation",
    description=(
        "Randomised across ports 0, 2, and 4. "
        "Tests generalisation beyond two learned positions."
    ),
    overrides={
        "port_0_enabled": True,
        "port_2_enabled": True,
        "port_4_enabled": True,
        "cue_duration": 0.0,
        "punishment_duration": 10.0,
        "punishment_enabled": True,
        "wait_duration": 1.0,
        "response_timeout": 12.0,
    },
))

_register(Stage(
    name="phase_4_all_ports",
    display_name="Phase 4b: Full 6-Port Randomisation",
    description=(
        "All 6 ports enabled with randomised cue presentation. "
        "Final training stage -- mouse is fully trained when reaching "
        "80% accuracy here."
    ),
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.0,
        "punishment_duration": 10.0,
        "punishment_enabled": True,
        "wait_duration": 1.0,
        "response_timeout": 10.0,
    },
))
