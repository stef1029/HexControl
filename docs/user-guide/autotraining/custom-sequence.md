# Creating a Custom Training Sequence

This tutorial walks through creating a new autotraining sequence from scratch -- from defining stages and transitions to wiring it into a protocol.

## 1. Create the definitions folder

```
autotraining/definitions/
├── audio/                # Existing
├── visual/               # Existing
└── my_training/          # New!
    ├── __init__.py
    ├── stages.py
    └── graph.py
```

## 2. Define stages (stages.py)

Create your stage definitions. Each stage only overrides what differs from `BASE_DEFAULTS`:

```python
"""My custom training stages."""

from ...stage import Stage

STAGES: dict[str, Stage] = {}

def _register(stage: Stage) -> Stage:
    STAGES[stage.name] = stage
    return stage

# Warm-up: easy single-port task
_register(Stage(
    name="warm_up",
    display_name="Warm-Up",
    description="Quick warm-up to get the mouse engaged.",
    is_warmup=True,
    overrides={
        "port_0_enabled": True,
        "response_timeout": 30.0,
    },
))

# Stage 1: Learn port 0
_register(Stage(
    name="stage_1_single_port",
    display_name="Stage 1: Single Port",
    description="Mouse learns to go to port 0 for reward.",
    overrides={
        "port_0_enabled": True,
        "response_timeout": 20.0,
    },
))

# Stage 2: Two ports
_register(Stage(
    name="stage_2_two_ports",
    display_name="Stage 2: Two Ports",
    description="Cue alternates between ports 0 and 2.",
    overrides={
        "port_0_enabled": True,
        "port_2_enabled": True,
        "punishment_enabled": True,
        "punishment_duration": 5.0,
        "response_timeout": 15.0,
    },
))

# Stage 3: All ports
_register(Stage(
    name="stage_3_all_ports",
    display_name="Stage 3: All Ports",
    description="Full 6-port randomisation. Final stage.",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "punishment_enabled": True,
        "punishment_duration": 5.0,
        "response_timeout": 10.0,
    },
))
```

!!! important
    Register stages in order from earliest to latest. This ordering is used by the `warmup_after` gate logic.

## 3. Define transitions (graph.py)

Create your transition rules:

```python
"""My custom training transition graph."""

from ...transitions import Transition, Condition

TRANSITIONS: list[Transition] = [

    # Warm-up exit
    Transition(
        from_stage="warm_up",
        to_stage="$saved",
        conditions=[
            Condition("consecutive_correct", ">=", 3),
            Condition("trials_in_stage", ">=", 5),
        ],
        priority=1,
        description="Warm-up complete",
    ),

    # Stage 1 -> Stage 2
    Transition(
        from_stage="stage_1_single_port",
        to_stage="stage_2_two_ports",
        conditions=[
            Condition("trials_in_stage", ">=", 30),
            Condition("rolling_accuracy", ">=", 80, window=15),
        ],
        priority=10,
        description="Single port mastered (80% over 15, 30+ trials)",
    ),

    # Stage 2 -> Stage 3
    Transition(
        from_stage="stage_2_two_ports",
        to_stage="stage_3_all_ports",
        conditions=[
            Condition("trials_in_stage", ">=", 40),
            Condition("rolling_accuracy", ">=", 75, window=20),
        ],
        priority=10,
        description="Two-port discrimination (75% over 20, 40+ trials)",
    ),

    # Regression: Stage 2 too hard
    Transition(
        from_stage="stage_2_two_ports",
        to_stage="stage_1_single_port",
        conditions=[
            Condition("trials_in_stage", ">=", 20),
            Condition("rolling_accuracy", "<", 35, window=15),
        ],
        priority=5,
        description="Struggling with two ports -- reverting to single",
    ),

    # Regression: Stage 3 too hard
    Transition(
        from_stage="stage_3_all_ports",
        to_stage="stage_2_two_ports",
        conditions=[
            Condition("trials_in_stage", ">=", 20),
            Condition("rolling_accuracy", "<", 35, window=20),
        ],
        priority=5,
        description="Struggling with all ports -- reverting to two",
    ),
]
```

## 4. Create the `__init__.py`

```python
"""My custom training definitions."""

from .stages import STAGES
from .graph import TRANSITIONS

__all__ = ["STAGES", "TRANSITIONS"]
```

## 5. Create the protocol

Create a new protocol file in `protocols/` (e.g. `my_autotraining.py`):

