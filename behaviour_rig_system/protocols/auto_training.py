"""
Training Autotraining Protocol

An adaptive training protocol that automatically progresses mice through
a sequence of training stages based on performance. This file is a standard
function-based protocol that the main system discovers and loads like any
other protocol in the protocols/ folder.

Internally it uses the autotraining engine to:
  1. Load the mouse's saved training stage from the previous session
  2. Run a warm-up phase at session start
  3. Execute the main trial loop with the current stage's parameters
  4. Evaluate transition rules after each trial and switch stages as needed
  5. Save the mouse's progress at session end

The trial loop itself is very similar to full_task_with_wait.py — the key
difference is that parameters are read from the engine's active params
(which can change mid-session) rather than being frozen at startup.
"""

import time
import random
from datetime import datetime
from pathlib import Path

# Autotraining system imports
from autotraining.engine import AutotrainingEngine
from autotraining.persistence import (
    load_training_state,
    save_training_state,
    append_transition_log,
)
from autotraining.definitions.stages import STAGES
from autotraining.definitions.graph import TRANSITIONS

# Try to import speaker enums from BehavLink
try:
    from BehavLink import SpeakerFrequency, SpeakerDuration
    SPEAKER_AVAILABLE = True
except ImportError:
    SPEAKER_AVAILABLE = False
    class SpeakerFrequency:
        FREQ_3300_HZ = 4
    class SpeakerDuration:
        DURATION_500_MS = 4
        CONTINUOUS = 7


# =============================================================================
# Protocol metadata (discovered by protocol loader)
# =============================================================================

NAME = "Autotraining"
DESCRIPTION = (
    "Adaptive training protocol. Automatically progresses through training "
    "stages based on mouse performance. Saves progress between sessions."
)

PARAMETERS = {
    # Autotraining progress folder --- where training state is saved/loaded
    "progress_folder": {
        "default": "D:\\behaviour_data\\autotraining_progress",
        "label": "Autotraining Progress Folder",
    },
    # Manual stage override — empty string means use saved state
    "start_stage_override": {
        "default": "",
        "label": "Override Start Stage (blank = use saved)",
    },
    # Platform settings (common across all stages, set per-session)
    "weight_offset": {
        "default": 3.0,
        "label": "Weight Threshold Offset (g)",
        "min": 0.0,
        "max": 10.0,
    },
    "platform_settle_time": {
        "default": 1,
        "label": "Platform Settle Time (s)",
        "min": 0,
        "max": 5,
    },
    # Global settings
    "led_brightness": {
        "default": 255,
        "label": "LED Brightness (0-255)",
        "min": 0,
        "max": 255,
    },
    "reward_duration": {
        "default": 500,
        "label": "Reward Duration (ms)",
        "min": 50,
        "max": 5000,
    },
    "iti": {
        "default": 1.0,
        "label": "Inter-Trial Interval (s)",
        "min": 0.0,
        "max": 10.0,
    },
}


# =============================================================================
# Main run function
# =============================================================================

