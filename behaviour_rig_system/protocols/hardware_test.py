"""
Hardware Test Protocol

A simple diagnostic protocol that sequentially tests all rig hardware:
    1. LEDs        - cycles through each port (0-5) at configurable brightness
    2. Spotlights  - cycles through each port, then all at once
    3. IR illuminator - ramps on then off
    4. Buzzers     - short pulse on each port
    5. Speaker     - plays ascending tones
    6. Valves      - short pulse on each port (OPTIONAL - disable if no water loaded)
    7. Sensors     - waits for IR beam-break events and reports them
    8. Scales      - reads and reports current weight

Each step pauses briefly so the operator can visually/audibly confirm the hardware
is responding. The protocol can be stopped at any time.

Usage:
    Select "Hardware Test" from the protocol list in the GUI and click Start.
"""

import time

try:
    from BehavLink import SpeakerFrequency, SpeakerDuration
    SPEAKER_AVAILABLE = True
except ImportError:
    SPEAKER_AVAILABLE = False


NAME = "Hardware Test"
DESCRIPTION = (
    "Diagnostic protocol that cycles through LEDs, spotlights, IR, buzzers, "
    "speaker, valves, and sensors to verify all rig hardware is working."
)

PARAMETERS = {
    "led_test_enabled": {
        "default": True,
        "label": "Test LEDs",
    },
    "led_brightness": {
        "default": 255,
        "label": "LED Brightness (0-255)",
        "min": 0,
        "max": 255,
    },
    "spotlight_test_enabled": {
        "default": True,
        "label": "Test Spotlights",
    },
    "spotlight_brightness": {
        "default": 255,
        "label": "Spotlight Brightness (0-255)",
        "min": 0,
        "max": 255,
    },
    "ir_test_enabled": {
        "default": True,
        "label": "Test IR Illuminator",
    },
    "buzzer_test_enabled": {
        "default": True,
        "label": "Test Buzzers",
    },
    "speaker_test_enabled": {
        "default": True,
        "label": "Test Speaker",
    },
    "valve_test_enabled": {
        "default": True,
        "label": "Test Valves",
    },
    "valve_duration_ms": {
        "default": 100,
        "label": "Valve Pulse Duration (ms)",
        "min": 10,
        "max": 2000,
    },
    "sensor_test_enabled": {
        "default": True,
        "label": "Test Sensors",
    },
    "sensor_test_duration": {
        "default": 10.0,
        "label": "Sensor Listen Duration (s)",
        "min": 1.0,
        "max": 60.0,
    },
    "scales_test_enabled": {
        "default": True,
        "label": "Test Scales",
    },
    "step_duration": {
        "default": 0.5,
        "label": "Step Duration (s)",
        "min": 0.1,
        "max": 5.0,
    },
    "num_cycles": {
        "default": 1,
        "label": "Number of Test Cycles",
        "min": 1,
        "max": 10,
    },
}


