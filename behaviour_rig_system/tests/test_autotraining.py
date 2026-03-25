"""Quick smoke test for the autotraining engine."""
import sys
from pathlib import Path

# Ensure behaviour_rig_system/ is on sys.path regardless of cwd
_PROJECT_DIR = Path(__file__).resolve().parent.parent  # behaviour_rig_system/
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from autotraining.engine import AutotrainingEngine
from autotraining.definitions.visual.stages import STAGES
from autotraining.definitions.visual.graph import TRANSITIONS
from core.performance_tracker import PerformanceTracker

# Create a tracker and engine (fresh mouse, no saved state)
tracker = PerformanceTracker()
tracker.reset()

engine = AutotrainingEngine(STAGES, TRANSITIONS)
logs = []
engine.initialise_session({"warm_up": tracker}, lambda msg: logs.append(msg))

print(f"Started in: {engine.current_stage_name} (warmup={engine.in_warmup})")

# Simulate 15 successful warm-up trials
for i in range(15):
    tracker.success(correct_port=0, trial_duration=1.0)
    result = engine.on_trial_complete("success", 0, 0, 1.0)
    if result:
        print(f"  Trial {i+1}: transitioned to {result}")

print(f"After warm-up: {engine.current_stage_name} (warmup={engine.in_warmup})")

# Simulate progress through phase 1a (50+ trials, 80%+ accuracy)
for i in range(60):
    if i % 5 == 0:
        tracker.failure(correct_port=0, chosen_port=1, trial_duration=1.0)
        engine.on_trial_complete("failure", 0, 1, 1.0)
    else:
        tracker.success(correct_port=0, trial_duration=1.0)
        result = engine.on_trial_complete("success", 0, 0, 1.0)
        if result:
            print(f"  Phase 1a trial {i+1}: transitioned to {result}")
            break

print(f"After phase 1a: {engine.current_stage_name}")

# Print transition log
print(f"\nTransition log ({len(engine.get_transition_log())} transitions):")
for t in engine.get_transition_log():
    print(f"  {t['from_stage']} -> {t['to_stage']}: {t['trigger']}")

# Test persistence
from autotraining.persistence import load_training_state, save_training_state
import tempfile, os

with tempfile.TemporaryDirectory() as tmpdir:
    state = load_training_state(tmpdir, "TEST_MOUSE", "phase_1_platform_reward")
    print(f"\nFresh state: stage={state.current_stage}, trials={state.trials_in_stage}")

    end_state = engine.get_session_end_state()
    save_training_state(tmpdir, "TEST_MOUSE", end_state["current_stage"], end_state["trials_in_stage"], state)

    state2 = load_training_state(tmpdir, "TEST_MOUSE")
    print(f"Saved state: stage={state2.current_stage}, trials={state2.trials_in_stage}")
    print(f"History: {state2.stage_history}")

print("\n=== ALL TESTS PASSED ===")