```python
"""My Custom Autotraining Protocol."""

import os
import random
from datetime import datetime

from autotraining.definitions.my_training.graph import TRANSITIONS
from autotraining.definitions.my_training.stages import STAGES
from autotraining.engine import AutotrainingEngine
from autotraining.persistence import (
    append_transition_log,
    load_training_state,
    save_training_state,
)
from core.parameter_types import BoolParameter, StringParameter
from core.performance_tracker import TrackerDefinition
from core.protocol_base import BaseProtocol


class MyAutoTrainingProtocol(BaseProtocol):
    """Custom autotraining with 3 stages."""

    @classmethod
    def get_name(cls) -> str:
        return "My Autotraining"

    @classmethod
    def get_description(cls) -> str:
        return "Custom autotraining: single port -> two ports -> all ports."

    @classmethod
    def get_tracker_definitions(cls) -> list:
        # One tracker per stage for separate performance tabs
        return [
            TrackerDefinition(name=s.name, display_name=s.display_name)
            for s in STAGES.values()
        ]

    @classmethod
    def get_parameters(cls) -> list:
        return [
            BoolParameter(
                name="skip_warmup",
                display_name="Skip Warm-Up",
                default=False,
            ),
            StringParameter(
                name="start_stage_override",
                display_name="Override Start Stage (blank = use saved)",
                default="",
            ),
            StringParameter(
                name="progress_folder_override",
                display_name="Progress Folder Override (blank = default)",
                default="",
            ),
        ]

    def _run_protocol(self) -> None:
        params = self.parameters
        scales = self.scales
        perf_trackers = self.perf_trackers

        if scales is None:
            self.log("ERROR: Scales not available!")
            return

        for tracker in perf_trackers.values():
            tracker.reset()

        num_trials = params["num_trials"]
        mouse_id = params.get("mouse_id", "unknown")
        save_directory = params.get("save_directory", "")
        progress_override = params.get("progress_folder_override", "").strip()
        progress_folder = progress_override if progress_override else os.path.join(
            save_directory, "autotraining_progress"
        )
        start_override = params.get("start_stage_override", "").strip()

        # Find default first stage (first non-warmup)
        default_first = next(
            (s.name for s in STAGES.values() if not s.is_warmup), ""
        )

        # Load saved state
        saved_state = load_training_state(progress_folder, mouse_id, default_first)

        if start_override and start_override in STAGES:
            saved_stage = start_override
            saved_trials = 0
        else:
            saved_stage = saved_state.current_stage or default_first
            saved_trials = saved_state.trials_in_stage

        # Create engine
        engine = AutotrainingEngine(
            stages=STAGES,
            transitions=TRANSITIONS,
            saved_stage_name=saved_stage,
            saved_trials_in_stage=saved_trials,
        )
        engine.initialise_session(
            perf_trackers=perf_trackers,
            log=self.log,
            skip_warmup=params.get("skip_warmup", False),
        )

        session_start = self.now()
        trial_num = 0

        try:
            while True:
                if num_trials > 0 and trial_num >= num_trials:
                    break
                if self.check_stop():
                    break

                stage_params = engine.get_active_params()

                # --- Your trial logic here ---
                # Use stage_params for port selection, timeouts, etc.
                # Record outcomes with the stage-specific tracker
                # Call engine.on_trial_complete() after each trial

                # Example: (replace with your actual trial logic)
                enabled_ports = [
                    i for i in range(6)
                    if stage_params.get(f"port_{i}_enabled", False)
                ]
                target_port = random.choice(enabled_ports or [0])

                # ... run trial, get outcome ...

                trial_num += 1
                tracker = perf_trackers.get(engine.current_stage_name)

                # Report outcome to engine
                engine.on_trial_complete(
                    outcome="success",  # or "failure" or "timeout"
                    correct_port=target_port,
                    chosen_port=target_port,
                    trial_duration=1.0,
                )

        finally:
            # Save training state
            end_state = engine.get_session_end_state()
            if not end_state.get("in_warmup", False):
                save_training_state(
                    progress_root=progress_folder,
                    mouse_id=mouse_id,
                    current_stage=end_state["current_stage"],
                    trials_in_stage=end_state["trials_in_stage"],
                    previous_state=saved_state,
                    transition_log=engine.get_transition_log(),
                )

            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            transition_log = engine.get_transition_log()
            if transition_log:
                append_transition_log(
                    progress_folder, mouse_id, session_id, transition_log
                )
```

## 6. Test it

1. Launch the system with **Simulate** enabled
2. Select your new protocol tab
3. Run a session -- verify that stages transition correctly
4. Check the `autotraining_progress/` folder for saved state

!!! tip
    Use simulation with accelerated time (`BehaviourClock`) to run through the full training sequence quickly and verify all transitions fire at the right thresholds.

## Checklist

- [ ] Stages registered in progression order
- [ ] Warm-up stage has `is_warmup=True`
- [ ] Every forward transition has a matching regression transition
- [ ] Regression thresholds are well below forward thresholds (prevents oscillation)
- [ ] All transitions have `trials_in_stage >= N` to prevent premature firing
- [ ] Protocol saves state in `finally` block (runs even on error/stop)
- [ ] Protocol skips state save if session ended during warm-up