def run(link, params, log, check_abort, scales, perf_tracker):
    """Run the hardware test sequence."""

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
        if check_abort():
            return

        log(f"{'='*40}")
        log(f"  TEST CYCLE {cycle} / {num_cycles}")
        log(f"{'='*40}")

        # ==================================================================
        # 1. LED Test
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- LED Test ---")
        if led_enabled:
            for port in range(num_ports):
                if check_abort():
                    return
                log(f"  LED port {port} ON  (brightness {led_brightness})")
                link.led_set(port, led_brightness)
                time.sleep(step)
                link.led_set(port, 0)

            # All LEDs at once
            if not check_abort():
                log("  All LEDs ON")
                for port in range(num_ports):
                    link.led_set(port, led_brightness)
                time.sleep(step)
                for port in range(num_ports):
                    link.led_set(port, 0)
                log("  All LEDs OFF")
        else:
            log("  SKIPPED - LED test disabled")

        # ==================================================================
        # 2. Spotlight Test
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- Spotlight Test ---")
        if spotlight_enabled:
            for port in range(num_ports):
                if check_abort():
                    return
                log(f"  Spotlight port {port} ON  (brightness {spotlight_brightness})")
                link.spotlight_set(port, spotlight_brightness)
                time.sleep(step)
                link.spotlight_set(port, 0)

            # All spotlights at once
            if not check_abort():
                log("  All spotlights ON")
                link.spotlight_set(255, spotlight_brightness)
                time.sleep(step)
                link.spotlight_set(255, 0)
                log("  All spotlights OFF")
        else:
            log("  SKIPPED - spotlight test disabled")

        # ==================================================================
        # 3. IR Illuminator Test
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- IR Illuminator Test ---")
        if ir_enabled:
            log("  Ramping IR up...")
            for brightness in range(0, 256, 32):
                if check_abort():
                    link.ir_set(0)
                    return
                link.ir_set(min(brightness, 255))
                time.sleep(step / 4)
            time.sleep(step)
            log("  Ramping IR down...")
            for brightness in range(255, -1, -32):
                if check_abort():
                    link.ir_set(0)
                    return
                link.ir_set(max(brightness, 0))
                time.sleep(step / 4)
            link.ir_set(0)
            log("  IR OFF")
        else:
            log("  SKIPPED - IR test disabled")

        # ==================================================================
        # 4. Buzzer Test
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- Buzzer Test ---")
        if buzzer_enabled:
            for port in range(num_ports):
                if check_abort():
                    return
                log(f"  Buzzer port {port} ON")
                link.buzzer_set(port, True)
                time.sleep(step / 2)
                link.buzzer_set(port, False)
                time.sleep(step / 4)
        else:
            log("  SKIPPED - buzzer test disabled")

        # ==================================================================
        # 5. Speaker Test
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- Speaker Test ---")
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
                    if check_abort():
                        link.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)
                        return
                    log(f"  Playing {label}")
                    link.speaker_set(freq, SpeakerDuration.DURATION_500_MS)
                    time.sleep(0.6)  # slightly longer than the 500ms tone
                log("  Speaker test complete")
            else:
                log("  SKIPPED - BehavLink speaker enums not available")
        else:
            log("  SKIPPED - speaker test disabled")

        # ==================================================================
        # 6. Valve Test (optional)
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- Valve Test ---")
        if valve_enabled:
            for port in range(num_ports):
                if check_abort():
                    return
                log(f"  Valve port {port} pulse ({valve_ms} ms)")
                link.valve_pulse(port, valve_ms)
                time.sleep(step)
        else:
            log("  SKIPPED - valve test disabled (enable in parameters)")

        # ==================================================================
        # 7. Sensor Test (IR beam-break)
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- Sensor Test ---")
        if sensor_enabled:
            log(f"  Listening for beam-break events for {sensor_duration:.0f}s...")
            log("  Break each port's IR beam to confirm sensors are working.")

            detected_ports = set()
            start = time.time()
            # Drain any stale events first
            link.drain_events()

            while time.time() - start < sensor_duration:
                if check_abort():
                    return
                event = link.wait_for_event(timeout=0.2)
                if event is not None:
                    state = "BROKEN" if event.is_activation else "CLEAR"
                    log(f"  Sensor port {event.port}: {state}  (event_id={event.event_id})")
                    detected_ports.add(event.port)

            if detected_ports:
                sorted_ports = sorted(detected_ports)
                log(f"  Detected activity on ports: {sorted_ports}")
            else:
                log("  No sensor events detected during window")

            missing = set(range(num_ports)) - detected_ports
            if missing:
                sorted_missing = sorted(missing)
                log(f"  WARNING: No events from ports: {sorted_missing}")
        else:
            log("  SKIPPED - sensor test disabled")

        # ==================================================================
        # 8. Scales Test
        # ==================================================================
        if check_abort():
            return
        log("")
        log("--- Scales Test ---")
        if scales_enabled:
            if scales is not None:
                weight = scales.get_weight()
                if weight is not None:
                    log(f"  Current weight reading: {weight:.2f} g")
                else:
                    log("  Scales connected but returned no reading")
            else:
                log("  SKIPPED - no scales client available")
        else:
            log("  SKIPPED - scales test disabled")

    # ======================================================================
    # Done
    # ======================================================================
    log("")
    log("=" * 40)
    log("  HARDWARE TEST COMPLETE")
    log("=" * 40)
