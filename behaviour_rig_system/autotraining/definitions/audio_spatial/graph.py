"""
Audio Spatial Autotraining Transition Graph

Defines the edges and conditions for moving between training stages in the
combined visual + spatial audio protocol.

Training path overview:

    scales_training -> combined_single_port -> combined_two_ports_lenient
        -> combined_two_ports -> separated_two_ports
                                       |
                              +--------+---------+
                              |        |         |
                        both >= 80%  vis ok   aud ok
                              |      aud weak  vis weak
                              v        |         |
                     interleaved_6   audio_    visual_
                        _ports       only_     only_
                              |      two_      two_
                              |      ports     ports
                              |        |         |
                              |        +----+----+
                              |             |
                              +<--  >= 80% -+
                              |
                              v
                     cue_duration_1000ms -> 750ms -> 500ms -> 250ms -> 100ms

Transition priorities:
    1:     Warm-up exit
    5-6:   Severe regression rules
    8:     Remedial routing (weaker modality detection)
    10-11: Forward progression
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
    # Phase 1 -> Phase 2: scales_training -> combined_single_port
    # -------------------------------------------------------------------------

    Transition(
        from_stage="scales_training",
        to_stage="combined_single_port",
        conditions=[
            Condition("rolling_trial_duration", "<=", 2.5, window=20),
        ],
        priority=10,
        description="Scales training complete (avg trial time <= 2.5s over 20)",
    ),

    # -------------------------------------------------------------------------
    # Phase 2 -> Phase 3: combined_single_port -> combined_two_ports_lenient
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_single_port",
        to_stage="combined_two_ports_lenient",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=20),
        ],
        priority=10,
        description="Single port combined cue mastered (>=90% over 20)",
    ),

    # Regression: combined_single_port -> scales_training
    Transition(
        from_stage="combined_single_port",
        to_stage="scales_training",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Regression at combined single port (<30% over 20)",
    ),

    # -------------------------------------------------------------------------
    # Phase 3: combined_two_ports_lenient -> combined_two_ports
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_two_ports_lenient",
        to_stage="combined_two_ports",
        conditions=[
            Condition("trials_in_stage", ">=", 30),
        ],
        priority=10,
        description="Lenient phase complete (30 trials), moving to strict",
    ),

    # -------------------------------------------------------------------------
    # Phase 3 -> Phase 4: combined_two_ports -> separated_two_ports
    # -------------------------------------------------------------------------

    Transition(
        from_stage="combined_two_ports",
        to_stage="separated_two_ports",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30),
        ],
        priority=10,
        description="Combined 2-port mastered (>=90% over 30), separating cues",
    ),

    # Regression: combined_two_ports -> combined_single_port
    Transition(
        from_stage="combined_two_ports",
        to_stage="combined_single_port",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20),
        ],
        priority=5,
        description="Regression at combined 2-port (<30% over 20)",
    ),

    # -------------------------------------------------------------------------
    # Phase 4 -> Phase 6: both modalities learned, skip to 6-port
    # (higher priority than remedial routing so it fires first)
    # -------------------------------------------------------------------------

    Transition(
        from_stage="separated_two_ports",
        to_stage="interleaved_6_ports",
        conditions=[
            Condition("rolling_accuracy", ">=", 80, window=20, tracker="visual"),
            Condition("rolling_accuracy", ">=", 80, window=20, tracker="audio"),
        ],
        priority=10,
        description="Both modalities learned (>=80% each over 20), skip to 6-port",
    ),

    # -------------------------------------------------------------------------
    # Phase 4 -> Phase 5: only one modality learned, remedial for the other
    # (lower priority so the "both good" check fires first)
    # -------------------------------------------------------------------------

    # Visual is strong but audio is weak -> audio remedial
    Transition(
        from_stage="separated_two_ports",
        to_stage="audio_only_two_ports",
        conditions=[
            Condition("rolling_accuracy", ">=", 80, window=20, tracker="visual"),
            Condition("rolling_accuracy", "<", 70, window=20, tracker="audio"),
            Condition("trials_in_stage", ">=", 40),
        ],
        priority=11,
        description="Visual learned but audio weak (vis>=80%, aud<70%), audio remedial",
    ),

    # Audio is strong but visual is weak -> visual remedial
    Transition(
        from_stage="separated_two_ports",
        to_stage="visual_only_two_ports",
        conditions=[
            Condition("rolling_accuracy", ">=", 80, window=20, tracker="audio"),
            Condition("rolling_accuracy", "<", 70, window=20, tracker="visual"),
            Condition("trials_in_stage", ">=", 40),
        ],
        priority=11,
        description="Audio learned but visual weak (aud>=80%, vis<70%), visual remedial",
    ),

    # Regression: separated_two_ports -> combined_two_ports
    Transition(
        from_stage="separated_two_ports",
        to_stage="combined_two_ports",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="visual"),
            Condition("rolling_accuracy", "<", 30, window=20, tracker="audio"),
        ],
        priority=5,
        description="Both modalities collapsed (<30% each over 20), back to combined",
    ),

    # -------------------------------------------------------------------------
    # Phase 5 -> Phase 6: remedial complete, advance to 6-port
    # -------------------------------------------------------------------------

    Transition(
        from_stage="visual_only_two_ports",
        to_stage="interleaved_6_ports",
        conditions=[
            Condition("rolling_accuracy", ">=", 80, window=20, tracker="visual"),
        ],
        priority=10,
        description="Visual remedial complete (>=80% over 20), advancing to 6-port",
    ),

    Transition(
        from_stage="audio_only_two_ports",
        to_stage="interleaved_6_ports",
        conditions=[
            Condition("rolling_accuracy", ">=", 80, window=20, tracker="audio"),
        ],
        priority=10,
        description="Audio remedial complete (>=80% over 20), advancing to 6-port",
    ),

    # Regression: remedial stages -> separated_two_ports
    Transition(
        from_stage="visual_only_two_ports",
        to_stage="separated_two_ports",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="visual"),
        ],
        priority=5,
        description="Visual remedial regression (<30% over 20), back to separated",
    ),

    Transition(
        from_stage="audio_only_two_ports",
        to_stage="separated_two_ports",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="audio"),
        ],
        priority=5,
        description="Audio remedial regression (<30% over 20), back to separated",
    ),

    # -------------------------------------------------------------------------
    # Phase 6 -> Phase 7: interleaved_6_ports -> cue_duration_1000ms
    # -------------------------------------------------------------------------

    Transition(
        from_stage="interleaved_6_ports",
        to_stage="cue_duration_1000ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 85, window=30, tracker="visual"),
            Condition("rolling_accuracy", ">=", 85, window=30, tracker="audio"),
        ],
        priority=10,
        description="6-port interleaved mastered (>=85% each over 30), start duration ladder",
    ),

    # Regression: interleaved_6_ports -> separated_two_ports
    Transition(
        from_stage="interleaved_6_ports",
        to_stage="separated_two_ports",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="visual"),
        ],
        priority=5,
        description="Severe visual regression at 6-port (<30% over 20)",
    ),

    Transition(
        from_stage="interleaved_6_ports",
        to_stage="separated_two_ports",
        conditions=[
            Condition("rolling_accuracy", "<", 30, window=20, tracker="audio"),
        ],
        priority=5,
        description="Severe audio regression at 6-port (<30% over 20)",
    ),

    # -------------------------------------------------------------------------
    # Phase 7: Cue duration ladder
    # -------------------------------------------------------------------------

    Transition(
        from_stage="cue_duration_1000ms",
        to_stage="cue_duration_750ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="visual"),
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="audio"),
        ],
        priority=10,
        description="1000ms mastered (>=90% each over 30)",
    ),

    Transition(
        from_stage="cue_duration_750ms",
        to_stage="cue_duration_500ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="visual"),
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="audio"),
        ],
        priority=10,
        description="750ms mastered (>=90% each over 30)",
    ),

    Transition(
        from_stage="cue_duration_500ms",
        to_stage="cue_duration_250ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="visual"),
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="audio"),
        ],
        priority=10,
        description="500ms mastered (>=90% each over 30)",
    ),

    Transition(
        from_stage="cue_duration_250ms",
        to_stage="cue_duration_100ms",
        conditions=[
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="visual"),
            Condition("rolling_accuracy", ">=", 90, window=30, tracker="audio"),
        ],
        priority=10,
        description="250ms mastered (>=90% each over 30)",
    ),

    # Regression: any cue_duration stage -> interleaved_6_ports
    Transition(
        from_stage="cue_duration_1000ms",
        to_stage="interleaved_6_ports",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="visual"),
        ],
        priority=6,
        description="Duration ladder regression (visual <40% over 20), back to continuous",
    ),

    Transition(
        from_stage="cue_duration_1000ms",
        to_stage="interleaved_6_ports",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="audio"),
        ],
        priority=6,
        description="Duration ladder regression (audio <40% over 20), back to continuous",
    ),

    Transition(
        from_stage="cue_duration_750ms",
        to_stage="cue_duration_1000ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="visual"),
        ],
        priority=6,
        description="750ms regression (visual <40%), back to 1000ms",
    ),

    Transition(
        from_stage="cue_duration_750ms",
        to_stage="cue_duration_1000ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="audio"),
        ],
        priority=6,
        description="750ms regression (audio <40%), back to 1000ms",
    ),

    Transition(
        from_stage="cue_duration_500ms",
        to_stage="cue_duration_750ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="visual"),
        ],
        priority=6,
        description="500ms regression (visual <40%), back to 750ms",
    ),

    Transition(
        from_stage="cue_duration_500ms",
        to_stage="cue_duration_750ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="audio"),
        ],
        priority=6,
        description="500ms regression (audio <40%), back to 750ms",
    ),

    Transition(
        from_stage="cue_duration_250ms",
        to_stage="cue_duration_500ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="visual"),
        ],
        priority=6,
        description="250ms regression (visual <40%), back to 500ms",
    ),

    Transition(
        from_stage="cue_duration_250ms",
        to_stage="cue_duration_500ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="audio"),
        ],
        priority=6,
        description="250ms regression (audio <40%), back to 500ms",
    ),

    Transition(
        from_stage="cue_duration_100ms",
        to_stage="cue_duration_250ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="visual"),
        ],
        priority=6,
        description="100ms regression (visual <40%), back to 250ms",
    ),

    Transition(
        from_stage="cue_duration_100ms",
        to_stage="cue_duration_250ms",
        conditions=[
            Condition("rolling_accuracy", "<", 40, window=20, tracker="audio"),
        ],
        priority=6,
        description="100ms regression (audio <40%), back to 250ms",
    ),

]
