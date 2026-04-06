"""
Audio Spatial Autotraining Transition Graph

Mirrors the visual autotraining introduction sequence but with combined
LED + noise cues. Ends at 2-port discrimination.

Training path:

    scales_training
        -> combined_1_port_no_wait
            -> combined_1_port
                -> combined_2nd_port_lenient
                    -> combined_2nd_port
                        -> combined_2_ports  (final stage)

Transition priorities:
    1:     Warm-up exit
    5:     Regression rules
    10:    Forward progression
"""

from ...transitions import Transition, Condition


# =============================================================================
# All transitions
# =============================================================================

TRANSITIONS: list[Transition] = [

    # -------------------------------------------------------------------------
    # Warm-up exit
    # -------------------------------------------------------------------------

    Transition(
        from_stage="warm_up",
        to_stage="$saved",
        conditions=[
            Condition("consecutive_correct", ">=", 5),
            Condition("trials_in_stage", ">=", 10),
        ],
        priority=1,
        description="Warm-up complete (5 consecutive correct, 10+ trials)",
    ),

    # -------------------------------------------------------------------------
    # Forward: scales_training -> combined_1_port_no_wait
    # -------------------------------------------------------------------------

    Transition(
        from_stage="scales_training",
        to_stage="combined_1_port_no_wait",
        conditions=[
            Condition("rolling_trial_duration", "<=", 2.5, window=20),
        ],
        priority=10,
        description="Scales training complete (avg trial time <= 2.5s over 20)",
    ),

    # -------------------------------------------------------------------------
    # Forward: combined_1_port_no_wait -> combined_1_port
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_1_port_no_wait",
        to_stage="combined_1_port",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20),
        ],
        priority=10,
        description="Single port mastered (>=90% over 20), adding platform settle",
    ),

    # -------------------------------------------------------------------------
    # Forward: combined_1_port -> combined_2nd_port_lenient
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_1_port",
        to_stage="combined_2nd_port_lenient",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30),
        ],
        priority=10,
        description="Single port with settle mastered (>=90% over 30), introducing 2nd port",
    ),

    # -------------------------------------------------------------------------
    # Forward: combined_2nd_port_lenient -> combined_2nd_port
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_2nd_port_lenient",
        to_stage="combined_2nd_port",
        conditions=[
            Condition("trials_in_stage", ">=", 30),
        ],
        priority=10,
        description="Lenient 2nd port complete (30 trials), adding punishment",
    ),

    # -------------------------------------------------------------------------
    # Forward: combined_2nd_port -> combined_2_ports
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_2nd_port",
        to_stage="combined_2_ports",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20),
        ],
        priority=10,
        description="2nd port mastered (>=90% over 20), moving to 2-port discrimination",
    ),

    # -------------------------------------------------------------------------
    # Regression rules
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_1_port_no_wait",
        to_stage="scales_training",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Regression at 1 port no wait (<30% over 20), back to scales",
    ),

    Transition(
        from_stage="combined_1_port",
        to_stage="combined_1_port_no_wait",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Regression at 1 port with settle (<30% over 20), removing settle",
    ),

    Transition(
        from_stage="combined_2nd_port",
        to_stage="combined_1_port",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Regression at 2nd port (<30% over 20), back to 1 port",
    ),

    Transition(
        from_stage="combined_2_ports",
        to_stage="combined_2nd_port",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Regression at 2-port discrimination (<30% over 20), back to 2nd port",
    ),

]
