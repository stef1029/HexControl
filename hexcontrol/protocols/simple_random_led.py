"""
Simple Random LED Protocol

Presents a continuous LED cue at a randomly chosen port (0-5) each trial.
Trial starts only when the mouse is detected on the scales platform.
Correct port visit = reward, incorrect = failure, no response = timeout.
"""

import random

from hexcontrol.core.parameter_types import FloatParameter, IntParameter
from hexcontrol.core.protocol_base import BaseProtocol
from hexcontrol.core.tracker import TrackerDefinition, Trial


class SimpleRandomLedProtocol(BaseProtocol):
    """Random LED on one of 6 ports, continuous cue until response or timeout."""

    @classmethod
    def get_name(cls) -> str:
        return "Simple Random LED"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Each trial lights a random LED (ports 0-5) continuously until the mouse "
            "responds or the trial times out. Trial only begins when the mouse is "
            "detected on the scales platform. Correct port visit delivers a reward."
        )

    @classmethod
    def get_parameters(cls) -> list:
        return [
            IntParameter(
                name="num_trials",
                display_name="Number of Trials",
                default=100,
                min_value=1,
                max_value=5000,
            ),
            IntParameter(
                name="led_brightness",
                display_name="LED Brightness (0-255)",
                default=255,
                min_value=1,
                max_value=255,
            ),
            FloatParameter(
                name="response_timeout",
                display_name="Response Timeout (s)",
                default=30.0,
                min_value=1.0,
                max_value=120.0,
            ),
            FloatParameter(
                name="weight_offset",
                display_name="Weight Offset (g)",
                default=5.0,
                min_value=0.0,
                max_value=15.0,
            ),
            FloatParameter(
                name="platform_settle_time",
                display_name="Platform Settle Time (s)",
                default=0.5,
                min_value=0.0,
                max_value=5.0,
            ),
            FloatParameter(
                name="wait_duration",
                display_name="Wait Duration on Platform (s)",
                default=0.5,
                min_value=0.0,
                max_value=10.0,
            ),
            FloatParameter(
                name="iti",
                display_name="Inter-Trial Interval (s)",
                default=3.0,
                min_value=0.0,
                max_value=30.0,
            ),
        ]

    @classmethod
    def get_tracker_definitions(cls) -> dict:
        return {"trials": TrackerDefinition(name="trials", display_name="Trials")}

    def _setup(self) -> None:
        self.link.ir_set(255)
        self.log("IR illuminator ON")

    def _cleanup(self) -> None:
        for port in range(6):
            self.link.led_set(port, 0)
        self.link.ir_set(0)
        self.log("Cleanup complete")

    def _run_protocol(self) -> None:
        params = self.parameters
        scales = self.scales
        tracker = self.trackers.get("trials")

        if tracker is None:
            self.log("ERROR: 'trials' tracker not available!")
            return
        if scales is None:
            self.log("ERROR: Scales not available!")
            return

        tracker.reset()

        num_trials = params["num_trials"]
        led_brightness = params["led_brightness"]
        response_timeout = params["response_timeout"]
        weight_offset = params["weight_offset"]
        platform_settle_time = params["platform_settle_time"]
        wait_duration = params["wait_duration"]
        iti = params["iti"]

        mouse_weight = params["mouse_weight"]
        weight_threshold = mouse_weight - weight_offset

        self.log(
            f"Starting {num_trials} trials | brightness={led_brightness} | "
            f"timeout={response_timeout}s | ITI={iti}s"
        )
        self.log(f"  Mouse weight: {mouse_weight}g, threshold: {weight_threshold:.1f}g")

        trial_num = 0

        while trial_num < num_trials:
            if self.check_stop():
                self.log("Stopped by user")
                return

            # --- Wait for mouse on platform ---
            platform_ready = False
            while not self.check_stop() and not platform_ready:
                weight = scales.get_weight()
                if weight is not None and weight > weight_threshold:
                    # Weight detected — confirm it's stable
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

            # --- Wait duration: mouse must stay on platform ---
            wait_complete = False
            wait_start = self.now()
            while not self.check_stop():
                elapsed = self.now() - wait_start
                weight = scales.get_weight()
                if weight is None or weight < weight_threshold:
                    break  # Mouse left — restart
                if elapsed >= wait_duration:
                    wait_complete = True
                    break
                self.sleep(0.02)

            if self.check_stop():
                break
            if not wait_complete:
                self.sleep(iti)
                continue

            # --- Run trial ---
            trial_num += 1
            target_port = random.randint(0, 5)

            with Trial(tracker, correct_port=target_port) as t:
                t.stimulus(port=target_port, modality="visual")

                # Continuous LED cue — stays on until response or timeout
                self.link.led_set(target_port, led_brightness)

                trial_start = self.now()
                event = None
                while not self.check_stop():
                    elapsed = self.now() - trial_start
                    if elapsed >= response_timeout:
                        break
                    remaining = response_timeout - elapsed
                    event = self.link.wait_for_event(timeout=min(0.1, remaining))
                    if event is not None:
                        break

                # LED off
                self.link.led_set(target_port, 0)

                if self.check_stop():
                    break  # Trial auto-abandons

                # Record outcome
                if event is None:
                    t.timeout()
                    self.log(f"  T{trial_num} TIMEOUT (port {target_port})")
                elif event.port == target_port:
                    t.success()
                    self.link.valve_pulse(target_port, self.reward_durations[target_port])
                    self.log(f"  T{trial_num} CORRECT (port {target_port})")
                else:
                    t.failure(chosen_port=event.port)
                    self.log(f"  T{trial_num} INCORRECT (chose {event.port}, target {target_port})")

            # Inter-trial interval
            if not self.check_stop() and iti > 0:
                self.sleep(iti)

        self.log(f"Protocol complete: {trial_num} trials")
