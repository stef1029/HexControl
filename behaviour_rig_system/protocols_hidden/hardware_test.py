"""
Hardware Test Protocol (Class-based)

Sequentially tests rig hardware components.
"""

import time

from core.parameter_types import BoolParameter, FloatParameter, IntParameter
from core.protocol_base import BaseProtocol


try:
    from BehavLink import SpeakerFrequency, SpeakerDuration, GPIOMode
    SPEAKER_AVAILABLE = True
except ImportError:
    SPEAKER_AVAILABLE = False


class HardwareTestProtocol(BaseProtocol):
    """Diagnostic protocol that cycles through rig hardware outputs and sensors."""

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
            BoolParameter(name="daq_link_test_enabled", display_name="Test DAQ Links", default=True),
            BoolParameter(name="gpio_test_enabled", display_name="Test GPIOs", default=True),
            IntParameter(
                name="gpio_pulse_ms",
                display_name="DAQ Link / GPIO Pulse Duration (ms)",
                default=200,
                min_value=50,
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

    def _run_protocol(self) -> None:
        params = self.parameters
        scales = self.scales

        led_enabled = params["led_test_enabled"]
        led_brightness = params["led_brightness"]
        spotlight_enabled = params["spotlight_test_enabled"]
        spotlight_brightness = params["spotlight_brightness"]
        ir_enabled = params["ir_test_enabled"]
        buzzer_enabled = params["buzzer_test_enabled"]
        speaker_enabled = params["speaker_test_enabled"]
        valve_enabled = params["valve_test_enabled"]
        valve_ms = params["valve_duration_ms"]
        daq_link_enabled = params["daq_link_test_enabled"]
        gpio_enabled = params["gpio_test_enabled"]
        gpio_pulse_ms = params["gpio_pulse_ms"]
        sensor_enabled = params["sensor_test_enabled"]
        sensor_duration = params["sensor_test_duration"]
        scales_enabled = params["scales_test_enabled"]
        step = params["step_duration"]
        num_cycles = params["num_cycles"]

        num_ports = 6

        for cycle in range(1, num_cycles + 1):
            if self.check_stop():
                return

            self.log(f"{'=' * 40}")
            self.log(f"  TEST CYCLE {cycle} / {num_cycles}")
            self.log(f"{'=' * 40}")

            if self.check_stop():
                return
            self.log("")
            self.log("--- LED Test ---")
            if led_enabled:
                for port in range(num_ports):
                    if self.check_stop():
                        return
                    self.log(f"  LED port {port} ON  (brightness {led_brightness})")
                    self.link.led_set(port, led_brightness)
                    time.sleep(step)
                    self.link.led_set(port, 0)

                if not self.check_stop():
                    self.log("  All LEDs ON")
                    for port in range(num_ports):
                        self.link.led_set(port, led_brightness)
                    time.sleep(step)
                    for port in range(num_ports):
                        self.link.led_set(port, 0)
                    self.log("  All LEDs OFF")
            else:
                self.log("  SKIPPED - LED test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- Spotlight Test ---")
            if spotlight_enabled:
                for port in range(num_ports):
                    if self.check_stop():
                        return
                    self.log(f"  Spotlight port {port} ON  (brightness {spotlight_brightness})")
                    self.link.spotlight_set(port, spotlight_brightness)
                    time.sleep(step)
                    self.link.spotlight_set(port, 0)

                if not self.check_stop():
                    self.log("  All spotlights ON")
                    self.link.spotlight_set(255, spotlight_brightness)
                    time.sleep(step)
                    self.link.spotlight_set(255, 0)
                    self.log("  All spotlights OFF")
            else:
                self.log("  SKIPPED - spotlight test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- IR Illuminator Test ---")
            if ir_enabled:
                self.log("  Ramping IR up...")
                for brightness in range(0, 256, 32):
                    if self.check_stop():
                        self.link.ir_set(0)
                        return
                    self.link.ir_set(min(brightness, 255))
                    time.sleep(step / 4)
                time.sleep(step)
                self.log("  Ramping IR down...")
                for brightness in range(255, -1, -32):
                    if self.check_stop():
                        self.link.ir_set(0)
                        return
                    self.link.ir_set(max(brightness, 0))
                    time.sleep(step / 4)
                self.link.ir_set(0)
                self.log("  IR OFF")
            else:
                self.log("  SKIPPED - IR test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- Buzzer Test ---")
            if buzzer_enabled:
                for port in range(num_ports):
                    if self.check_stop():
                        return
                    self.log(f"  Buzzer port {port} ON")
                    self.link.buzzer_set(port, True)
                    time.sleep(step / 2)
                    self.link.buzzer_set(port, False)
                    time.sleep(step / 4)
            else:
                self.log("  SKIPPED - buzzer test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- Speaker Test ---")
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
                        if self.check_stop():
                            self.link.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)
                            return
                        self.log(f"  Playing {label}")
                        self.link.speaker_set(freq, SpeakerDuration.DURATION_500_MS)
                        time.sleep(0.6)
                    self.log("  Speaker test complete")
                else:
                    self.log("  SKIPPED - BehavLink speaker enums not available")
            else:
                self.log("  SKIPPED - speaker test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- Valve Test ---")
            if valve_enabled:
                for port in range(num_ports):
                    if self.check_stop():
                        return
                    self.log(f"  Valve port {port} pulse ({valve_ms} ms)")
                    self.link.valve_pulse(port, valve_ms)
                    time.sleep(step)
            else:
                self.log("  SKIPPED - valve test disabled (enable in parameters)")

            if self.check_stop():
                return
            self.log("")
            self.log("--- DAQ Link Test ---")
            if daq_link_enabled:
                pulse_step_s = gpio_pulse_ms / 1000.0
                num_links = self.link.NUM_DAQ_LINK_PINS

                for i in range(num_links):
                    if self.check_stop():
                        return
                    self.log(f"  DAQ_LINK{i} HIGH ({gpio_pulse_ms} ms)")
                    self.link.daq_link_set(i, True)
                    time.sleep(pulse_step_s)
                    self.link.daq_link_set(i, False)
                    time.sleep(step / 4)

                if not self.check_stop():
                    self.log("  All DAQ links HIGH")
                    for i in range(num_links):
                        self.link.daq_link_set(i, True)
                    time.sleep(pulse_step_s)
                    for i in range(num_links):
                        self.link.daq_link_set(i, False)
                    self.log("  All DAQ links LOW")
            else:
                self.log("  SKIPPED - DAQ link test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- GPIO Test ---")
            if gpio_enabled:
                num_gpio = self.link.NUM_GPIO_PINS
                pulse_step_s = gpio_pulse_ms / 1000.0

                for pin in range(num_gpio):
                    if self.check_stop():
                        return
                    self.log(f"  GPIO pin {pin} HIGH ({gpio_pulse_ms} ms)")
                    self.link.gpio_set(pin, True)
                    time.sleep(pulse_step_s)
                    self.link.gpio_set(pin, False)
                    time.sleep(step / 4)

                if not self.check_stop():
                    self.log("  All GPIOs HIGH")
                    for pin in range(num_gpio):
                        self.link.gpio_set(pin, True)
                    time.sleep(pulse_step_s)
                    for pin in range(num_gpio):
                        self.link.gpio_set(pin, False)
                    self.log("  All GPIOs LOW")
            else:
                self.log("  SKIPPED - GPIO test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- Sensor Test ---")
            if sensor_enabled:
                self.log(f"  Listening for beam-break events for {sensor_duration:.0f}s...")
                self.log("  Break each port's IR beam to confirm sensors are working.")

                detected_ports = set()
                start = time.time()
                self.link.drain_events()

                while time.time() - start < sensor_duration:
                    if self.check_stop():
                        return
                    event = self.link.wait_for_event(timeout=0.2)
                    if event is not None:
                        state = "BROKEN" if event.is_activation else "CLEAR"
                        self.log(f"  Sensor port {event.port}: {state}  (event_id={event.event_id})")
                        detected_ports.add(event.port)

                if detected_ports:
                    sorted_ports = sorted(detected_ports)
                    self.log(f"  Detected activity on ports: {sorted_ports}")
                else:
                    self.log("  No sensor events detected during window")

                missing = set(range(num_ports)) - detected_ports
                if missing:
                    sorted_missing = sorted(missing)
                    self.log(f"  WARNING: No events from ports: {sorted_missing}")
            else:
                self.log("  SKIPPED - sensor test disabled")

            if self.check_stop():
                return
            self.log("")
            self.log("--- Scales Test ---")
            if scales_enabled:
                if scales is not None:
                    weight = scales.get_weight()
                    if weight is not None:
                        self.log(f"  Current weight reading: {weight:.2f} g")
                    else:
                        self.log("  Scales connected but returned no reading")
                else:
                    self.log("  SKIPPED - no scales client available")
            else:
                self.log("  SKIPPED - scales test disabled")

        self.log("")
        self.log("=" * 40)
        self.log("  HARDWARE TEST COMPLETE")
        self.log("=" * 40)
