#!/usr/bin/env python3
"""
Hardware Test Script for Behaviour Rig
=======================================

This script performs a sequential test of all hardware components on the
behaviour rig. Run this script and visually verify that each component
activates correctly.

The script will:
    1. Establish connection with the rig
    2. Test each LED individually with a brightness sweep
    3. Test each spotlight individually
    4. Test all spotlights together
    5. Test the IR illuminator
    6. Test each buzzer individually
    7. Test the overhead speaker with different tones
    8. Test each solenoid valve with a short pulse
    9. Test GPIO outputs
    10. Briefly listen for sensor events

Modify the configuration variables below to match your setup.
"""

import sys
import time

import serial

from BehavLink import (
    BehaviourRigLink,
    GPIOMode,
    SpeakerDuration,
    SpeakerFrequency,
    reset_arduino_via_dtr,
)


# =============================================================================
# Configuration
# =============================================================================

# Serial port settings
SERIAL_PORT = "COM7"  # Change to match your system (e.g., "COM3" on Windows)
BAUD_RATE = 115200

# Timing settings (seconds)
LED_STEP_DELAY = 0.05       # Delay between brightness steps during LED sweep
COMPONENT_DELAY = 0.3       # Delay after each component test
SECTION_DELAY = 1.0         # Delay between test sections
VALVE_PULSE_MS = 100        # Duration of valve test pulses in milliseconds
SENSOR_LISTEN_TIME = 3.0    # How long to listen for sensor events at the end

# Test settings
RESET_BEFORE_TEST = True    # Whether to reset the Arduino before testing


# =============================================================================
# Helper Functions
# =============================================================================

