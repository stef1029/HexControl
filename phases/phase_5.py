"""
Phase 5 implementation: New port introduced. Mice allowed to explore, incorrect touches not penalized.
"""

import time
import keyboard
from colorama import Fore

from common.arduino import setup_arduino_case, wait_for_start_signal, check_port_was_received
from common.scales import weight, pressure_plate

# Phase-specific constants
PHASE_NUMBER = "5"
ARDUINO_CASE = 4  # Arduino setting for phase 5 is 4
EXIT_KEY = 'esc'
TRIAL_TIMEOUT = 10
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
    
    # Get port number for this phase
    try:
        phase_params["port"] = int(input("Enter port number (1-6): ").strip())
    except ValueError:
        print(Fore.RED + "Invalid port number, must be a number.")
        phase_params["port"] = int(input("Enter port number (1-6): ").strip())
    
    return phase_params

def run_phase(ser, session_params, metadata, rd, timer, log, scales_data):
    """
    Run Phase 5 experiment.
    
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
    mouse_weight = session_params.get("mouse_weight", 20)
    mouse_weight_offset = 2
    number_of_trials = session_params.get("number_of_trials", 0)
    port = session_params.get("port", 1) - 1  # Convert from 1-based to 0-based
    
    # Setup
    print(Fore.CYAN + f"Phase {PHASE_NUMBER}: New port introduced. Mice allowed to explore, incorrect touches not penalized.")
    print(Fore.CYAN + "In phase 5, reward is only given at one, new, port.")
    print(Fore.YELLOW + f"Use setting {ARDUINO_CASE} on arduino")
    
    # Setup Arduino
    setup_arduino_case(ser, ARDUINO_CASE)
    
    # Update metadata
    metadata["Port"] = port + 1
    
    # Wait for start signal
    if not wait_for_start_signal(ser):
        return 0
    
    # Clear serial buffer
    ser.read_all()
    
    # Update metadata
    metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
    pause_time = 1  # Set wait time for mouse to pause on platform before reward cue given
    metadata["Platform pause time"] = pause_time
    metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]
    
    # Main experiment loop
    m_break = False
    trial_count = 0
    
    rd.clear_buffer()
    while True:
        state, activation_time = pressure_plate(
            mouse_weight - mouse_weight_offset, 
            pause_time, 
            rd, 
            timer, 
            scales_data
        )
        
        if state:
            # Send reward port number to arduino
            ser.write(f"{port+1}".encode())
            log.append(f"OUT;{timer():0.4f}")
            
            trial_count += 1
            print(Fore.CYAN + "Cue given")
            receive_time = time.perf_counter()
            
            # Check if port was received
            incoming, error = check_port_was_received(ser, receive_time)
            try:
                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
            except IndexError:
                pass
            
            if not error:
                if incoming[0] == "R":
                    ser.read_all()  # Clear serial buffer
                
                # Wait for arduino to say that reward has been taken
                while True:
                    time.sleep(0.001)
                    weight(rd, timer, scales_data)  # Continue updating scales data
                    
                    incoming = ser.readline().decode("utf-8").strip()
                    if len(incoming) > 1:
                        if incoming[0] == "C":
                            ser.read_all()
                            if incoming[1] == str(port+1):
                                print(Fore.GREEN + "Reward taken")
                                print(Fore.CYAN + f"Trials: {trial_count}")
                                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")
                                
                                if trial_count >= number_of_trials and number_of_trials != 0:
                                    m_break = True
                                    
                                print(TRIAL_PRINT_DELIMITER)
                                break
                            
                            if incoming[1] != str(port+1):
                                if incoming[1] == "F":
                                    print(Fore.YELLOW + "Trial timeout")  # Yellow for timeout in phase 5
                                    log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                    
                                    if trial_count >= number_of_trials and number_of_trials != 0:
                                        m_break = True
                                        
                                    print(TRIAL_PRINT_DELIMITER)
                                    break
                                else:
                                    # In Phase 5, incorrect port touches are logged but not penalized
                                    print(Fore.YELLOW + f"Port {incoming[1]} touched")  # Yellow for non-penalized incorrect touch
                                    log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                    
                    if time.perf_counter() - receive_time > TRIAL_TIMEOUT:
                        print(Fore.RED + f"Serial error, timeout: {incoming}")
                        print(TRIAL_PRINT_DELIMITER)
                        break
                        
                    if keyboard.is_pressed(EXIT_KEY):
                        m_break = True
                    
                    if m_break:
                        break
        
        if keyboard.is_pressed(EXIT_KEY):
            m_break = True
        
        if m_break:
            break
    
    return trial_count