"""
Cue Conflict Test Protocol

Probe protocol to determine which modality (visual or audio) a mouse is
following. On each trial, an LED cue and a noise cue are presented
simultaneously at DIFFERENT ports. The mouse can go to either port for a
reward — whichever it chooses reveals its modality preference.

Both cues stay on continuously until the mouse touches a port (no cue
duration limit). Incorrect ports (neither the visual nor the audio port)
are punished.

Tracks visual-chosen and audio-chosen counts separately so you can see
the preference ratio at a glance.
"""

import random

from core.parameter_types import FloatParameter, IntParameter
from core.performance_tracker import TrackerGroupDefinition
from core.protocol_base import BaseProtocol


class CueConflictTestProtocol(BaseProtocol):
    """Conflict test: LED and noise at different ports, mouse chooses which to follow."""

    @classmethod
    def get_name(cls) -> str:
        return "Cue Conflict Test"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Determines which modality a mouse is following. Each trial presents "
            "an LED at one port and white noise at a different port simultaneously. "
            "The mouse can go to either for a reward. Tracks visual vs audio choices."
        )

    @classmethod
    def get_tracker_definitions(cls) -> list:
        return [
            TrackerGroupDefinition(
                name="conflict",
                display_name="Cue Conflict",
                sub_trackers=["visual", "audio"],
                stages={"conflict"},
            ),
        ]

    @classmethod
    def get_parameters(cls) -> list:
        return [
            IntParameter(
                name="num_ports",
                display_name="Number of Ports (2-6)",
                default=6,
                min_value=2,
                max_value=6,
            ),
            IntParameter(
                name="led_brightness",
                display_name="LED Brightness (0-255)",
                default=255,
                min_value=0,
                max_value=255,
            ),
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
                default=10.0,
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
        group = self.tracker_groups.get("conflict")

        if scales is None:
            self.log("ERROR: Scales not available!")
            return

        if group is not None:
            group.reset()

        mouse_weight = params["mouse_weight"]
        num_trials = params["num_trials"]
        weight_threshold = mouse_weight - params["weight_offset"]
        platform_settle_time = params["platform_settle_time"]

        response_timeout = params["response_timeout"]
        wait_duration = params["wait_duration"]
        iti = params["iti"]
        led_brightness = params["led_brightness"]

        incorrect_timeout = params["incorrect_timeout"]
        spotlight_duration = params["spotlight_duration"]
        spotlight_brightness = params["spotlight_brightness"]

        num_ports = params["num_ports"]
        enabled_ports = list(range(num_ports))

        visual_chosen = 0
        audio_chosen = 0

        trials_str = "unlimited" if num_trials == 0 else str(num_trials)
        self.log("Starting Cue Conflict Test")
        self.log(f"  Mouse weight: {mouse_weight}g, threshold: {weight_threshold:.1f}g")
        self.log(f"  Ports: {enabled_ports} ({num_ports} ports)")
        self.log(f"  Trials: {trials_str}")
        self.log(f"  Timeout: {response_timeout}s, ITI: {iti}s")
        self.log("  Cues: continuous until response")
        self.log("  Each trial: LED at one port, noise at a different port")
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

            # --- Pick two different ports: one for LED, one for noise ---

            visual_port, audio_port = random.sample(enabled_ports, 2)
            trial_num += 1

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

            # --- Present conflicting cues ---

            if group is not None:
                group.stimulus(visual_port)
            trial_start_time = self.now()

            self.link.led_set(visual_port, led_brightness)
            self.link.noise_set(audio_port, True)

            # --- Wait for response (any port touch) ---

            event = None
            while True:
                if self.check_stop():
                    break

                elapsed = self.now() - trial_start_time
                if elapsed >= response_timeout:
                    break

                remaining = response_timeout - elapsed
                event = self.link.wait_for_event(timeout=min(0.1, remaining))
                if event is not None:
                    break

            trial_duration = self.now() - trial_start_time

            # Turn off both cues
            self.link.led_set(visual_port, 0)
            self.link.noise_set(audio_port, False)

            if self.check_stop():
                break

            # --- Outcome ---

            if event is None:
                # Timeout
                if group is not None:
                    group.timeout(correct_port=visual_port, trial_duration=trial_duration,
                                  sub_tracker="visual")
                self.log(
                    f"  T{trial_num} TIMEOUT ({response_timeout:.0f}s) "
                    f"[LED={visual_port} noise={audio_port}]"
                )

            elif event.port == visual_port:
                # Chose the visual cue
                visual_chosen += 1
                if group is not None:
                    group.success(correct_port=visual_port, trial_duration=trial_duration,
                                  sub_tracker="visual")
                self.link.valve_pulse(visual_port, self.reward_durations[visual_port])
                self.log(
                    f"  T{trial_num} VISUAL port {visual_port} ({trial_duration:.1f}s) "
                    f"[LED={visual_port} noise={audio_port}] "
                    f"(V:{visual_chosen} A:{audio_chosen})"
                )

            elif event.port == audio_port:
                # Chose the audio cue
                audio_chosen += 1
                if group is not None:
                    group.success(correct_port=audio_port, trial_duration=trial_duration,
                                  sub_tracker="audio")
                self.link.valve_pulse(audio_port, self.reward_durations[audio_port])
                self.log(
                    f"  T{trial_num} AUDIO port {audio_port} ({trial_duration:.1f}s) "
                    f"[LED={visual_port} noise={audio_port}] "
                    f"(V:{visual_chosen} A:{audio_chosen})"
                )

            else:
                # Chose neither cue port — incorrect
                modality = "visual"
                if group is not None:
                    group.failure(correct_port=visual_port, chosen_port=event.port,
                                  trial_duration=trial_duration, sub_tracker=modality)
                self.log(
                    f"  T{trial_num} INCORRECT port {event.port} ({trial_duration:.1f}s) "
                    f"[LED={visual_port} noise={audio_port}]"
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

        # --- Summary ---
        total_choices = visual_chosen + audio_chosen
        if total_choices > 0:
            vis_pct = (visual_chosen / total_choices) * 100
            aud_pct = (audio_chosen / total_choices) * 100
            self.log("---")
            self.log(f"Preference: Visual {visual_chosen} ({vis_pct:.0f}%) | Audio {audio_chosen} ({aud_pct:.0f}%)")
        else:
            self.log("---")
            self.log("No valid choices recorded")
