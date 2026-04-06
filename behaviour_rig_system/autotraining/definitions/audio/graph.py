"""
Audio Autotraining Transition Graph

Defines the edges and conditions for moving between training stages in the
audio/visual interleaved protocol.

Stages share the same visual introduction path (phases 1-4) as the visual
protocol, then branch into audio training at 6-port mastery.

Transition priorities:
    0-4:   Global/emergency rules (apply from any stage)
    5-6:   Severe regression rules (<30% accuracy)
    7-8:   Moderate regression rules (<50% accuracy)
    10-19: Forward progression rules (the main training path)

Audio branch graph (after multiple_leds_6x):

    multiple_leds_6x ──(>=90%)──> audio_only ──(>=90%)──> interleaved_2_6
                                     ^                         │
                                     │                    (target stage)
                                     │                    ┌────┼────┐
                                     │               <50% audio  <50% visual
                                     │                    │         │
                                     │             interleaved_3_6  interleaved_1_6
                                     │                    │         │
                                     │              (>=60% audio)  (>=60% visual)
                                     │                    └────┬────┘
                                     │                         │
                                     │                  back to interleaved_2_6
                                     │
                              <30% audio from any interleaved
                              <30% visual ──> visual_only_remedial ──(>=90%)──┘
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
    # Forward: scales_training -> introduce_1_led_no_wait
    # -------------------------------------------------------------------------

    Transition(
        from_stage="scales_training",
        to_stage="introduce_1_led_no_wait",
        conditions=[
            Condition("rolling_trial_duration", "<=", 2.5, window=20),
        ],
        priority=10,
        description="Scales training complete (average trial time <= 2.5s over 20 trials)",
    ),

    # -------------------------------------------------------------------------
    # Forward: visual introduction path (phases 1-4)
    # -------------------------------------------------------------------------

    Transition(
        from_stage="introduce_1_led_no_wait",
        to_stage="introduce_1_led",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20),
        ],
        priority=10,
        description="Single LED mastered (>90% over 20 trials), adding platform wait",
    ),

    # -------------------------------------------------------------------------
    # Regression: introduce_1_led_no_wait -> scales_training
    # -------------------------------------------------------------------------

    Transition(
        from_stage="introduce_1_led_no_wait",
        to_stage="scales_training",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Performance regression at 1 LED no wait (<30% over 20 trials), back to scales",
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
    # Regression: visual introduction path
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
    # Forward: audio branch — 6-port mastery -> pure audio -> interleaved
    # -------------------------------------------------------------------------

    Transition(
        from_stage="multiple_leds_6x",
        to_stage="audio_only",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30),
        ],
        priority=10,
        description="6-port mastered (>=90% over 30 trials), entering audio training",
    ),

    Transition(
        from_stage="audio_only",
        to_stage="interleaved_2_6",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20, tracker="audio"),
        ],
        priority=10,
        description="Audio mastered (>=90% over 20 trials), entering interleaved 2:5",
    ),

    # -------------------------------------------------------------------------
    # Severe regression from interleaved_2_6: <30% in either trial type
    # (higher priority than moderate regressions)
    # -------------------------------------------------------------------------

    Transition(
        from_stage="interleaved_2_6",
        to_stage="audio_only",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="audio"),
        ],
        priority=5,
        description="Severe audio regression in 2:5 (<30% audio over 20), back to audio only",
    ),

    Transition(
        from_stage="interleaved_2_6",
        to_stage="visual_only_remedial",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="visual"),
        ],
        priority=5,
        description="Severe visual regression in 2:5 (<30% visual over 20), to visual remedial",
    ),

    # -------------------------------------------------------------------------
    # Moderate regression from interleaved_2_6: <50% in either trial type
    # -------------------------------------------------------------------------

    Transition(
        from_stage="interleaved_2_6",
        to_stage="interleaved_3_6",
        conditions=[
            Condition("rolling_accuracy", "<", 50, window=20, tracker="audio"),
        ],
        priority=7,
        description="Audio struggling in 2:5 (<50% audio over 20), increasing audio proportion",
    ),

    Transition(
        from_stage="interleaved_2_6",
        to_stage="interleaved_1_6",
        conditions=[
            Condition("rolling_accuracy", "<", 50, window=20, tracker="visual"),
        ],
        priority=7,
        description="Visual struggling in 2:5 (<50% visual over 20), decreasing audio proportion",
    ),

    # -------------------------------------------------------------------------
    # Forward: return from interleaved remedial stages -> interleaved_2_6
    # -------------------------------------------------------------------------

    Transition(
        from_stage="interleaved_3_6",
        to_stage="interleaved_2_6",
        conditions=[
            Condition("rolling_accuracy", ">=", 60, window=20, tracker="audio"),
        ],
        priority=10,
        description="Audio recovered in 3:5 (>=60% audio over 20), returning to 2:5",
    ),

    Transition(
        from_stage="interleaved_1_6",
        to_stage="interleaved_2_6",
        conditions=[
            Condition("rolling_accuracy", ">=", 60, window=20, tracker="visual"),
        ],
        priority=10,
        description="Visual recovered in 1:5 (>=60% visual over 20), returning to 2:5",
    ),

    # -------------------------------------------------------------------------
    # Severe regression from interleaved_3_6 and interleaved_1_6
    # -------------------------------------------------------------------------

    Transition(
        from_stage="interleaved_3_6",
        to_stage="audio_only",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="audio"),
        ],
        priority=5,
        description="Severe audio regression in 3:5 (<30% audio over 20), back to audio only",
    ),

    Transition(
        from_stage="interleaved_1_6",
        to_stage="visual_only_remedial",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="visual"),
        ],
        priority=5,
        description="Severe visual regression in 1:5 (<30% visual over 20), to visual remedial",
    ),

    # -------------------------------------------------------------------------
    # Forward: return from pure remedial stages -> interleaved_2_6
    # -------------------------------------------------------------------------

    Transition(
        from_stage="visual_only_remedial",
        to_stage="interleaved_2_6",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20, tracker="visual"),
        ],
        priority=10,
        description="Visual remedial mastered (>=90% over 20), returning to interleaved 2:5",
    ),

]
