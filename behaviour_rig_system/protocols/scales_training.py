"""
Scales Training Protocol

Simple protocol where the mouse learns to associate the platform with reward.
As soon as the mouse stands on the platform, a reward is delivered at a fixed port.
The next trial only begins once the mouse visits the port (activating the sensor),
or after a 30s timeout.

No LEDs, no error signals.
"""

from core.parameter_types import FloatParameter, IntParameter
from core.performance_tracker import TrackerDefinition
from core.protocol_base import BaseProtocol


class ScalesTrainingProtocol(BaseProtocol):
    """Platform association: stand on scales -> reward at fixed port."""

    @classmethod
    def get_name(cls) -> str:
        return "Scales Training"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Simple platform-reward association. Mouse stands on the platform "
            "and a reward is immediately delivered at a fixed port. The next "
            "trial starts once the mouse visits the port (or after timeout)."
        )

    @classmethod
    def get_tracker_definitions(cls) -> list:
        return [TrackerDefinition(name="trials", display_name="Trials")]

    @classmethod
    def get_parameters(cls) -> list:
        return [
            IntParameter(
                name="reward_port",
                display_name="Reward Port",
                default=0,
                min_value=0,
                max_value=5,
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
                default=0.0,
                min_value=0.0,
                max_value=5.0,
            ),
            FloatParameter(
                name="collection_timeout",
                display_name="Reward Collection Timeout (s)",
                default=30.0,
                min_value=1.0,
                max_value=120.0,
            ),
            FloatParameter(
                name="iti",
                display_name="Inter-Trial Interval (s)",
                default=1.0,
                min_value=0.0,
                max_value=10.0,
            ),
        ]

    def _setup(self) -> None:
        self.link.ir_set(255)
        self.log("IR illuminator ON (100%)")

    def _cleanup(self) -> None:
        self.link.ir_set(0)

    def _run_protocol(self) -> None:
        params = self.parameters
        scales = self.scales
        perf_tracker = self.perf_trackers.get("trials")

        if scales is None:
            self.log("ERROR: Scales not available!")
            return

        if perf_tracker is not None:
            perf_tracker.reset()

        mouse_weight = params["mouse_weight"]
        num_trials = params["num_trials"]
        reward_port = params["reward_port"]
        reward_ms = self.reward_durations[reward_port]
        weight_offset = params["weight_offset"]
        weight_threshold = mouse_weight - weight_offset
        platform_settle_time = params["platform_settle_time"]
        collection_timeout = params["collection_timeout"]
        iti = params["iti"]

        trials_str = "unlimited" if num_trials == 0 else str(num_trials)
        self.log("Starting Scales Training")
        self.log(f"  Mouse weight: {mouse_weight}g, threshold: {weight_threshold:.1f}g")
        self.log(f"  Reward port: {reward_port}, reward duration: {reward_ms}ms")
        self.log(f"  Collection timeout: {collection_timeout}s")
        self.log(f"  Trials: {trials_str}")
        self.log("---")

        trial_num = 0

        while True:
            if num_trials > 0 and trial_num >= num_trials:
                self.log(f"Completed {num_trials} trials")
                break

            if self.check_stop():
                self.log("Stopped by user")
                break

            # Wait for mouse to stand on the platform
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

            trial_num += 1
            trial_start = self.now()

            # Deliver reward immediately
            self.link.valve_pulse(reward_port, reward_ms)
            self.log(f"  T{trial_num}: Reward delivered at port {reward_port}")

            if perf_tracker is not None:
                perf_tracker.stimulus(reward_port)

            # Wait for mouse to visit the port (sensor activation) or timeout
            event = None
            while not self.check_stop():
                elapsed = self.now() - trial_start
                if elapsed >= collection_timeout:
                    break

                remaining = collection_timeout - elapsed
                event = self.link.wait_for_event(timeout=min(0.1, remaining))
                if event is not None and event.port == reward_port:
                    break
                event = None  # ignore visits to other ports

            trial_duration = self.now() - trial_start

            if event is not None and event.port == reward_port:
                if perf_tracker is not None:
                    perf_tracker.success(correct_port=reward_port, trial_duration=trial_duration)
                self.log(f"  T{trial_num}: Collected ({trial_duration:.1f}s)")
            else:
                if perf_tracker is not None:
                    perf_tracker.timeout(correct_port=reward_port, trial_duration=trial_duration)
                self.log(f"  T{trial_num}: Not collected (timeout {collection_timeout:.0f}s)")

            if not self.check_stop() and iti > 0:
                self.sleep(iti)
