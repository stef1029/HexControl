"""
Hardware Test Protocol (Class-based)

Sequentially tests rig hardware components.
"""

import time

from core.parameter_types import BoolParameter, FloatParameter, IntParameter
from core.protocol_base import BaseProtocol, ProtocolEvent


try:
    from BehavLink import SpeakerFrequency, SpeakerDuration
    SPEAKER_AVAILABLE = True
except ImportError:
    SPEAKER_AVAILABLE = False


class HardwareTestProtocol(BaseProtocol):
    """Diagnostic protocol that cycles through rig hardware outputs and sensors."""

    _scales_client = None

    @classmethod
    def get_name(cls) -> str:
        return "Hardware Test"

    @classmethod
    def get_description(cls) -> str:
        return (
            "Diagnostic protocol that cycles through LEDs, spotlights, IR, buzzers, "
            "speaker, valves, and sensors to verify all rig hardware is working."
        )

    @classmethod
    def get_parameters(cls) -> list:
        return [
            BoolParameter(name="led_test_enabled", display_name="Test LEDs", default=True),
            IntParameter(
                name="led_brightness",
                display_name="LED Brightness (0-255)",
                default=255,
                min_value=0,
                max_value=255,
            ),
            BoolParameter(name="spotlight_test_enabled", display_name="Test Spotlights", default=True),
            IntParameter(
                name="spotlight_brightness",
                display_name="Spotlight Brightness (0-255)",
                default=255,
                min_value=0,
                max_value=255,
            ),
            BoolParameter(name="ir_test_enabled", display_name="Test IR Illuminator", default=True),
            BoolParameter(name="buzzer_test_enabled", display_name="Test Buzzers", default=True),
            BoolParameter(name="speaker_test_enabled", display_name="Test Speaker", default=True),
            BoolParameter(name="valve_test_enabled", display_name="Test Valves", default=True),
            IntParameter(
                name="valve_duration_ms",
                display_name="Valve Pulse Duration (ms)",
                default=100,
                min_value=10,
                max_value=2000,
            ),
            BoolParameter(name="sensor_test_enabled", display_name="Test Sensors", default=True),
            FloatParameter(
                name="sensor_test_duration",
                display_name="Sensor Listen Duration (s)",
                default=10.0,
                min_value=1.0,
                max_value=60.0,
            ),
            BoolParameter(name="scales_test_enabled", display_name="Test Scales", default=True),
            FloatParameter(
                name="step_duration",
                display_name="Step Duration (s)",
                default=0.5,
                min_value=0.1,
                max_value=5.0,
            ),
            IntParameter(
                name="num_cycles",
                display_name="Number of Test Cycles",
                default=1,
                min_value=1,
                max_value=10,
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

        led_enabled = params["led_test_enabled"]
        led_brightness = params["led_brightness"]
        spotlight_enabled = params["spotlight_test_enabled"]
        spotlight_brightness = params["spotlight_brightness"]
        ir_enabled = params["ir_test_enabled"]
        buzzer_enabled = params["buzzer_test_enabled"]
        speaker_enabled = params["speaker_test_enabled"]
        valve_enabled = params["valve_test_enabled"]
        valve_ms = params["valve_duration_ms"]
        sensor_enabled = params["sensor_test_enabled"]
        sensor_duration = params["sensor_test_duration"]
        scales_enabled = params["scales_test_enabled"]
        step = params["step_duration"]
        num_cycles = params["num_cycles"]

        num_ports = 6

        for cycle in range(1, num_cycles + 1):
            if self._check_abort():
                return

            self._log(f"{'=' * 40}")
            self._log(f"  TEST CYCLE {cycle} / {num_cycles}")
            self._log(f"{'=' * 40}")

            if self._check_abort():
                return
            self._log("")
            self._log("--- LED Test ---")
            if led_enabled:
                for port in range(num_ports):
                    if self._check_abort():
                        return
                    self._log(f"  LED port {port} ON  (brightness {led_brightness})")
                    self.link.led_set(port, led_brightness)
                    time.sleep(step)
                    self.link.led_set(port, 0)

                if not self._check_abort():
                    self._log("  All LEDs ON")
                    for port in range(num_ports):
                        self.link.led_set(port, led_brightness)
                    time.sleep(step)
                    for port in range(num_ports):
                        self.link.led_set(port, 0)
                    self._log("  All LEDs OFF")
            else:
                self._log("  SKIPPED - LED test disabled")

            if self._check_abort():
                return
            self._log("")
            self._log("--- Spotlight Test ---")
            if spotlight_enabled:
                for port in range(num_ports):
                    if self._check_abort():
                        return
                    self._log(f"  Spotlight port {port} ON  (brightness {spotlight_brightness})")
                    self.link.spotlight_set(port, spotlight_brightness)
                    time.sleep(step)
                    self.link.spotlight_set(port, 0)

                if not self._check_abort():
                    self._log("  All spotlights ON")
                    self.link.spotlight_set(255, spotlight_brightness)
                    time.sleep(step)
                    self.link.spotlight_set(255, 0)
                    self._log("  All spotlights OFF")
            else:
                self._log("  SKIPPED - spotlight test disabled")

            if self._check_abort():
                return
            self._log("")
            self._log("--- IR Illuminator Test ---")
            if ir_enabled:
                self._log("  Ramping IR up...")
                for brightness in range(0, 256, 32):
                    if self._check_abort():
                        self.link.ir_set(0)
                        return
                    self.link.ir_set(min(brightness, 255))
                    time.sleep(step / 4)
                time.sleep(step)
                self._log("  Ramping IR down...")
                for brightness in range(255, -1, -32):
                    if self._check_abort():
                        self.link.ir_set(0)
                        return
                    self.link.ir_set(max(brightness, 0))
                    time.sleep(step / 4)
                self.link.ir_set(0)
                self._log("  IR OFF")
            else:
                self._log("  SKIPPED - IR test disabled")

            if self._check_abort():
                return
            self._log("")
            self._log("--- Buzzer Test ---")
            if buzzer_enabled:
                for port in range(num_ports):
                    if self._check_abort():
                        return
                    self._log(f"  Buzzer port {port} ON")
                    self.link.buzzer_set(port, True)
                    time.sleep(step / 2)
                    self.link.buzzer_set(port, False)
                    time.sleep(step / 4)
            else:
                self._log("  SKIPPED - buzzer test disabled")

            if self._check_abort():
                return
            self._log("")
            self._log("--- Speaker Test ---")
            if speaker_enabled:
                if SPEAKER_AVAILABLE:
                    frequencies = [
                        (SpeakerFrequency.FREQ_1000_HZ, "1000 Hz"),
                        (SpeakerFrequency.FREQ_1500_HZ, "1500 Hz"),
                        (SpeakerFrequency.FREQ_2200_HZ, "2200 Hz"),
                        (SpeakerFrequency.FREQ_3300_HZ, "3300 Hz"),
                        (SpeakerFrequency.FREQ_5000_HZ, "5000 Hz"),
                        (SpeakerFrequency.FREQ_7000_HZ, "7000 Hz"),
                    ]
                    for freq, label in frequencies:
                        if self._check_abort():
                            self.link.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)
                            return
                        self._log(f"  Playing {label}")
                        self.link.speaker_set(freq, SpeakerDuration.DURATION_500_MS)
                        time.sleep(0.6)
                    self._log("  Speaker test complete")
                else:
                    self._log("  SKIPPED - BehavLink speaker enums not available")
            else:
                self._log("  SKIPPED - speaker test disabled")

            if self._check_abort():
                return
            self._log("")
            self._log("--- Valve Test ---")
            if valve_enabled:
                for port in range(num_ports):
                    if self._check_abort():
                        return
                    self._log(f"  Valve port {port} pulse ({valve_ms} ms)")
                    self.link.valve_pulse(port, valve_ms)
                    time.sleep(step)
            else:
                self._log("  SKIPPED - valve test disabled (enable in parameters)")

            if self._check_abort():
                return
            self._log("")
            self._log("--- Sensor Test ---")
            if sensor_enabled:
                self._log(f"  Listening for beam-break events for {sensor_duration:.0f}s...")
                self._log("  Break each port's IR beam to confirm sensors are working.")

                detected_ports = set()
                start = time.time()
                self.link.drain_events()

                while time.time() - start < sensor_duration:
                    if self._check_abort():
                        return
                    event = self.link.wait_for_event(timeout=0.2)
                    if event is not None:
                        state = "BROKEN" if event.is_activation else "CLEAR"
                        self._log(f"  Sensor port {event.port}: {state}  (event_id={event.event_id})")
                        detected_ports.add(event.port)

                if detected_ports:
                    sorted_ports = sorted(detected_ports)
                    self._log(f"  Detected activity on ports: {sorted_ports}")
                else:
                    self._log("  No sensor events detected during window")

                missing = set(range(num_ports)) - detected_ports
                if missing:
                    sorted_missing = sorted(missing)
                    self._log(f"  WARNING: No events from ports: {sorted_missing}")
            else:
                self._log("  SKIPPED - sensor test disabled")

            if self._check_abort():
                return
            self._log("")
            self._log("--- Scales Test ---")
            if scales_enabled:
                if scales is not None:
                    weight = scales.get_weight()
                    if weight is not None:
                        self._log(f"  Current weight reading: {weight:.2f} g")
                    else:
                        self._log("  Scales connected but returned no reading")
                else:
                    self._log("  SKIPPED - no scales client available")
            else:
                self._log("  SKIPPED - scales test disabled")

        self._log("")
        self._log("=" * 40)
        self._log("  HARDWARE TEST COMPLETE")
        self._log("=" * 40)