def print_header(title: str) -> None:
    """Prints a formatted section header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_test(description: str) -> None:
    """Prints a test step description."""
    print(f"  → {description}")


def print_result(message: str) -> None:
    """Prints a result or status message."""
    print(f"    {message}")


# =============================================================================
# Test Functions
# =============================================================================

def test_leds(link: BehaviourRigLink) -> None:
    """
    Tests all 6 LEDs with a brightness sweep.
    
    Each LED is swept from off to full brightness and back to off,
    then the next LED is tested.
    """
    print_header("LED Test")
    
    for port in range(6):
        print_test(f"LED {port}: brightness sweep")
        
        # Sweep up
        for brightness in range(0, 256, 32):
            link.led_set(port, brightness)
            time.sleep(LED_STEP_DELAY)
        
        # Sweep down
        for brightness in range(255, -1, -32):
            link.led_set(port, brightness)
            time.sleep(LED_STEP_DELAY)
        
        link.led_set(port, 0)
        time.sleep(COMPONENT_DELAY)
    
    print_result("All LEDs tested")


def test_spotlights(link: BehaviourRigLink) -> None:
    """
    Tests all 6 spotlights individually, then all together.
    
    Each spotlight is turned on at 50% brightness, then off.
    Finally, all spotlights are activated together.
    """
    print_header("Spotlight Test")
    
    # Test each spotlight individually
    for port in range(6):
        print_test(f"Spotlight {port}: 50% brightness")
        link.spotlight_set(port, 128)
        time.sleep(COMPONENT_DELAY)
        link.spotlight_set(port, 0)
        time.sleep(COMPONENT_DELAY)
    
    # Test all spotlights together
    print_test("All spotlights: 50% brightness")
    link.spotlight_set(255, 128)
    time.sleep(SECTION_DELAY)
    
    print_test("All spotlights: 100% brightness")
    link.spotlight_set(255, 255)
    time.sleep(SECTION_DELAY)
    
    link.spotlight_set(255, 0)
    print_result("All spotlights tested")


def test_ir_illuminator(link: BehaviourRigLink) -> None:
    """
    Tests the IR illuminator with a brightness sweep.
    
    Note: IR light is not visible to the human eye. Use a camera
    (e.g., phone camera) to verify the IR illuminator is working.
    """
    print_header("IR Illuminator Test")
    print_result("Note: Use a camera to see IR light (not visible to human eye)")
    
    print_test("IR illuminator: 50% brightness")
    link.ir_set(128)
    time.sleep(SECTION_DELAY)
    
    print_test("IR illuminator: 100% brightness")
    link.ir_set(255)
    time.sleep(SECTION_DELAY)
    
    link.ir_set(0)
    print_result("IR illuminator tested")


def test_buzzers(link: BehaviourRigLink) -> None:
    """
    Tests all 6 buzzers individually, then all together.
    
    Each buzzer is turned on briefly, then off.
    """
    print_header("Buzzer Test")
    
    # Test each buzzer individually
    for port in range(6):
        print_test(f"Buzzer {port}: short beep")
        link.buzzer_set(port, True)
        time.sleep(0.15)
        link.buzzer_set(port, False)
        time.sleep(COMPONENT_DELAY)
    
    # Test all buzzers together
    print_test("All buzzers: simultaneous beep")
    link.buzzer_set(255, True)
    time.sleep(0.3)
    link.buzzer_set(255, False)
    
    print_result("All buzzers tested")


def test_speaker(link: BehaviourRigLink) -> None:
    """
    Tests the overhead speaker with various frequency presets.
    
    Plays each frequency for a short duration to verify the speaker
    is functioning correctly.
    """
    print_header("Overhead Speaker Test")
    
    frequencies = [
        (SpeakerFrequency.FREQ_1000_HZ, "1000 Hz"),
        (SpeakerFrequency.FREQ_1500_HZ, "1500 Hz"),
        (SpeakerFrequency.FREQ_2200_HZ, "2200 Hz (GO cue)"),
        (SpeakerFrequency.FREQ_3300_HZ, "3300 Hz"),
        (SpeakerFrequency.FREQ_5000_HZ, "5000 Hz"),
        (SpeakerFrequency.FREQ_7000_HZ, "7000 Hz (NOGO cue)"),
    ]
    
    for freq, name in frequencies:
        print_test(f"Speaker: {name}")
        link.speaker_set(freq, SpeakerDuration.DURATION_200_MS)
        time.sleep(0.4)
    
    # Test continuous mode briefly
    print_test("Speaker: continuous tone (2200 Hz)")
    link.speaker_set(SpeakerFrequency.FREQ_2200_HZ, SpeakerDuration.CONTINUOUS)
    time.sleep(0.5)
    link.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)
    
    print_result("Speaker tested")


def test_valves(link: BehaviourRigLink) -> None:
    """
    Tests all 6 solenoid valves with short pulses.
    
    Each valve is pulsed briefly. You should hear/see each valve
    actuate in sequence.
    """
    print_header("Solenoid Valve Test")
    print_result(f"Pulse duration: {VALVE_PULSE_MS} ms")
    
    for port in range(6):
        print_test(f"Valve {port}: pulse")
        link.valve_pulse(port, VALVE_PULSE_MS)
        time.sleep(COMPONENT_DELAY + (VALVE_PULSE_MS / 1000))
    
    print_result("All valves tested")


def test_gpio_outputs(link: BehaviourRigLink) -> None:
    """
    Tests all 6 GPIO pins configured as outputs.
    
    Each pin is set HIGH briefly, then LOW. Use a multimeter or
    LED connected to the GPIO pins to verify output.
    """
    print_header("GPIO Output Test")
    print_result("Use multimeter or indicator LEDs to verify GPIO states")
    
    # Configure all pins as outputs
    for pin in range(6):
        link.gpio_configure(pin, GPIOMode.OUTPUT)
    
    # Test each pin
    for pin in range(6):
        print_test(f"GPIO {pin}: HIGH")
        link.gpio_set(pin, True)
        time.sleep(COMPONENT_DELAY)
        
        print_test(f"GPIO {pin}: LOW")
        link.gpio_set(pin, False)
        time.sleep(COMPONENT_DELAY)
    
    # Flash all pins together
    print_test("All GPIO pins: HIGH")
    for pin in range(6):
        link.gpio_set(pin, True)
    time.sleep(SECTION_DELAY)
    
    print_test("All GPIO pins: LOW")
    for pin in range(6):
        link.gpio_set(pin, False)
    
    print_result("All GPIO outputs tested")


def test_sensors(link: BehaviourRigLink) -> None:
    """
    Listens for sensor events for a short period.
    
    Wave your hand through any sensor gates during this period
    to verify they are detecting correctly.
    """
    print_header("Sensor Test")
    print_result(f"Listening for sensor events for {SENSOR_LISTEN_TIME} seconds...")
    print_result("Wave your hand through the sensor gates to test detection")
    print()
    
    # Clear any stale events
    link.drain_events()
    
    start_time = time.monotonic()
    events_received = 0
    
    while (time.monotonic() - start_time) < SENSOR_LISTEN_TIME:
        try:
            event = link.wait_for_event(timeout=0.1, auto_acknowledge=True)
            events_received += 1
            state = "ACTIVATED" if event.is_activation else "RELEASED"
            print_test(f"Sensor {event.port}: {state} (event_id={event.event_id})")
        except TimeoutError:
            # No event received, continue listening
            pass
    
    print()
    if events_received > 0:
        print_result(f"Received {events_received} sensor event(s)")
    else:
        print_result("No sensor events detected (this may be normal if no sensors were triggered)")


# =============================================================================
# Main Test Sequence
# =============================================================================

def run_hardware_test() -> None:
    """
    Runs the complete hardware test sequence.
    
    Opens the serial connection, establishes communication with the rig,
    and runs through all component tests in order.
    """
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           BEHAVIOUR RIG HARDWARE TEST                        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"Serial port: {SERIAL_PORT}")
    print(f"Baud rate: {BAUD_RATE}")
    print()
    
    try:
        # Open serial connection
        print("Opening serial connection...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        
        try:
            # Reset Arduino if configured
            if RESET_BEFORE_TEST:
                print("Resetting Arduino...")
                reset_arduino_via_dtr(ser)
            
            # Create link and run tests
            with BehaviourRigLink(ser) as link:
                # Establish connection
                print("Establishing connection...")
                link.send_hello()
                link.wait_hello(timeout=5.0)
                print("Connection established successfully")
                
                # Run all tests
                test_leds(link)
                time.sleep(SECTION_DELAY)
                
                test_spotlights(link)
                time.sleep(SECTION_DELAY)
                
                test_ir_illuminator(link)
                time.sleep(SECTION_DELAY)
                
                test_buzzers(link)
                time.sleep(SECTION_DELAY)
                
                test_speaker(link)
                time.sleep(SECTION_DELAY)
                
                test_valves(link)
                time.sleep(SECTION_DELAY)
                
                test_gpio_outputs(link)
                time.sleep(SECTION_DELAY)
                
                test_sensors(link)
                
                # Final summary
                print_header("Test Complete")
                print_result("All hardware tests completed successfully")
                print_result("Review the output above to verify each component")
                print()
        
        finally:
            ser.close()
            print("Serial connection closed")
    
    except serial.SerialException as e:
        print(f"Serial error: {e}", file=sys.stderr)
        print(f"Check that the device is connected to {SERIAL_PORT}", file=sys.stderr)
        sys.exit(1)
    
    except TimeoutError as e:
        print(f"Timeout error: {e}", file=sys.stderr)
        print("The rig did not respond. Check connections and try again.", file=sys.stderr)
        sys.exit(1)
    
    except KeyboardInterrupt:
        print()
        print("Test interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    run_hardware_test()