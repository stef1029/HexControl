"""
Phase 2 implementation: Reward given for over-threshold scales readings.
"""

import time
import keyboard
from colorama import Fore

from common.arduino import setup_arduino_case, wait_for_start_signal, check_port_was_received
from common.scales import weight, pressure_plate

# Phase-specific constants
PHASE_NUMBER = 2
ARDUINO_CASE = 2
EXIT_KEY = 'esc'
TRIAL_TIMEOUT = 11
TRIAL_PRINT_DELIMITER = "----------------------------------------"

def get_phase_params(params):
    """
    Get phase-specific parameters.
    
    Args:
        params (dict): Existing parameters
        
    Returns:
        dict: Phase-specific parameters
    """
    phase_params = {}
    
    # Port selection
    if "port" not in params:
        port = int(input("Enter port number (1-6): ")) - 1
        phase_params["port"] = port
    
    return phase_params

def run_phase(ser, session_params, metadata, rd, timer, log, scales_data):
    """
    Run Phase 2 experiment.
    
    Args:
        ser: Serial connection to Arduino
        session_params (dict): Session parameters
        metadata (dict): Metadata dictionary to update
        rd: Scales object
        timer (function): Timer function
        log (list): Log to append to
        scales_data (list): Scales data to append to
        
    Returns:
        int: Number of trials completed
    """
    # Extract parameters
    port = session_params.get("port", 0)
    mouse_weight = session_params.get("mouse_weight", 20)
    mouse_weight_offset = 2
    number_of_trials = session_params.get("number_of_trials", 0)
    
    # Setup
    print("Phase 2: Reward given for over-threshold scales readings.")
    print("In phase 2, reward is only given at one port.")
    print(f"Use setting {ARDUINO_CASE} on arduino")
    
    # Setup Arduino
    setup_arduino_case(ser, ARDUINO_CASE)
    
    # Wait for start signal
    if not wait_for_start_signal(ser):
        return 0
    
    # Update metadata
    metadata["Port"] = port + 1
    metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
    metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]
    
    # Main experiment loop
    m_break = False
    trial_count = 0
    
    rd.clear_buffer()
    while True:
        state, activation_time = pressure_plate(
            mouse_weight - mouse_weight_offset, 
            0.2, 
            rd, 
            timer, 
            scales_data
        )
        
        if state:
            ser.read_all()  # Clear serial buffer
            ser.write(f"{port+1}".encode())  # Send reward port number to arduino
            log.append(f"OUT;{timer():0.4f}")  # Add time to log
            
            trial_count += 1
            print("Reward given")
            
            receive_time = time.perf_counter()
            incoming, error = check_port_was_received(ser, receive_time)
            
            time.sleep(0.01)
            try:
                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
            except IndexError:
                pass
                
            if not error and incoming[0] == "R":
                time.sleep(0.01)
                ser.read_all()  # Clear serial buffer
                
                while True:
                    time.sleep(0.001)
                    # Wait for arduino to say that reward has been taken
                    weight(rd, timer, scales_data)  # Update scales_data list
                    incoming = ser.readline().decode("utf-8").strip()  # Read arduino port number
                    
                    if len(incoming) > 1 and incoming[0] == "C":
                        ser.read_all()
                        if incoming[1] == str(port+1):
                            print("Reward taken")
                            print(f"Trials: {trial_count}")
                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")  # Add time to log
                            
                            if trial_count >= number_of_trials and number_of_trials != 0:
                                m_break = True
                                
                            print(TRIAL_PRINT_DELIMITER)
                            break
                            
                        if incoming[1] != str(port+1):
                            if incoming[1] == "F":
                                print("Trial timeout")
                                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                
                                if trial_count >= number_of_trials and number_of_trials != 0:
                                    m_break = True
                                    
                                print(TRIAL_PRINT_DELIMITER)
                                break
                            else:
                                print(f"Port {incoming[1]} touched")
                                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                
                    if time.perf_counter() - receive_time > TRIAL_TIMEOUT:
                        print(f"Serial error, timeout: {incoming}")
                        ser.read_all()  # Clear serial buffer
                        print(TRIAL_PRINT_DELIMITER)
                        break
                        
                    if keyboard.is_pressed(EXIT_KEY):  # If exit key is pressed, end program
                        m_break = True
                        
                    if m_break:
                        break
                        
        if keyboard.is_pressed(EXIT_KEY):  # If exit key is pressed, end program
            m_break = True
            
        if m_break:
            break
            
    return trial_count