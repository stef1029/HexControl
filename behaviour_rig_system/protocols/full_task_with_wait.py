"""
Full Task with Wait Period Protocol (Phase 9c)

Class-based version of the original full task protocol.
"""

import random
import time

from core.parameter_types import BoolParameter, FloatParameter, IntParameter
from core.protocol_base import BaseProtocol, ProtocolEvent


try:
    from BehavLink import SpeakerFrequency, SpeakerDuration
except ImportError:
    class SpeakerFrequency:
        FREQ_3300_HZ = 4

    class SpeakerDuration:
        DURATION_500_MS = 4
        CONTINUOUS = 7


class FullTaskWithWaitProtocol(BaseProtocol):
    """Complete task: wait on platform, then respond to visual/audio cue for reward."""

    _scales_client = None
    _perf_tracker = None

    @classmethod
    def get_name(cls) -> str:
        return "Full Task with Wait"

    @classmethod
    def get_description(cls) -> str:
        return "Complete task: mouse waits on platform, then responds to visual/audio cue for reward."

    @classmethod
    def get_parameters(cls) -> list:
        return [
            FloatParameter(
                name="cue_duration",
                display_name="Cue Duration (s, 0=until response)",
                default=0.1,
                min_value=0.0,
                max_value=30.0,
            ),
            BoolParameter(name="port_0_enabled", display_name="Port 0 Enabled", default=True),
            BoolParameter(name="port_1_enabled", display_name="Port 1 Enabled", default=True),
            BoolParameter(name="port_2_enabled", display_name="Port 2 Enabled", default=True),
            BoolParameter(name="port_3_enabled", display_name="Port 3 Enabled", default=True),
            BoolParameter(name="port_4_enabled", display_name="Port 4 Enabled", default=True),
            BoolParameter(name="port_5_enabled", display_name="Port 5 Enabled", default=True),
            BoolParameter(name="audio_enabled", display_name="Enable Audio Trials", default=False),
            IntParameter(
                name="audio_proportion",
                display_name="Audio Proportion (0=all audio, 6=50:50)",
                default=6,
                min_value=0,
                max_value=12,
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
                display_name="Wait Duration (s)",
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
                name="punishment_duration",
                display_name="Punishment Duration (s)",
                default=5.0,
                min_value=0.0,
                max_value=30.0,
            ),
        ]

    def _cleanup(self) -> None:
        if self.link:
            try:
                self.link.shutdown()
            except Exception:
                pass

    def _on_abort(self) -> None:
        if self.link:
            try:
                self.link.shutdown()
            except Exception:
                pass

    def _log(self, message: str) -> None:
        self._emit_event(ProtocolEvent("status_update", data={"message": message}))

    def _run_protocol(self) -> None:
        params = self.parameters
        scales = getattr(self, "_scales_client", None)
        perf_tracker = getattr(self, "_perf_tracker", None)

        if scales is None:
            self._log("ERROR: Scales not available!")
            return

        if perf_tracker is not None:
            perf_tracker.reset()

        mouse_weight = params["mouse_weight"]
        num_trials = params["num_trials"]

        weight_offset = params["weight_offset"]
        weight_threshold = mouse_weight - weight_offset

        response_timeout = params["response_timeout"]
        wait_duration = params["wait_duration"]
        iti = params["iti"]
        cue_duration = params["cue_duration"]
        platform_settle_time = params["platform_settle_time"]

        led_brightness = params["led_brightness"]
        reward_ms = params["reward_duration"]
        punishment_s = params["punishment_duration"]

        audio_enabled = params["audio_enabled"]
        audio_proportion = params["audio_proportion"]

        enabled_ports = []
        for i in range(6):
            if params[f"port_{i}_enabled"]:
                enabled_ports.append(i)

        if not enabled_ports and not audio_enabled:
            self._log("ERROR: No ports enabled and audio disabled! Enable at least one port.")
            return

        trial_order = None

        if audio_enabled:
            if audio_proportion == 0:
                weighted_pool = [6]
                self._log("Mode: All audio trials (reward at port 0)")
            else:
                weighted_pool = enabled_ports.copy()
                for _ in range(audio_proportion):
                    weighted_pool.append(6)
                self._log(f"Mode: Mixed audio/visual (audio proportion: {audio_proportion})")
                self._log(f"Visual ports: {enabled_ports}")
        else:
            weighted_pool = enabled_ports.copy()
            self._log(f"Mode: Visual only, ports: {enabled_ports}")

        if num_trials > 0:
            trial_order = []
            for i in range(num_trials):
                trial_order.append(weighted_pool[i % len(weighted_pool)])
            random.shuffle(trial_order)

        trials_str = "unlimited" if num_trials == 0 else str(num_trials)
        self._log("Starting Full Task with Wait Period")
        self._log(f"  Mouse weight: {mouse_weight}g, threshold: {weight_threshold:.1f}g")
        self._log(f"  Trials: {trials_str}")
        self._log(f"  Wait duration: {wait_duration}s, Response timeout: {response_timeout}s")
        if cue_duration > 0:
            self._log(f"  Cue duration: {cue_duration}s (limited)")
        else:
            self._log("  Cue duration: unlimited (until response)")
        self._log("---")

        trial_num = 0

        while True:
            if num_trials > 0 and trial_num >= num_trials:
                self._log(f"Completed {num_trials} trials")
                break

            if self._check_abort():
                self._log("Aborted by user")
                break

            platform_ready = False
            while not self._check_abort() and not platform_ready:
                weight = scales.get_weight()
                if weight is not None and weight > weight_threshold:
                    settle_start = time.time()
                    settled = True

                    while time.time() - settle_start < platform_settle_time:
                        if self._check_abort():
                            break
                        weight = scales.get_weight()
                        if weight is None or weight < weight_threshold:
                            settled = False
                            break
                        time.sleep(0.02)

                    if settled and not self._check_abort():
                        weight = scales.get_weight()
                        if weight is not None and weight > weight_threshold:
                            platform_ready = True
                else:
                    time.sleep(0.05)

            if self._check_abort():
                break

            activation_time = time.time()
            trial_num += 1

            if trial_order is not None:
                port = trial_order[trial_num - 1]
            else:
                port = random.choice(weighted_pool)

            is_audio = port == 6
            target_port = 0 if is_audio else port

            wait_complete = False
            while not self._check_abort():
                elapsed = time.time() - activation_time
                weight = scales.get_weight()

                if weight is None or weight < weight_threshold:
                    self._log("  Mouse left platform during wait period")
                    break

                if elapsed >= wait_duration:
                    wait_complete = True
                    break

                time.sleep(0.02)

            if self._check_abort():
                break

            if not wait_complete:
                trial_num -= 1
                if iti > 0:
                    time.sleep(iti)
                continue

            if perf_tracker is not None:
                perf_tracker.stimulus(target_port)
            trial_start_time = time.time()

            if is_audio:
                try:
                    self.link.speaker_set(SpeakerFrequency.FREQ_3300_HZ, SpeakerDuration.DURATION_500_MS)
                except Exception as e:
                    self._log(f"  Warning: Could not play audio cue: {e}")
            else:
                self.link.led_set(target_port, led_brightness)

            cue_on = True
            event = None

            while True:
                if self._check_abort():
                    break

                elapsed = time.time() - trial_start_time

                if cue_on and cue_duration > 0 and elapsed >= cue_duration:
                    if not is_audio:
                        self.link.led_set(target_port, 0)
                    cue_on = False

                if elapsed >= response_timeout:
                    break

                remaining = response_timeout - elapsed
                event = self.link.wait_for_event(timeout=min(0.1, remaining))
                if event is not None:
                    break

            trial_duration = time.time() - trial_start_time

            if cue_on and not is_audio:
                self.link.led_set(target_port, 0)

            if event is None:
                if perf_tracker is not None:
                    perf_tracker.timeout(correct_port=target_port, trial_duration=trial_duration)
                self._log(f"  TIMEOUT - no response in {response_timeout:.1f}s")
            elif event.port == target_port:
                if perf_tracker is not None:
                    perf_tracker.success(correct_port=target_port, trial_duration=trial_duration)
                self.link.valve_pulse(target_port, reward_ms)
                self._log(f"  SUCCESS - correct port {event.port}, reward delivered")
            else:
                if perf_tracker is not None:
                    perf_tracker.failure(
                        correct_port=target_port,
                        chosen_port=event.port,
                        trial_duration=trial_duration,
                    )
                self._log(f"  FAILURE - chose port {event.port}, expected port {target_port}")

                if punishment_s > 0:
                    self.link.spotlight_set(255, 255)
                    time.sleep(punishment_s)
                    self.link.spotlight_set(255, 0)

            if not self._check_abort() and iti > 0:
                time.sleep(iti)
