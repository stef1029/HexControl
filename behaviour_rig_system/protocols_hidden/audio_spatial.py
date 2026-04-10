"""
Audio Spatial Protocol

Simple standalone protocol for spatial audio tasks. Uses white noise
played from individual buzzer ports as the cue — the mouse must go to
the port that is producing the noise to receive a reward.

Mirrors the 6-port visual protocol structure but replaces LED cues
with spatial noise cues via noise_set().
"""

import random

from core.parameter_types import BoolParameter, FloatParameter, IntParameter
from core.protocol_base import BaseProtocol
from core.tracker import TrackerDefinition, Trial


class AudioSpatialProtocol(BaseProtocol):
    """Spatial audio task: noise cue at a random port, mouse must go to it."""

    @classmethod
    def get_name(cls) -> str:
        return "Audio Spatial (6-port)"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Spatial audio task using white noise. On each trial a random "
            "buzzer port plays broadband noise and the mouse must visit that "
            "port to receive a reward. Supports cue duration limiting and "
            "punishment for incorrect responses."
        )

    @classmethod
    def get_tracker_definitions(cls) -> dict:
        return {"trials": TrackerDefinition(name="trials", display_name="Trials")}

    @classmethod
    def get_parameters(cls) -> list:
        return [
            FloatParameter(
                name="cue_duration",
                display_name="Cue Duration (s, 0=until response)",
                default=0.0,
                min_value=0.0,
                max_value=30.0,
            ),
            BoolParameter(name="port_0_enabled", display_name="Port 0 Enabled", default=True),
            BoolParameter(name="port_1_enabled", display_name="Port 1 Enabled", default=True),
            BoolParameter(name="port_2_enabled", display_name="Port 2 Enabled", default=True),
            BoolParameter(name="port_3_enabled", display_name="Port 3 Enabled", default=True),
            BoolParameter(name="port_4_enabled", display_name="Port 4 Enabled", default=True),
            BoolParameter(name="port_5_enabled", display_name="Port 5 Enabled", default=True),
            FloatParameter(
                name="weight_offset",
                display_name="Weight Threshold Offset (g)",
                default=3.0,
                min_value=0.0,
                max_value=10.0,
            ),
            FloatParameter(
                name="platform_settle_time",
                display_name="Platform Settle Time (s)",
                default=1.0,
                min_value=0.0,
                max_value=5.0,
            ),
            FloatParameter(
                name="response_timeout",
                display_name="Response Timeout (s)",
                default=5.0,
                min_value=1.0,
                max_value=60.0,
            ),
            FloatParameter(
                name="wait_duration",
                display_name="Wait Duration on Platform (s)",
                default=0.0,
                min_value=0.0,
                max_value=10.0,
            ),
            FloatParameter(
                name="iti",
                display_name="Inter-Trial Interval (s)",
                default=1.0,
                min_value=0.0,
                max_value=10.0,
            ),
            BoolParameter(
                name="ignore_incorrect",
                display_name="Ignore Incorrect Touches",
                default=False,
            ),
            FloatParameter(
                name="incorrect_timeout",
                display_name="Incorrect Timeout (s)",
                default=5.0,
                min_value=0.0,
                max_value=30.0,
            ),
            FloatParameter(
                name="spotlight_duration",
                display_name="Spotlight Punishment Duration (s)",
                default=1.0,
                min_value=0.0,
                max_value=10.0,
            ),
            IntParameter(
                name="spotlight_brightness",
                display_name="Spotlight Punishment Brightness",
                default=128,
                min_value=0,
                max_value=255,
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
        tracker = self.trackers.get("trials")

        if scales is None:
            self.log("ERROR: Scales not available!")
            return

        if tracker is None:
            self.log("ERROR: 'trials' tracker not available!")
            return

        tracker.reset()

        mouse_weight = params["mouse_weight"]
        num_trials = params["num_trials"]
        weight_threshold = mouse_weight - params["weight_offset"]
        platform_settle_time = params["platform_settle_time"]

        response_timeout = params["response_timeout"]
        wait_duration = params["wait_duration"]
        iti = params["iti"]
        cue_duration = params["cue_duration"]

        ignore_incorrect = params["ignore_incorrect"]
        incorrect_timeout = params["incorrect_timeout"]
        spotlight_duration = params["spotlight_duration"]
        spotlight_brightness = params["spotlight_brightness"]

        enabled_ports = []
        for i in range(6):
            if params[f"port_{i}_enabled"]:
                enabled_ports.append(i)

        if not enabled_ports:
            self.log("ERROR: No ports enabled! Enable at least one port.")
            return

        trials_str = "unlimited" if num_trials == 0 else str(num_trials)
        self.log("Starting Audio Spatial Protocol")
        self.log(f"  Mouse weight: {mouse_weight}g, threshold: {weight_threshold:.1f}g")
        self.log(f"  Enabled ports: {enabled_ports}")
        self.log(f"  Trials: {trials_str}")
        self.log(f"  Wait: {wait_duration}s, Timeout: {response_timeout}s, ITI: {iti}s")
        if cue_duration > 0:
            self.log(f"  Cue duration: {cue_duration}s (limited)")
        else:
            self.log("  Cue duration: unlimited (until response)")
        self.log("---")

        trial_num = 0

        while True:
            if num_trials > 0 and trial_num >= num_trials:
                self.log(f"Completed {num_trials} trials")
                break

            if self.check_stop():
                self.log("Stopped by user")
                break

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

            # --- Wait period on platform ---

            target_port = random.choice(enabled_ports)
            trial_num += 1

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

            # --- Cue presentation: noise on target buzzer ---

            with Trial(tracker, correct_port=target_port) as t:
                t.stimulus(port=target_port, modality="audio")

                trial_start_time = self.now()
                self.link.noise_set(target_port, True)

                cue_on = True
                event = None

                while True:
                    if self.check_stop():
                        break

                    elapsed = self.now() - trial_start_time

                    if cue_on and cue_duration > 0 and elapsed >= cue_duration:
                        self.link.noise_set(target_port, False)
                        cue_on = False

                    if elapsed >= response_timeout:
                        break

                    remaining = response_timeout - elapsed
                    event = self.link.wait_for_event(timeout=min(0.1, remaining))
                    if event is not None:
                        if not ignore_incorrect or event.port == target_port:
                            break

                # Always turn off noise at end of trial
                if cue_on:
                    self.link.noise_set(target_port, False)

                if self.check_stop():
                    break  # Trial auto-abandons

                # --- Outcome ---
                if event is None:
                    t.timeout()
                    self.log(
                        f"  T{trial_num} TIMEOUT ({response_timeout:.0f}s)"
                    )
                elif event.port == target_port:
                    t.success()
                    self.link.valve_pulse(target_port, self.reward_durations[target_port])
                    self.log(
                        f"  T{trial_num} SUCCESS port {event.port}"
                    )
                else:
                    t.failure(chosen_port=event.port)
                    self.log(
                        f"  T{trial_num} FAILURE port {event.port} (expected {target_port})"
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

            if not self.check_stop() and iti > 0:
                self.sleep(iti)
