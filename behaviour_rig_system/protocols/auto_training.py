"""
Training Autotraining Protocol (Class-based)

Adaptive protocol that progresses through training stages based on performance.
"""

import random
import time
from datetime import datetime

from autotraining.definitions.graph import TRANSITIONS
from autotraining.definitions.stages import STAGES
from autotraining.engine import AutotrainingEngine
from autotraining.persistence import (
    append_transition_log,
    load_training_state,
    save_training_state,
)
from core.parameter_types import FloatParameter, IntParameter, StringParameter
from core.protocol_base import BaseProtocol


class AutoTrainingProtocol(BaseProtocol):
    """Adaptive training protocol with persistent stage progression."""

    @classmethod
    def get_name(cls) -> str:
        return "Autotraining"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Adaptive training protocol. Automatically progresses through training "
            "stages based on mouse performance. Saves progress between sessions."
        )

    @classmethod
    def get_parameters(cls) -> list:
        return [
            StringParameter(
                name="progress_folder",
                display_name="Autotraining Progress Folder",
                default="D:\\behaviour_data\\autotraining_progress",
            ),
            StringParameter(
                name="start_stage_override",
                display_name="Override Start Stage (blank = use saved)",
                default="",
            ),
            FloatParameter(
                name="weight_offset",
                display_name="Weight Threshold Offset (g)",
                default=3.0,
                min_value=0.0,
                max_value=10.0,
            ),
            IntParameter(
                name="platform_settle_time",
                display_name="Platform Settle Time (s)",
                default=1,
                min_value=0,
                max_value=5,
            ),
            IntParameter(
                name="led_brightness",
                display_name="LED Brightness (0-255)",
                default=255,
                min_value=0,
                max_value=255,
            ),
            IntParameter(
                name="reward_duration",
                display_name="Reward Duration (ms)",
                default=500,
                min_value=50,
                max_value=5000,
            ),
            FloatParameter(
                name="iti",
                display_name="Inter-Trial Interval (s)",
                default=1.0,
                min_value=0.0,
                max_value=10.0,
            ),
        ]

    def _run_protocol(self) -> None:
        params = self.parameters
        scales = self.scales
        perf_tracker = self.perf_tracker

        if scales is None:
            self.log("ERROR: Scales not available!")
            return

        if perf_tracker is not None:
            perf_tracker.reset()

        mouse_weight = params["mouse_weight"]
        num_trials = params["num_trials"]
        mouse_id = params.get("mouse_id", "unknown")

        progress_folder = params.get("progress_folder", "D:\\behaviour_data\\autotraining_progress")
        start_override = params.get("start_stage_override", "").strip()

        session_overrides = {
            "weight_offset": params["weight_offset"],
            "platform_settle_time": params["platform_settle_time"],
            "led_brightness": params["led_brightness"],
            "reward_duration": params["reward_duration"],
            "iti": params["iti"],
        }

        weight_threshold = mouse_weight - session_overrides["weight_offset"]

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

        if perf_tracker is not None:
            engine.initialise_session(perf_tracker, self.log)

        session_start = time.time()
        trial_num = 0

        try:
            while True:
                if num_trials > 0 and trial_num >= num_trials:
                    self.log(f"Completed {num_trials} trials")
                    break

                if self._check_stop():
                    self.log("Stopped by user")
                    break

                stage_params = engine.get_active_params()
                stage_params.update(session_overrides)

                response_timeout = stage_params["response_timeout"]
                wait_duration = stage_params["wait_duration"]
                iti = stage_params["iti"]
                cue_duration = stage_params["cue_duration"]
                led_brightness = stage_params["led_brightness"]
                reward_ms = stage_params["reward_duration"]
                punishment_s = stage_params["punishment_duration"]
                punishment_enabled = stage_params.get("punishment_enabled", False)
                platform_settle_time = stage_params["platform_settle_time"]

                enabled_ports = []
                for i in range(6):
                    if stage_params.get(f"port_{i}_enabled", False):
                        enabled_ports.append(i)

                if not enabled_ports:
                    self.log(f"WARNING: No ports enabled in stage {engine.current_stage_name}, using port 0")
                    enabled_ports = [0]

                platform_ready = False
                while not self._check_stop() and not platform_ready:
                    weight = scales.get_weight()
                    if weight is not None and weight > weight_threshold:
                        settle_start = time.time()
                        settled = True

                        while time.time() - settle_start < platform_settle_time:
                            if self._check_stop():
                                break
                            weight = scales.get_weight()
                            if weight is None or weight < weight_threshold:
                                settled = False
                                break
                            time.sleep(0.02)

                        if settled and not self._check_stop():
                            weight = scales.get_weight()
                            if weight is not None and weight > weight_threshold:
                                platform_ready = True
                    else:
                        time.sleep(0.05)

                if self._check_stop():
                    break

                trial_num += 1
                target_port = random.choice(enabled_ports)

                wait_complete = False
                activation_time = time.time()
                while not self._check_stop():
                    elapsed = time.time() - activation_time
                    weight = scales.get_weight()
                    if weight is None or weight < weight_threshold:
                        self.log("  Mouse left platform during wait period")
                        break
                    if elapsed >= wait_duration:
                        wait_complete = True
                        break
                    time.sleep(0.02)

                if self._check_stop():
                    break

                if not wait_complete:
                    trial_num -= 1
                    time.sleep(iti)
                    continue

                if perf_tracker is not None:
                    perf_tracker.stimulus(target_port)
                trial_start_time = time.time()

                self.link.led_set(target_port, led_brightness)

                cue_on = True
                event = None
                while True:
                    if self._check_stop():
                        break

                    elapsed = time.time() - trial_start_time
                    if cue_on and cue_duration > 0 and elapsed >= cue_duration:
                        self.link.led_set(target_port, 0)
                        cue_on = False

                    if elapsed >= response_timeout:
                        break

                    remaining = response_timeout - elapsed
                    event = self.link.wait_for_event(timeout=min(0.1, remaining))
                    if event is not None:
                        break

                trial_duration = time.time() - trial_start_time
                if cue_on:
                    self.link.led_set(target_port, 0)

                outcome = "timeout"
                chosen_port = None

                if self._check_stop():
                    break

                if event is None:
                    if perf_tracker is not None:
                        perf_tracker.timeout(correct_port=target_port, trial_duration=trial_duration)
                    outcome = "timeout"
                    self.log(f"  [{engine.current_stage_display}] T{trial_num} TIMEOUT ({response_timeout:.0f}s)")
                elif event.port == target_port:
                    if perf_tracker is not None:
                        perf_tracker.success(correct_port=target_port, trial_duration=trial_duration)
                    self.link.valve_pulse(target_port, reward_ms)
                    outcome = "success"
                    chosen_port = event.port
                    self.log(
                        f"  [{engine.current_stage_display}] T{trial_num} SUCCESS port {event.port} ({trial_duration:.1f}s)"
                    )
                else:
                    if perf_tracker is not None:
                        perf_tracker.failure(
                            correct_port=target_port,
                            chosen_port=event.port,
                            trial_duration=trial_duration,
                        )
                    outcome = "failure"
                    chosen_port = event.port
                    self.log(
                        f"  [{engine.current_stage_display}] T{trial_num} FAILURE port {event.port} (expected {target_port})"
                    )

                    if punishment_enabled and punishment_s > 0:
                        self.link.spotlight_set(255, 255)
                        time.sleep(punishment_s)
                        self.link.spotlight_set(255, 0)

                new_stage = engine.on_trial_complete(
                    outcome=outcome,
                    correct_port=target_port,
                    chosen_port=chosen_port,
                    trial_duration=trial_duration,
                )

                if new_stage is not None and perf_tracker is not None:
                    self.log(f"    Rolling accuracy: {perf_tracker.rolling_accuracy(10):.0f}% (last 10)")
                    self.log(f"    Now entering: {engine.current_stage_display}")

                if not self._check_stop() and iti > 0:
                    time.sleep(iti)

        finally:
            end_state = engine.get_session_end_state()

            if not end_state.get("in_warmup", False):
                save_training_state(
                    progress_root=progress_folder,
                    mouse_id=mouse_id,
                    current_stage=end_state["current_stage"],
                    trials_in_stage=end_state["trials_in_stage"],
                    previous_state=saved_state,
                )
                self.log(
                    f"Training state saved: stage={end_state['current_stage']}, "
                    f"trials={end_state['trials_in_stage']}"
                )
            else:
                self.log("Session ended during warm-up — training state NOT updated")

            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            transition_log = engine.get_transition_log()
            if transition_log:
                append_transition_log(progress_folder, mouse_id, session_id, transition_log)
                self.log(f"Logged {len(transition_log)} stage transition(s)")

            session_duration = (time.time() - session_start) / 60.0
            self.log(f"Session complete: {trial_num} trials in {session_duration:.1f} minutes")