def run(link, params, log, check_abort, scales, perf_tracker):
    """
    Main entry point — called by the protocol framework.

    This function:
      1. Sets up the autotraining engine with the mouse's saved state
      2. Runs the warm-up + main training loop
      3. Saves progress on exit
    """
    if scales is None:
        log("ERROR: Scales not available!")
        return

    # ─── Extract session-level params ────────────────────────────────────
    mouse_weight = params["mouse_weight"]
    num_trials = params["num_trials"]  # 0 = unlimited
    mouse_id = params.get("mouse_id", "unknown")

    progress_folder = params.get("progress_folder", "D:\\behaviour_data\\autotraining_progress")
    start_override = params.get("start_stage_override", "").strip()

    # Session-level params that override stage defaults
    session_overrides = {
        "weight_offset": params["weight_offset"],
        "platform_settle_time": params["platform_settle_time"],
        "led_brightness": params["led_brightness"],
        "reward_duration": params["reward_duration"],
        "iti": params["iti"],
    }

    weight_threshold = mouse_weight - session_overrides["weight_offset"]

    # ─── Load saved training state ───────────────────────────────────────

    # Determine the default first stage (first non-warmup stage)
    default_first_stage = ""
    for s in STAGES.values():
        if not s.is_warmup:
            default_first_stage = s.name
            break

    saved_state = load_training_state(progress_folder, mouse_id, default_first_stage)

    # Handle manual override
    if start_override and start_override in STAGES:
        saved_stage = start_override
        saved_trials = 0
        log(f"Manual stage override: {start_override}")
    else:
        saved_stage = saved_state.current_stage or default_first_stage
        saved_trials = saved_state.trials_in_stage

    log(f"Mouse: {mouse_id}")
    log(f"Saved stage: {saved_stage} ({saved_trials} trials accumulated)")
    log(f"Progress folder: {progress_folder}")

    # ─── Create autotraining engine ────────────────────────────────────────

    engine = AutotrainingEngine(
        stages=STAGES,
        transitions=TRANSITIONS,
        saved_stage_name=saved_stage,
        saved_trials_in_stage=saved_trials,
    )

    engine.initialise_session(perf_tracker, log)

    # ─── Main trial loop ────────────────────────────────────────────────

    session_start = time.time()
    trial_num = 0

    try:
        while True:
            # Check trial limit
            if num_trials > 0 and trial_num >= num_trials:
                log(f"Completed {num_trials} trials")
                break

            if check_abort():
                log("Aborted by user")
                break

            # Get current stage params + apply session overrides
            stage_params = engine.get_active_params()
            stage_params.update(session_overrides)

            # Extract trial parameters from the (possibly updated) stage
            response_timeout = stage_params["response_timeout"]
            wait_duration = stage_params["wait_duration"]
            iti = stage_params["iti"]
            cue_duration = stage_params["cue_duration"]
            led_brightness = stage_params["led_brightness"]
            reward_ms = stage_params["reward_duration"]
            punishment_s = stage_params["punishment_duration"]
            punishment_enabled = stage_params.get("punishment_enabled", False)
            platform_settle_time = stage_params["platform_settle_time"]

            # Build enabled port list from current stage
            enabled_ports = []
            for i in range(6):
                if stage_params.get(f"port_{i}_enabled", False):
                    enabled_ports.append(i)

            if not enabled_ports:
                log(f"WARNING: No ports enabled in stage {engine.current_stage_name}, using port 0")
                enabled_ports = [0]

            # ─── Wait for mouse on platform ──────────────────────────

            platform_ready = False
            while not check_abort() and not platform_ready:
                weight = scales.get_weight()
                if weight is not None and weight > weight_threshold:
                    settle_start = time.time()
                    settled = True

                    while time.time() - settle_start < platform_settle_time:
                        if check_abort():
                            break
                        weight = scales.get_weight()
                        if weight is None or weight < weight_threshold:
                            settled = False
                            break
                        time.sleep(0.02)

                    if settled and not check_abort():
                        weight = scales.get_weight()
                        if weight is not None and weight > weight_threshold:
                            platform_ready = True
                else:
                    time.sleep(0.05)

            if check_abort():
                break

            trial_num += 1

            # ─── Select target port ──────────────────────────────────

            target_port = random.choice(enabled_ports)

            # ─── Wait period (rearing stand-in) ──────────────────────

            wait_complete = False
            activation_time = time.time()

            while not check_abort():
                elapsed = time.time() - activation_time
                weight = scales.get_weight()
                if weight is None or weight < weight_threshold:
                    log(f"  Mouse left platform during wait period")
                    break
                if elapsed >= wait_duration:
                    wait_complete = True
                    break
                time.sleep(0.02)

            if check_abort():
                break

            if not wait_complete:
                trial_num -= 1
                time.sleep(iti)
                continue

            # ─── Present cue ─────────────────────────────────────────

            perf_tracker.stimulus(target_port)
            trial_start_time = time.time()

            link.led_set(target_port, led_brightness)

            # ─── Wait for response ───────────────────────────────────

            cue_on = True
            event = None

            while True:
                if check_abort():
                    break

                elapsed = time.time() - trial_start_time

                # Turn off cue after cue_duration (if limited)
                if cue_on and cue_duration > 0 and elapsed >= cue_duration:
                    link.led_set(target_port, 0)
                    cue_on = False

                # Check timeout
                if elapsed >= response_timeout:
                    break

                # Poll for event
                remaining = response_timeout - elapsed
                event = link.wait_for_event(timeout=min(0.1, remaining))
                if event is not None:
                    break

            trial_duration = time.time() - trial_start_time

            # Turn off LED if still on
            if cue_on:
                link.led_set(target_port, 0)

            # ─── Process response ────────────────────────────────────

            outcome = "timeout"
            chosen_port = None

            if check_abort():
                break

            if event is None:
                # Timeout
                perf_tracker.timeout(correct_port=target_port, trial_duration=trial_duration)
                outcome = "timeout"
                log(f"  [{engine.current_stage_display}] T{trial_num} TIMEOUT ({response_timeout:.0f}s)")

            elif event.port == target_port:
                # Correct
                perf_tracker.success(correct_port=target_port, trial_duration=trial_duration)
                link.valve_pulse(target_port, reward_ms)
                outcome = "success"
                chosen_port = event.port
                log(f"  [{engine.current_stage_display}] T{trial_num} SUCCESS port {event.port} ({trial_duration:.1f}s)")

            else:
                # Incorrect
                perf_tracker.failure(
                    correct_port=target_port,
                    chosen_port=event.port,
                    trial_duration=trial_duration,
                )
                outcome = "failure"
                chosen_port = event.port
                log(f"  [{engine.current_stage_display}] T{trial_num} FAILURE port {event.port} (expected {target_port})")

                # Punishment
                if punishment_enabled and punishment_s > 0:
                    link.spotlight_set(255, 255)
                    time.sleep(punishment_s)
                    link.spotlight_set(255, 0)

            # ─── Notify engine and check for stage transition ────────

            new_stage = engine.on_trial_complete(
                outcome=outcome,
                correct_port=target_port,
                chosen_port=chosen_port,
                trial_duration=trial_duration,
            )

            if new_stage is not None:
                # Stage changed — log summary stats
                log(f"    Rolling accuracy: {perf_tracker.rolling_accuracy(10):.0f}% (last 10)")
                log(f"    Now entering: {engine.current_stage_display}")

            # ─── Inter-trial interval ────────────────────────────────

            if not check_abort() and iti > 0:
                time.sleep(iti)

    finally:
        # ─── Save training progress ──────────────────────────────────────

        end_state = engine.get_session_end_state()

        # Don't save if we're still in warm-up (mouse didn't complete it)
        if not end_state.get("in_warmup", False):
            save_training_state(
                progress_root=progress_folder,
                mouse_id=mouse_id,
                current_stage=end_state["current_stage"],
                trials_in_stage=end_state["trials_in_stage"],
                previous_state=saved_state,
            )
            log(f"Training state saved: stage={end_state['current_stage']}, "
                f"trials={end_state['trials_in_stage']}")
        else:
            log("Session ended during warm-up — training state NOT updated")

        # Save transition log
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        transition_log = engine.get_transition_log()
        if transition_log:
            append_transition_log(progress_folder, mouse_id, session_id, transition_log)
            log(f"Logged {len(transition_log)} stage transition(s)")

        session_duration = (time.time() - session_start) / 60.0
        log(f"Session complete: {trial_num} trials in {session_duration:.1f} minutes")
