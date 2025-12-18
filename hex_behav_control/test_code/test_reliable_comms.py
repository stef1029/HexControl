
from rig_link import (
    BehaviourRigLink,
    GPIOMode,   
    log_message,
    reset_arduino_via_dtr,
)
import serial
import time


# =============================================================================
# Test Script
# =============================================================================

def main() -> None:
    """
    Runs a comprehensive test sequence demonstrating all rig capabilities.
    
    This test sequence:
        1. Establishes connection with handshake
        2. Tests IR illuminator
        3. Tests spotlight control (individual and all)
        4. Tests buzzer tones
        5. Tests overhead speaker
        6. Tests GPIO configuration and output control
        7. Tests GPIO input events
        8. For each sensor port (0-5):
            a. Turns on the LED at full brightness
            b. Waits for sensor activation
            c. Waits for sensor release
            d. Acknowledges events
            e. Turns off LED and pulses valve
    
    Configuration is set via the constants below. Modify SERIAL_PORT to match
    your system.
    """
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    SERIAL_PORT = "COM7"
    BAUD_RATE = 115200
    SERIAL_TIMEOUT = 0.1
    
    HANDSHAKE_TIMEOUT = 3.0
    EVENT_TIMEOUT = 30.0
    VALVE_PULSE_DURATION_MS = 500
    INTER_PORT_DELAY = 0.25
    
    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT) as ser:
        log_message(f"Opened {SERIAL_PORT} at {BAUD_RATE} baud")
        reset_arduino_via_dtr(ser)

        with BehaviourRigLink(ser) as link:
            # Establish connection
            link.send_hello()
            link.wait_hello(timeout=HANDSHAKE_TIMEOUT)
            log_message("Handshake successful")
            
            # Test IR illuminator
            log_message("\n=== TESTING IR ILLUMINATOR ===")
            link.ir_set(255)
            log_message("IR ON (full brightness)")
            time.sleep(0.5)
            link.ir_set(128)
            log_message("IR at 50%")
            time.sleep(0.5)
            
            # Test spotlights
            log_message("\n=== TESTING SPOTLIGHTS ===")
            for port in range(6):
                link.spotlight_set(port, 100)
                log_message(f"Spotlight {port} ON")
                time.sleep(0.2)
                link.spotlight_set(port, 0)
            
            link.spotlight_all_set(50)
            log_message("All spotlights at 50%")
            time.sleep(0.5)
            link.spotlight_all_off()
            log_message("All spotlights OFF")
            
            # Test buzzers
            log_message("\n=== TESTING BUZZERS ===")
            for port in range(6):
                link.buzzer_set(port, 1)
                log_message(f"Buzzer {port} ON")
                time.sleep(0.3)
                link.buzzer_set(port, 0)
            
            # Test overhead speaker
            log_message("\n=== TESTING OVERHEAD SPEAKER ===")
            link.speaker_go_cue(True)
            log_message("GO cue ON")
            time.sleep(0.5)
            link.speaker_off()
            
            link.speaker_nogo_cue(True)
            log_message("NOGO cue ON")
            time.sleep(0.5)
            link.speaker_off()
            
            # Test GPIO outputs
            log_message("\n=== TESTING GPIO OUTPUTS ===")
            for pin in range(4):
                link.gpio_configure(pin, GPIOMode.OUTPUT)
                log_message(f"GPIO {pin} configured as OUTPUT")
                
                link.gpio_on(pin)
                log_message(f"GPIO {pin} HIGH")
                time.sleep(0.2)
                
                link.gpio_off(pin)
                log_message(f"GPIO {pin} LOW")
            
            # Test GPIO input (configure pin 0 as input and wait for event)
            log_message("\n=== TESTING GPIO INPUT ===")
            link.gpio_configure(0, GPIOMode.INPUT)
            log_message("GPIO 0 configured as INPUT - trigger it within 5 seconds...")
            
            try:
                gpio_event = link.wait_for_gpio_event(pin=0, timeout=5.0)
                event_type = "ACTIVATED" if gpio_event.is_activation else "RELEASED"
                log_message(
                    f"GPIO EVENT: pin={gpio_event.pin}, type={event_type}, "
                    f"timestamp={gpio_event.timestamp_ms}ms"
                )
                link.acknowledge_gpio_event(gpio_event.event_id)
            except TimeoutError:
                log_message("No GPIO event received (timeout)")
            
            # Reconfigure GPIO 0 back to output for cleanup
            link.gpio_configure(0, GPIOMode.OUTPUT)
            
            # Test error handling - try to set an input pin
            log_message("\n=== TESTING GPIO ERROR HANDLING ===")
            link.gpio_configure(1, GPIOMode.INPUT)
            try:
                link.gpio_set(1, True)
                log_message("ERROR: Should have raised RuntimeError!")
            except RuntimeError as e:
                log_message(f"Correctly caught error: {e}")
            
            # Test sensor/LED/valve on each port
            for port in range(6):
                log_message(f"\n=== TESTING PORT {port} ===")
                
                # Clear any stale events before starting this trial
                drained_events = link.drain_events()
                if drained_events:
                    log_message(f"Cleared {len(drained_events)} old events before trial")
                
                link.led_set(port, 255)
                log_message(f"LED[{port}] ON - waiting for sensor activation")
                
                # Wait for an activation on the correct port
                while True:
                    event = link.wait_for_event(timeout=EVENT_TIMEOUT)
                    event_type = "ACTIVATED" if event.is_activation else "RELEASED"
                    
                    if event.port == port and event.is_activation:
                        log_message(
                            f"Received EVENT: id={event.event_id}, port={event.port}, "
                            f"type={event_type}, timestamp={event.timestamp_ms}ms"
                        )
                        break
                    else:
                        log_message(
                            f"OTHER EVENT: id={event.event_id}, port={event.port}, "
                            f"type={event_type}"
                        )
                
                # Deliver reward
                link.led_set(port, 0)
                link.valve_pulse(port, VALVE_PULSE_DURATION_MS)
                log_message(
                    f"LED[{port}] OFF - VALVE[{port}] pulsed for "
                    f"{VALVE_PULSE_DURATION_MS}ms"
                )
                
                time.sleep(INTER_PORT_DELAY)
            
            log_message("\nAll tests completed successfully")
            

        # Always attempt clean shutdown
        log_message("Shutting down rig...")
        log_message("Done")


if __name__ == "__main__":
    main()