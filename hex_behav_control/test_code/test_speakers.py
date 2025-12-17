"""
Simple debug script for buzzer 2.
"""

import time
import serial

from test_reliable_comms import (
    BehaviourRigLink,
    log_message,
    reset_arduino_via_dtr,
)

# Configuration
SERIAL_PORT = "COM7"
BAUD_RATE = 115200

port = 2

def main() -> None:
    """Tests buzzer with different timing patterns."""
    
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1) as ser:
        log_message(f"Opened {SERIAL_PORT}")
        reset_arduino_via_dtr(ser)
        
        with BehaviourRigLink(ser) as link:
            log_message("Starting buzzer test...")
            
            # Test 1: Simple on/off
            log_message("Test 1: Simple on/off")
            link.buzzer_set(port, 1000)
            time.sleep(1.0)
            link.buzzer_set(port, 0)
            time.sleep(0.5)
            
            # Test 2: Pulsed buzzer
            log_message("Test 2: Pulsed buzzer")
            for _ in range(5):
                link.buzzer_set(port, 1000)
                time.sleep(0.2)
                link.buzzer_set(port, 0)
                time.sleep(0.2)

            
            log_message("Buzzer test completed.")
            log_message("All tests completed successfully")


if __name__ == "__main__":
    main()