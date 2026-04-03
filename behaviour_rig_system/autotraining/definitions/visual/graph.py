"""
Visual Autotraining Transition Graph

Defines the edges and conditions for moving between training stages.
Transitions are evaluated after every trial, in priority order (lowest first).

The special target "$saved" means "go to the mouse's persisted stage from
last session" -- used exclusively by the warm-up exit transition.

Transition priorities:
    0-4:   Global/emergency rules (apply from any stage)
    5-9:   Regression rules (falling back to easier stages)
    10-19: Forward progression rules (the main training path)
"""

from ...transitions import Transition, Condition


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
            Condition("consecutive_correct", ">=", 5),
            Condition("trials_in_stage", ">=", 10),
        ],
        priority=1,
        description="Warm-up complete (5 consecutive correct, 10+ trials)",
    ),

    # -------------------------------------------------------------------------
    # Forward: introduce_1_led -> introduce_another_led -> multiple_leds_2x -> multiple_leds_6x
    # -------------------------------------------------------------------------

    Transition(
        from_stage="introduce_1_led_no_wait",
        to_stage="introduce_1_led",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20),
        ],
        priority=10,
        description="Single LED mastered (>90% over 20 trials), move to adding wait on platform time",
    ),

    Transition(
        from_stage="introduce_1_led",
        to_stage="introduce_another_led_lenient",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30),
        ],
        priority=10,
        description="Single LED mastered (>90% over 30 trials), move to lenient 2nd port",
    ),

    Transition(
        from_stage="introduce_another_led_lenient",
        to_stage="introduce_another_led",
        conditions=[
            Condition("trials_in_stage", ">=", 30),
        ],
        priority=10,
        description="Lenient 2nd port complete (30 trials), move to strict 2nd port",
    ),

    Transition(
        from_stage="introduce_another_led",
        to_stage="multiple_leds_2x",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20),
        ],
        priority=10,
        description="Second LED mastered (>90% over 20 trials)",
    ),

    Transition(
        from_stage="multiple_leds_2x",
        to_stage="multiple_leds_6x",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30),
        ],
        priority=10,
        description="2-port discrimination mastered (>90% over 30 trials)",
    ),

    # -------------------------------------------------------------------------
    # Regression
    # -------------------------------------------------------------------------

    Transition(
        from_stage="introduce_1_led",
        to_stage="introduce_1_led_no_wait",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Performance regression at scales wait training (<30% over 20 trials)",
    ),

    Transition(
        from_stage="introduce_another_led",
        to_stage="introduce_1_led",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Performance regression at second LED (<30% over 20 trials)",
    ),

    Transition(
        from_stage="multiple_leds_2x",
        to_stage="introduce_another_led",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Performance regression at 2-port (<30% over 20 trials)",
    ),

    Transition(
        from_stage="multiple_leds_6x",
        to_stage="multiple_leds_2x",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Performance regression at 6-port (<30% over 20 trials)",
    ),

    # -------------------------------------------------------------------------
    # Forward: cue duration ladder
    # multiple_leds_6x -> 1000ms -> 750ms -> 500ms -> 250ms -> 100ms
    # -------------------------------------------------------------------------

    Transition(
        from_stage="multiple_leds_6x",
        to_stage="cue_duration_1000ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30),
        ],
        priority=10,
        description="6-port mastered, beginning cue duration ladder (>90% over 30 trials)",
    ),

    Transition(
        from_stage="cue_duration_1000ms",
        to_stage="cue_duration_750ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 75, window=30),
        ],
        priority=10,
        description="1000ms cue mastered (>=75% over 30 trials)",
    ),

    Transition(
        from_stage="cue_duration_750ms",
        to_stage="cue_duration_500ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 60, window=30),
        ],
        priority=10,
        description="750ms cue mastered (>=60% over 30 trials)",
    ),

    Transition(
        from_stage="cue_duration_500ms",
        to_stage="cue_duration_250ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 50, window=30),
        ],
        priority=10,
        description="500ms cue mastered (>=50% over 30 trials)",
    ),

    Transition(
        from_stage="cue_duration_250ms",
        to_stage="cue_duration_100ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 40, window=30),
        ],
        priority=10,
        description="250ms cue mastered (>=40% over 30 trials)",
    ),

    # -------------------------------------------------------------------------
    # Regression: cue duration ladder
    # -------------------------------------------------------------------------

    Transition(
        from_stage="cue_duration_1000ms",
        to_stage="multiple_leds_6x",
        conditions=[
            Condition("rolling_accuracy", "<", 25, window=20),
        ],
        priority=5,
        description="Regression at 1000ms cue (<25% over 20 trials)",
    ),

    Transition(
        from_stage="cue_duration_750ms",
        to_stage="cue_duration_1000ms",
        conditions=[
            Condition("rolling_accuracy", "<", 25, window=20),
        ],
        priority=5,
        description="Regression at 750ms cue (<25% over 20 trials)",
    ),

    Transition(
        from_stage="cue_duration_500ms",
        to_stage="cue_duration_750ms",
        conditions=[
            Condition("rolling_accuracy", "<", 25, window=20),
        ],
        priority=5,
        description="Regression at 500ms cue (<25% over 20 trials)",
    ),

    Transition(
        from_stage="cue_duration_250ms",
        to_stage="cue_duration_500ms",
        conditions=[
            Condition("rolling_accuracy", "<", 25, window=20),
        ],
        priority=5,
        description="Regression at 250ms cue (<25% over 20 trials)",
    ),

    Transition(
        from_stage="cue_duration_100ms",
        to_stage="cue_duration_250ms",
        conditions=[
            Condition("rolling_accuracy", "<", 20, window=20),
        ],
        priority=5,
        description="Regression at 100ms cue (<20% over 20 trials)",
    ),

]
