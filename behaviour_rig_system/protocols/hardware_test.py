"""
Hardware Test Protocol for Behaviour Rig.

This protocol performs a sequential test of all hardware components on the
behaviour rig. It is useful for verifying that all components are functioning
correctly before running experiments.

The test sequence includes:
    1. LED brightness sweeps
    2. Spotlight activation tests
    3. IR illuminator test
    4. Buzzer tests
    5. Speaker tone tests
    6. Solenoid valve pulse tests
    7. GPIO output tests
    8. Sensor event listening

Configurable parameters allow customisation of test durations, brightness
levels, and which components to test.
"""

import time

from BehavLink import (
    GPIOMode,
    SpeakerDuration,
    SpeakerFrequency,
)

from core.parameter_types import (
    BoolParameter,
    FloatParameter,
    IntParameter,
    Parameter,
)
from core.protocol_base import BaseProtocol, ProtocolEvent


class HardwareTestProtocol(BaseProtocol):
    """
    Protocol for testing all hardware components on the behaviour rig.

    This protocol sequentially tests each hardware component, allowing the
    user to visually verify correct operation. Parameters control timing
    and which components are tested.
    """

    # =========================================================================
    # Protocol Metadata
    # =========================================================================

    @classmethod
    def get_name(cls) -> str:
        """Return the protocol display name."""
        return "Hardware Test"

    @classmethod
    def get_description(cls) -> str:
        """Return the protocol description."""
        return (
            "Tests all hardware components on the behaviour rig sequentially. "
            "Use this to verify LEDs, spotlights, buzzers, speaker, valves, "
            "and sensors are functioning correctly."
        )

    @classmethod
    def get_parameters(cls) -> list[Parameter]:
        """Return the list of configurable parameters."""
        return [
            # Timing parameters
            FloatParameter(
                name="led_step_delay",
                display_name="LED Step Delay (s)",
                description="Delay between brightness steps during LED sweep",
                default=0.05,
                min_value=0.01,
                max_value=0.5,
                step=0.01,
                group="Timing",
                order=1,
            ),
            FloatParameter(
                name="component_delay",
                display_name="Component Delay (s)",
                description="Delay after each individual component test",
                default=0.3,
                min_value=0.1,
                max_value=2.0,
                step=0.1,
                group="Timing",
                order=2,
            ),
            FloatParameter(
                name="section_delay",
                display_name="Section Delay (s)",
                description="Delay between major test sections",
                default=1.0,
                min_value=0.5,
                max_value=5.0,
                step=0.5,
                group="Timing",
                order=3,
            ),
            IntParameter(
                name="valve_pulse_ms",
                display_name="Valve Pulse Duration (ms)",
                description="Duration of solenoid valve test pulses",
                default=100,
                min_value=10,
                max_value=1000,
                step=10,
                group="Timing",
                order=4,
            ),
            FloatParameter(
                name="sensor_listen_time",
                display_name="Sensor Listen Time (s)",
                description="Duration to listen for sensor events",
                default=3.0,
                min_value=1.0,
                max_value=10.0,
                step=1.0,
                group="Timing",
                order=5,
            ),
            # Component selection parameters
            BoolParameter(
                name="test_leds",
                display_name="Test LEDs",
                description="Include LED sweep test",
                default=True,
                group="Components",
                order=10,
            ),
            BoolParameter(
                name="test_spotlights",
                display_name="Test Spotlights",
                description="Include spotlight test",
                default=True,
                group="Components",
                order=11,
            ),
            BoolParameter(
                name="test_ir",
                display_name="Test IR Illuminator",
                description="Include IR illuminator test",
                default=True,
                group="Components",
                order=12,
            ),
            BoolParameter(
                name="test_buzzers",
                display_name="Test Buzzers",
                description="Include buzzer test",
                default=True,
                group="Components",
                order=13,
            ),
            BoolParameter(
                name="test_speaker",
                display_name="Test Speaker",
                description="Include overhead speaker test",
                default=True,
                group="Components",
                order=14,
            ),
            BoolParameter(
                name="test_valves",
                display_name="Test Valves",
                description="Include solenoid valve test",
                default=True,
                group="Components",
                order=15,
            ),
            BoolParameter(
                name="test_gpio",
                display_name="Test GPIO Outputs",
                description="Include GPIO output test",
                default=True,
                group="Components",
                order=16,
            ),
            BoolParameter(
                name="test_sensors",
                display_name="Test Sensors",
                description="Listen for sensor events at the end",
                default=True,
                group="Components",
                order=17,
            ),
            # LED test parameters
            IntParameter(
                name="led_brightness_step",
                display_name="LED Brightness Step",
                description="Brightness increment for LED sweep (1-64)",
                default=32,
                min_value=1,
                max_value=64,
                step=1,
                group="LED Settings",
                order=20,
            ),
            # Spotlight parameters
            IntParameter(
                name="spotlight_test_brightness",
                display_name="Spotlight Test Brightness",
                description="Brightness level for spotlight tests (0-255)",
                default=128,
                min_value=0,
                max_value=255,
                step=16,
                group="Spotlight Settings",
                order=30,
            ),
        ]

    # =========================================================================
    # Protocol Implementation
    # =========================================================================

    def _setup(self) -> None:
        """Initialise the protocol before running."""
        self._emit_event(ProtocolEvent(
            "status_update",
            data={"message": "Preparing hardware test..."}
        ))

    def _cleanup(self) -> None:
        """Ensure all hardware is in a safe state after completion."""
        if self.hardware is not None:
            self.hardware.all_off()
            self._emit_event(ProtocolEvent(
                "status_update",
                data={"message": "All outputs turned off"}
            ))

    def _on_abort(self) -> None:
        """Handle abort request by turning off outputs immediately."""
        if self.hardware is not None:
            self.hardware.all_off()

    def _run_protocol(self) -> None:
        """Execute the hardware test sequence."""
        # Extract parameters for convenience
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "test_started",
            data={"message": "Beginning hardware test sequence"}
        ))

        # Run each test section if enabled
        if p["test_leds"] and not self._check_abort():
            self._test_leds()
            time.sleep(p["section_delay"])

        if p["test_spotlights"] and not self._check_abort():
            self._test_spotlights()
            time.sleep(p["section_delay"])

        if p["test_ir"] and not self._check_abort():
            self._test_ir_illuminator()
            time.sleep(p["section_delay"])

        if p["test_buzzers"] and not self._check_abort():
            self._test_buzzers()
            time.sleep(p["section_delay"])

        if p["test_speaker"] and not self._check_abort():
            self._test_speaker()
            time.sleep(p["section_delay"])

        if p["test_valves"] and not self._check_abort():
            self._test_valves()
            time.sleep(p["section_delay"])

        if p["test_gpio"] and not self._check_abort():
            self._test_gpio_outputs()
            time.sleep(p["section_delay"])

        if p["test_sensors"] and not self._check_abort():
            self._test_sensors()

        self._emit_event(ProtocolEvent(
            "test_completed",
            data={"message": "Hardware test sequence complete"}
        ))

    # =========================================================================
    # Individual Test Methods
    # =========================================================================

    def _test_leds(self) -> None:
        """Test all LEDs with brightness sweeps."""
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "section_started",
            data={"section": "LEDs", "message": "Testing LEDs..."}
        ))

        for port in range(6):
            if self._check_abort():
                return

            self._emit_event(ProtocolEvent(
                "component_test",
                data={"component": "LED", "port": port, "action": "sweep"}
            ))

            # Sweep brightness up
            brightness = 0
            while brightness < 256:
                self.hardware.led_set(port, min(brightness, 255))
                time.sleep(p["led_step_delay"])
                brightness += p["led_brightness_step"]

            # Sweep brightness down
            brightness = 255
            while brightness >= 0:
                self.hardware.led_set(port, max(brightness, 0))
                time.sleep(p["led_step_delay"])
                brightness -= p["led_brightness_step"]

            self.hardware.led_set(port, 0)
            time.sleep(p["component_delay"])

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={"section": "LEDs", "message": "All LEDs tested"}
        ))

    def _test_spotlights(self) -> None:
        """Test all spotlights individually and together."""
        p = self.parameters
        brightness = p["spotlight_test_brightness"]

        self._emit_event(ProtocolEvent(
            "section_started",
            data={"section": "Spotlights", "message": "Testing spotlights..."}
        ))

        # Test each spotlight individually
        for port in range(6):
            if self._check_abort():
                return

            self._emit_event(ProtocolEvent(
                "component_test",
                data={
                    "component": "Spotlight",
                    "port": port,
                    "brightness": brightness
                }
            ))

            self.hardware.spotlight_set(port, brightness)
            time.sleep(p["component_delay"])
            self.hardware.spotlight_set(port, 0)
            time.sleep(p["component_delay"])

        if self._check_abort():
            return

        # Test all spotlights together at 50%
        self._emit_event(ProtocolEvent(
            "component_test",
            data={
                "component": "Spotlight",
                "port": "all",
                "brightness": brightness
            }
        ))
        self.hardware.spotlight_set(255, brightness)
        time.sleep(p["section_delay"])

        # Test all spotlights at 100%
        self._emit_event(ProtocolEvent(
            "component_test",
            data={"component": "Spotlight", "port": "all", "brightness": 255}
        ))
        self.hardware.spotlight_set(255, 255)
        time.sleep(p["section_delay"])

        self.hardware.spotlight_set(255, 0)

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={"section": "Spotlights", "message": "All spotlights tested"}
        ))

    def _test_ir_illuminator(self) -> None:
        """Test the IR illuminator."""
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "section_started",
            data={
                "section": "IR Illuminator",
                "message": "Testing IR illuminator (use camera to verify)..."
            }
        ))

        # Test at 50%
        self._emit_event(ProtocolEvent(
            "component_test",
            data={"component": "IR", "brightness": 128}
        ))
        self.hardware.ir_set(128)
        time.sleep(p["section_delay"])

        # Test at 100%
        self._emit_event(ProtocolEvent(
            "component_test",
            data={"component": "IR", "brightness": 255}
        ))
        self.hardware.ir_set(255)
        time.sleep(p["section_delay"])

        self.hardware.ir_set(0)

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={"section": "IR Illuminator", "message": "IR illuminator tested"}
        ))

    def _test_buzzers(self) -> None:
        """Test all buzzers individually and together."""
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "section_started",
            data={"section": "Buzzers", "message": "Testing buzzers..."}
        ))

        # Test each buzzer individually
        for port in range(6):
            if self._check_abort():
                return

            self._emit_event(ProtocolEvent(
                "component_test",
                data={"component": "Buzzer", "port": port, "action": "beep"}
            ))

            self.hardware.buzzer_set(port, True)
            time.sleep(0.15)
            self.hardware.buzzer_set(port, False)
            time.sleep(p["component_delay"])

        if self._check_abort():
            return

        # Test all buzzers together
        self._emit_event(ProtocolEvent(
            "component_test",
            data={"component": "Buzzer", "port": "all", "action": "simultaneous"}
        ))
        self.hardware.buzzer_set(255, True)
        time.sleep(0.3)
        self.hardware.buzzer_set(255, False)

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={"section": "Buzzers", "message": "All buzzers tested"}
        ))

    def _test_speaker(self) -> None:
        """Test the overhead speaker with various frequencies."""
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "section_started",
            data={"section": "Speaker", "message": "Testing speaker..."}
        ))

        frequencies = [
            (SpeakerFrequency.FREQ_1000_HZ, "1000 Hz"),
            (SpeakerFrequency.FREQ_1500_HZ, "1500 Hz"),
            (SpeakerFrequency.FREQ_2200_HZ, "2200 Hz (GO cue)"),
            (SpeakerFrequency.FREQ_3300_HZ, "3300 Hz"),
            (SpeakerFrequency.FREQ_5000_HZ, "5000 Hz"),
            (SpeakerFrequency.FREQ_7000_HZ, "7000 Hz (NOGO cue)"),
        ]

        for freq, name in frequencies:
            if self._check_abort():
                return

            self._emit_event(ProtocolEvent(
                "component_test",
                data={"component": "Speaker", "frequency": name}
            ))

            self.hardware.speaker_set(freq, SpeakerDuration.DURATION_200_MS)
            time.sleep(0.4)

        if self._check_abort():
            return

        # Test continuous mode briefly
        self._emit_event(ProtocolEvent(
            "component_test",
            data={"component": "Speaker", "frequency": "2200 Hz continuous"}
        ))
        self.hardware.speaker_set(
            SpeakerFrequency.FREQ_2200_HZ, SpeakerDuration.CONTINUOUS
        )
        time.sleep(0.5)
        self.hardware.speaker_set(
            SpeakerFrequency.OFF, SpeakerDuration.OFF
        )

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={"section": "Speaker", "message": "Speaker tested"}
        ))

    def _test_valves(self) -> None:
        """Test all solenoid valves with short pulses."""
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "section_started",
            data={
                "section": "Valves",
                "message": f"Testing valves ({p['valve_pulse_ms']} ms pulses)..."
            }
        ))

        for port in range(6):
            if self._check_abort():
                return

            self._emit_event(ProtocolEvent(
                "component_test",
                data={
                    "component": "Valve",
                    "port": port,
                    "duration_ms": p["valve_pulse_ms"]
                }
            ))

            self.hardware.valve_pulse(port, p["valve_pulse_ms"])
            time.sleep(p["component_delay"] + (p["valve_pulse_ms"] / 1000))

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={"section": "Valves", "message": "All valves tested"}
        ))

    def _test_gpio_outputs(self) -> None:
        """Test all GPIO pins as outputs."""
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "section_started",
            data={
                "section": "GPIO",
                "message": "Testing GPIO outputs (use multimeter to verify)..."
            }
        ))

        # Configure all pins as outputs
        for pin in range(6):
            self.hardware.gpio_configure(pin, GPIOMode.OUTPUT)

        # Test each pin
        for pin in range(6):
            if self._check_abort():
                return

            self._emit_event(ProtocolEvent(
                "component_test",
                data={"component": "GPIO", "pin": pin, "state": "HIGH"}
            ))
            self.hardware.gpio_set(pin, True)
            time.sleep(p["component_delay"])

            self._emit_event(ProtocolEvent(
                "component_test",
                data={"component": "GPIO", "pin": pin, "state": "LOW"}
            ))
            self.hardware.gpio_set(pin, False)
            time.sleep(p["component_delay"])

        if self._check_abort():
            return

        # Flash all pins together
        self._emit_event(ProtocolEvent(
            "component_test",
            data={"component": "GPIO", "pin": "all", "state": "HIGH"}
        ))
        for pin in range(6):
            self.hardware.gpio_set(pin, True)
        time.sleep(p["section_delay"])

        self._emit_event(ProtocolEvent(
            "component_test",
            data={"component": "GPIO", "pin": "all", "state": "LOW"}
        ))
        for pin in range(6):
            self.hardware.gpio_set(pin, False)

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={"section": "GPIO", "message": "All GPIO outputs tested"}
        ))

    def _test_sensors(self) -> None:
        """Listen for sensor events."""
        p = self.parameters

        self._emit_event(ProtocolEvent(
            "section_started",
            data={
                "section": "Sensors",
                "message": f"Listening for sensor events for {p['sensor_listen_time']} seconds..."
            }
        ))

        # Clear any stale events
        self.hardware.drain_sensor_events()

        start_time = time.monotonic()
        events_received = 0

        while (time.monotonic() - start_time) < p["sensor_listen_time"]:
            if self._check_abort():
                return

            event = self.hardware.wait_for_sensor_event(
                timeout=0.1, auto_acknowledge=True
            )

            if event is not None:
                events_received += 1
                state = "ACTIVATED" if event.is_activation else "RELEASED"

                self._emit_event(ProtocolEvent(
                    "sensor_event",
                    data={
                        "port": event.port,
                        "state": state,
                        "event_id": event.event_id
                    }
                ))

        self._emit_event(ProtocolEvent(
            "section_completed",
            data={
                "section": "Sensors",
                "message": f"Received {events_received} sensor event(s)",
                "event_count": events_received
            }
        ))
