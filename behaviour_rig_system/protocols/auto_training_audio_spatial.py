"""
Audio Spatial Autotraining Protocol

Adaptive protocol that trains mice to respond to combined visual (LED) +
spatial audio (white noise) cues at individual ports. Mirrors the visual
autotraining introduction sequence but with simultaneous LED + noise cues.
Autotraining ends at 2-port discrimination with combined cues.

All stages use cue_type="combined" (LED + noise on the same port).
"""

import os
import random
from datetime import datetime

from autotraining.definitions.audio_spatial.graph import TRANSITIONS
from autotraining.definitions.audio_spatial.stages import STAGES
from autotraining.engine import AutotrainingEngine
from autotraining.persistence import (
    append_transition_log,
    load_training_state,
    save_training_state,
)
from core.parameter_types import BoolParameter, StringParameter
from core.protocol_base import BaseProtocol
from core.tracker import TrackerDefinition, Trial


class AudioSpatialAutoTrainingProtocol(BaseProtocol):
    """Adaptive combined visual + spatial audio training with persistent stage progression."""

    @classmethod
    def get_name(cls) -> str:
        return "Autotraining (Audio Spatial)"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Audio spatial autotraining protocol. Trains mice on combined visual "
            "(LED) + spatial audio (white noise) cues presented simultaneously. "
            "Mirrors the visual autotraining introduction sequence and ends at "
            "2-port discrimination."
        )

    @classmethod
    def get_tracker_definitions(cls) -> dict:
        return {
            stage.name: TrackerDefinition(name=stage.name, display_name=stage.display_name)
            for stage in STAGES.values()
        }

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
                display_name="Progress Folder Override (blank = use cohort folder)",
                default="",
            ),
        ]

    def _setup(self) -> None:
        self.link.ir_set(255)
        self.log("IR illuminator ON (100%)")

    def _cleanup(self) -> None:
        self.link.noise_set(255, False)
        self.link.ir_set(0)

    def _run_protocol(self) -> None:
        params = self.parameters
        scales = self.scales
        trackers = self.trackers

        if scales is None:
            self.log("ERROR: Scales not available!")
            return

        for tracker in trackers.values():
            tracker.reset()

        num_trials = params["num_trials"]
        mouse_id = params.get("mouse_id", "unknown")

        save_directory = params.get("save_directory", "D:\\behaviour_data\\default")
        progress_override = params.get("progress_folder_override", "").strip()
        progress_folder = progress_override if progress_override else os.path.join(save_directory, "autotraining_progress")
        start_override = params.get("start_stage_override", "").strip()

        default_first_stage = ""
        for stage in STAGES.values():
            if not stage.is_warmup:
                default_first_stage = stage.name
                break

        saved_state = load_training_state(progress_folder, mouse_id, default_first_stage)

        if start_override and start_override in STAGES:
            saved_stage = start_override
            saved_trials = 0
            self.log(f"Manual stage override: {start_override}")
        else:
            saved_stage = saved_state.current_stage or default_first_stage
            saved_trials = saved_state.trials_in_stage

        self.log(f"Mouse: {mouse_id}")
        self.log(f"Saved stage: {saved_stage} ({saved_trials} trials accumulated)")
        self.log(f"Progress folder: {progress_folder}")

        engine = AutotrainingEngine(
            stages=STAGES,
            transitions=TRANSITIONS,
            saved_stage_name=saved_stage,
            saved_trials_in_stage=saved_trials,
        )

        # trackers is stage-keyed: trackers[stage_name] -> Tracker
        engine.initialise_session(
            log=self.log,
            skip_warmup=params.get("skip_warmup", False),
            tracker_lookup=lambda stage_name: trackers.get(stage_name),
        )

        session_start = self.now()
        trial_num = 0

        try:
            while True:
                if num_trials > 0 and trial_num >= num_trials:
                    self.log(f"Completed {num_trials} trials")
                    break

                if self.check_stop():
                    self.log("Stopped by user")
                    break

                stage_params = engine.get_active_params()
                stage_name = engine.current_stage_name

                trial_mode = stage_params.get("trial_mode", "visual")
                weight_threshold = params["mouse_weight"] - stage_params["weight_offset"]
                platform_settle_time = stage_params["platform_settle_time"]
                iti = stage_params["iti"]

                # --- Platform detection ---

                platform_ready = False
                while not self.check_stop() and not platform_ready:
                    weight = scales.get_weight()
                    if weight is not None and weight > weight_threshold:
                        settle_start = self.now()
                        settled = True

                        while self.now() - settle_start < platform_settle_time:
                            if self.check_stop():
                                break
                            weight = scales.get_weight()
                            if weight is None or weight < weight_threshold:
                                settled = False
                                break
                            self.sleep(0.02)

                        if settled and not self.check_stop():
                            weight = scales.get_weight()
                            if weight is not None and weight > weight_threshold:
                                platform_ready = True
                    else:
                        self.sleep(0.05)

                if self.check_stop():
                    break

                # --- Scales mode trial ---

                if trial_mode == "scales":
                    scales_reward_port = stage_params.get("scales_reward_port", 1)
                    collection_timeout = stage_params.get("collection_timeout", 30.0)

                    trial_num += 1
                    target_port = scales_reward_port
                    tracker = trackers.get(stage_name)
                    if tracker is None:
                        self.log(f"ERROR: no tracker for stage {stage_name}")
                        break

                    trial_start_time = self.now()
                    outcome = "timeout"
                    chosen_port = None

                    with Trial(tracker, correct_port=target_port) as t:
                        t.stimulus(port=target_port, modality="scales", stage=stage_name)

                        self.link.valve_pulse(target_port, self.reward_durations[target_port])

                        event = None
                        while not self.check_stop():
                            elapsed = self.now() - trial_start_time
                            if elapsed >= collection_timeout:
                                break
                            remaining = collection_timeout - elapsed
                            event = self.link.wait_for_event(timeout=min(0.1, remaining))
                            if event is not None and event.port == target_port:
                                break
                            event = None

                        if self.check_stop():
                            break  # Trial auto-abandons

                        if event is not None and event.port == target_port:
                            t.success(stage=stage_name)
                            outcome = "success"
                            chosen_port = target_port
                            self.log(
                                f"  [{engine.current_stage_display}] T{trial_num} COLLECTED port {target_port}"
                            )
                        else:
                            t.timeout(stage=stage_name)
                            outcome = "timeout"
                            chosen_port = None
                            self.log(
                                f"  [{engine.current_stage_display}] T{trial_num} NOT COLLECTED (timeout {collection_timeout:.0f}s)"
                            )

                    trial_duration = self.now() - trial_start_time

                # --- Combined cue trial (LED + noise) ---

                else:
                    response_timeout = stage_params["response_timeout"]
                    wait_duration = stage_params["wait_duration"]
                    cue_duration = stage_params["cue_duration"]
                    led_brightness = stage_params["led_brightness"]
                    ignore_incorrect = stage_params.get("ignore_incorrect", False)
                    incorrect_timeout = stage_params.get("incorrect_timeout", 0.0)
                    spotlight_duration = stage_params.get("spotlight_duration", 0.0)
                    spotlight_brightness = stage_params.get("spotlight_brightness", 255)

                    enabled_ports = []
                    for i in range(6):
                        if stage_params.get(f"port_{i}_enabled", False):
                            enabled_ports.append(i)

                    if not enabled_ports:
                        self.log(f"WARNING: No ports enabled in stage {stage_name}, using port 1")
                        enabled_ports = [1]

                    trial_num += 1
                    target_port = random.choice(enabled_ports)

                    # --- Wait period on platform ---

                    wait_complete = False
                    activation_time = self.now()
                    while not self.check_stop():
                        elapsed = self.now() - activation_time
                        weight = scales.get_weight()
                        if weight is None or weight < weight_threshold:
                            self.log("  Mouse left platform during wait period")
                            break
                        if elapsed >= wait_duration:
                            wait_complete = True
                            break
                        self.sleep(0.02)

                    if self.check_stop():
                        break

                    if not wait_complete:
                        trial_num -= 1
                        self.sleep(iti)
                        continue

                    # --- Record to tracker ---
                    tracker = trackers.get(stage_name)
                    if tracker is None:
                        self.log(f"ERROR: no tracker for stage {stage_name}")
                        break

                    trial_start_time = self.now()
                    outcome = "timeout"
                    chosen_port = None

                    with Trial(tracker, correct_port=target_port) as t:
                        t.stimulus(port=target_port, modality="combined", stage=stage_name)

                        # --- Present combined cue (LED + noise) ---
                        self.link.led_set(target_port, led_brightness)
                        self.link.noise_set(target_port, True)

                        # --- Wait for response ---
                        cue_on = True
                        event = None
                        while True:
                            if self.check_stop():
                                break

                            elapsed = self.now() - trial_start_time

                            if cue_on and cue_duration > 0 and elapsed >= cue_duration:
                                self.link.led_set(target_port, 0)
                                self.link.noise_set(target_port, False)
                                cue_on = False

                            if elapsed >= response_timeout:
                                break

                            remaining = response_timeout - elapsed
                            event = self.link.wait_for_event(timeout=min(0.1, remaining))
                            if event is not None:
                                if not ignore_incorrect or event.port == target_port:
                                    break

                        # Turn off cues
                        if cue_on:
                            self.link.led_set(target_port, 0)
                            self.link.noise_set(target_port, False)

                        if self.check_stop():
                            break  # Trial auto-abandons

                        if event is None:
                            t.timeout(stage=stage_name)
                            outcome = "timeout"
                            self.log(
                                f"  [{engine.current_stage_display}] T{trial_num} TIMEOUT ({response_timeout:.0f}s)"
                            )
                        elif event.port == target_port:
                            t.success(stage=stage_name)
                            self.link.valve_pulse(target_port, self.reward_durations[target_port])
                            outcome = "success"
                            chosen_port = event.port
                            self.log(
                                f"  [{engine.current_stage_display}] T{trial_num} SUCCESS port {event.port}"
                            )
                        else:
                            t.failure(chosen_port=event.port, stage=stage_name)
                            outcome = "failure"
                            chosen_port = event.port
                            self.log(
                                f"  [{engine.current_stage_display}] T{trial_num} FAILURE port {event.port} (expected {target_port})"
                            )

                            if incorrect_timeout > 0:
                                if spotlight_duration > 0:
                                    self.link.spotlight_set(255, spotlight_brightness)
                                    self.sleep(min(spotlight_duration, incorrect_timeout))
                                    self.link.spotlight_set(255, 0)
                                    remaining_timeout = incorrect_timeout - spotlight_duration
                                    if remaining_timeout > 0:
                                        self.sleep(remaining_timeout)
                                else:
                                    self.sleep(incorrect_timeout)

                    trial_duration = self.now() - trial_start_time

                # --- Common post-trial ---

                new_stage = engine.on_trial_complete(
                    outcome=outcome,
                    correct_port=target_port,
                    chosen_port=chosen_port,
                    trial_duration=trial_duration,
                )

                if new_stage is not None:
                    new_tracker = trackers.get(engine.current_stage_name)
                    if new_tracker is not None:
                        self.log(f"    Rolling accuracy: {new_tracker.rolling_accuracy(10):.0f}% (last 10)")
                    self.log(f"    Now entering: {engine.current_stage_display}")

                if not self.check_stop() and iti > 0:
                    self.sleep(iti)

        finally:
            self.link.noise_set(255, False)

            end_state = engine.get_session_end_state()
            transition_log = engine.get_transition_log()

            if not end_state.get("in_warmup", False):
                save_training_state(
                    progress_root=progress_folder,
                    mouse_id=mouse_id,
                    current_stage=end_state["current_stage"],
                    trials_in_stage=end_state["trials_in_stage"],
                    previous_state=saved_state,
                    transition_log=transition_log,
                )
                self.log(
                    f"Training state saved: stage={end_state['current_stage']}, "
                    f"trials={end_state['trials_in_stage']}"
                )
            else:
                self.log("Session ended during warm-up — training state NOT updated")

            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            if transition_log:
                append_transition_log(progress_folder, mouse_id, session_id, transition_log)
                self.log(f"Logged {len(transition_log)} stage transition(s)")

            session_duration = (self.now() - session_start) / 60.0
            self.log(f"Session complete: {trial_num} trials in {session_duration:.1f} minutes")
