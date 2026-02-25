"""
Training Transition Graph

Defines the edges and conditions for moving between training stages.
Transitions are evaluated after every trial, in priority order (lowest first).

The special target "$saved" means "go to the mouse's persisted stage from
last session" -- used exclusively by the warm-up exit transition.

Transition priorities:
    0-4:   Global/emergency rules (apply from any stage)
    5-9:   Regression rules (falling back to easier stages)
    10-19: Forward progression rules (the main training path)
"""

from ..transitions import Transition, Condition, Operator


# =============================================================================
# All transitions
# =============================================================================

TRANSITIONS: list[Transition] = [

    # -------------------------------------------------------------------------
    # Warm-up exit: after 10 correct trials, move to the saved stage
    # -------------------------------------------------------------------------

    Transition(
        from_stage="warm_up",
        to_stage="$saved",
        conditions=[
            Condition("consecutive_correct", Operator.GTE, 5),
            Condition("trials_in_stage", Operator.GTE, 10),
        ],
        priority=1,
        description="Warm-up complete (5 consecutive correct, 10+ trials)",
    ),

    # -------------------------------------------------------------------------
    # Phase 1: Platform association -> Rearing
    # -------------------------------------------------------------------------

    Transition(
        from_stage="phase_1_platform_reward",
        to_stage="phase_1_rearing",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 50),
            Condition("rolling_accuracy", Operator.GTE, 80, window=20),
        ],
        priority=10,
        description="Reliable platform-port alternation (80% over 20, 50+ trials)",
    ),

    Transition(
        from_stage="phase_1_rearing",
        to_stage="phase_2_cue_no_punish",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 20),
            Condition("rolling_accuracy", Operator.GTE, 80, window=10),
        ],
        priority=10,
        description="Rearing acquired (80% over 10, 20+ trials)",
    ),

    # -------------------------------------------------------------------------
    # Phase 2: Cue-response training
    # -------------------------------------------------------------------------

    Transition(
        from_stage="phase_2_cue_no_punish",
        to_stage="phase_2_cue_with_punish",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 20),
            Condition("rolling_accuracy", Operator.GTE, 70, window=10),
        ],
        priority=10,
        description="Evidence of understanding cue (70% over 10, 20+ trials)",
    ),

    Transition(
        from_stage="phase_2_cue_with_punish",
        to_stage="phase_3_port3_no_punish",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 30),
            Condition("rolling_accuracy", Operator.GTE, 80, window=20),
        ],
        priority=10,
        description="Reliable cue-response at port 0 (80% over 20, 30+ trials)",
    ),

    # Regression: if punishment tanks performance, go back
    Transition(
        from_stage="phase_2_cue_with_punish",
        to_stage="phase_2_cue_no_punish",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 15),
            Condition("rolling_accuracy", Operator.LT, 30, window=10),
        ],
        priority=5,
        description="Performance regression -- removing punishment temporarily",
    ),

    # -------------------------------------------------------------------------
    # Phase 3: Spatial flexibility
    # -------------------------------------------------------------------------

    Transition(
        from_stage="phase_3_port3_no_punish",
        to_stage="phase_3_port3_with_punish",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 15),
            Condition("rolling_accuracy", Operator.GTE, 70, window=10),
        ],
        priority=10,
        description="Learning port 3 (70% over 10, 15+ trials)",
    ),

    Transition(
        from_stage="phase_3_port3_with_punish",
        to_stage="phase_3_two_ports",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 20),
            Condition("rolling_accuracy", Operator.GTE, 80, window=10),
        ],
        priority=10,
        description="Reliable port 3 responding (80% over 10, 20+ trials)",
    ),

    # Regression: port 3 with punishment not working
    Transition(
        from_stage="phase_3_port3_with_punish",
        to_stage="phase_3_port3_no_punish",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 15),
            Condition("rolling_accuracy", Operator.LT, 30, window=10),
        ],
        priority=5,
        description="Performance regression at port 3 -- removing punishment",
    ),

    Transition(
        from_stage="phase_3_two_ports",
        to_stage="phase_4_three_ports",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 30),
            Condition("rolling_accuracy", Operator.GTE, 80, window=20),
        ],
        priority=10,
        description="Cue-following confirmed with 2 ports (80% over 20, 30+ trials)",
    ),

    # Regression: 2-port alternation failing
    Transition(
        from_stage="phase_3_two_ports",
        to_stage="phase_3_port3_with_punish",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 20),
            Condition("rolling_accuracy", Operator.LT, 40, window=20),
        ],
        priority=5,
        description="Struggling with 2-port alternation -- reverting to single port",
    ),

    # -------------------------------------------------------------------------
    # Phase 4: Generalisation
    # -------------------------------------------------------------------------

    Transition(
        from_stage="phase_4_three_ports",
        to_stage="phase_4_all_ports",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 30),
            Condition("rolling_accuracy", Operator.GTE, 80, window=20),
        ],
        priority=10,
        description="3-port generalisation achieved (80% over 20, 30+ trials)",
    ),

    # Regression: 3 ports too hard
    Transition(
        from_stage="phase_4_three_ports",
        to_stage="phase_3_two_ports",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 20),
            Condition("rolling_accuracy", Operator.LT, 40, window=20),
        ],
        priority=5,
        description="Struggling with 3 ports -- reverting to 2 ports",
    ),

    # Regression: all 6 ports too hard
    Transition(
        from_stage="phase_4_all_ports",
        to_stage="phase_4_three_ports",
        conditions=[
            Condition("trials_in_stage", Operator.GTE, 20),
            Condition("rolling_accuracy", Operator.LT, 40, window=20),
        ],
        priority=5,
        description="Struggling with 6 ports -- reverting to 3 ports",
    ),

]
