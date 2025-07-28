"""
Phase 10 implementation: LED catch trial experiment.
"""

import time
import random
import keyboard
from colorama import Fore
from datetime import datetime

from common.arduino import setup_arduino_case, wait_for_start_signal, check_port_was_received
from common.scales import weight, pressure_plate

# Phase-specific constants
PHASE_NUMBER = "10"
ARDUINO_CASE = 8  # Arduino setting for phase 10
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
    
    # Get cue duration
    phase_params["cue_duration"] = input("Enter cue duration (ms) (0 = unlimited) (1 = mixed): ").strip()
    
    # Get catch trial type
    phase_params["catch_type"] = input("Enter catch trial type (w = wait time, l = led brightness): ").strip()
    if phase_params["catch_type"] not in ["w", "l"]:
        print(Fore.RED + "Invalid catch trial type")
        phase_params["catch_type"] = input("Enter catch trial type (w = wait time, l = led brightness): ").strip()
    
    # Get catch parameters based on type
    if phase_params["catch_type"] == "l":
        try:
            phase_params["catch_brightness"] = int(input("Enter led brightness (1-10000): ").strip())
        except ValueError:
            print(Fore.RED + "Invalid led brightness")
            phase_params["catch_brightness"] = int(input("Enter dimmer led brightness (1-10000): ").strip())
        phase_params["catch_wait"] = None
    
    if phase_params["catch_type"] == "w":
        try:
            phase_params["catch_wait"] = int(input("Enter longer wait time (ms): ").strip())/1000
            phase_params["catch_brightness"] = 10000
        except ValueError:
            print(Fore.RED + "Invalid wait time")
            phase_params["catch_wait"] = float(input("Enter longer wait time (ms): ").strip())/1000
    
    # Use all 6 ports by default
    phase_params["ports_in_use"] = [0, 1, 2, 3, 4, 5]
    
    return phase_params

def run_phase(ser, session_params, metadata, rd, timer, log, scales_data):
    """
    Run Phase 10 experiment.
    
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
    cue_duration = session_params.get("cue_duration", "0")
    catch_type = session_params.get("catch_type", "l")
    catch_brightness = session_params.get("catch_brightness", 5000)
    catch_wait = session_params.get("catch_wait", None)
    ports_in_use = session_params.get("ports_in_use", [0, 1, 2, 3, 4, 5])
    
    # Setup
    print(Fore.CYAN + "LED catch trial task")
    print(Fore.YELLOW + f"Use setting {ARDUINO_CASE} on arduino")
    
    # Set up trial order
    number_of_ports = len(ports_in_use)
    trial_order = None
    
    if number_of_trials != 0:
        trial_order = []
        for i in range(number_of_trials):
            trial_order.append(i % number_of_ports)
        random.shuffle(trial_order)
    
    # Generate catch trial sequence
    frequency = 5  # 1 in 5 trials are catch trials
    length = 1000  # More than enough trials
    space = 3      # Minimum spacing between catch trials
    num_ones = length // frequency
    catch_sequence = [0] * length  # Start with all zeros (normal trials)
    
    # Determine positions for catch trials (1s)
    possible_positions = [i for i in range(0, length, space)]
    one_positions = random.sample(possible_positions, num_ones)
    for pos in one_positions:
        catch_sequence[pos] = 1
    
    # Setup Arduino
    setup_arduino_case(ser, ARDUINO_CASE)
    
    # Wait for start signal
    if not wait_for_start_signal(ser):
        return 0
    
    # Send cue duration to Arduino
    ser.write(f"{cue_duration}".encode())
    
    # Wait for confirmation
    start = time.perf_counter()
    while True:
        time.sleep(0.001)
        incoming = ser.readline().decode("utf-8").strip()
        if len(incoming) > 0:
            break
        if time.perf_counter() - start > 1:
            print(Fore.RED + "Start signal timeout")
            break
    
    # Send catch brightness to Arduino
    ser.write(f"{catch_brightness}".encode())
    
    # Wait for final confirmation
    start = time.perf_counter()
    while True:
        time.sleep(0.001)
        incoming = ser.readline().decode("utf-8").strip()
        if len(incoming) > 0:
            print(Fore.GREEN + f"Start signal received {datetime.now().strftime('%H%M%S')}")
            break
        if time.perf_counter() - start > 1:
            print(Fore.RED + "Start signal timeout")
            break
    
    ser.read_all()  # Clear serial buffer
    
    # Update metadata
    metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
    metadata["Port"] = [(port + 1) for port in ports_in_use]
    metadata["Platform pause time"] = 1
    metadata["Cue duration"] = cue_duration
    metadata["Catch trial type"] = catch_type
    metadata["Catch brightness"] = catch_brightness
    metadata["Catch wait time"] = catch_wait
    metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]
    
    # Main experiment loop
    m_break = False
    trial_count = 0
    successes = 0
    normal_pause_time = 1
    pause_time = 1
    
    rd.clear_buffer()
    while True:
        # Set pause time for wait-type catch trials
        if catch_type == 'w':
            if catch_sequence[trial_count] == 1:
                pause_time = catch_wait
            else:
                pause_time = normal_pause_time
        
        state, activation_time = pressure_plate(
            mouse_weight - mouse_weight_offset, 
            pause_time, 
            rd, 
            timer, 
            scales_data
        )
        
        if state:
            state = False
            
            # Select port for this trial
            if number_of_trials != 0 and trial_order is not None:
                try:
                    port = trial_order[trial_count]
                except IndexError:
                    port = random.choice(ports_in_use)
            else:
                port = random.choice(ports_in_use)
            
            # Get catch flag for this trial
            catch = catch_sequence[trial_count]
            
            # Send port and catch info to Arduino
            ser.write(f"{port+1}{catch}".encode())
            log.append(f"OUT;{timer():0.4f}")
            
            # Wait for Arduino's confirmation
            send_time = time.perf_counter()
            while True:
                time.sleep(0.001)
                incoming = ser.read_all().decode("utf-8").strip()
                if len(incoming) > 0:
                    if incoming[0] == 'G':
                        break
                    else:
                        break
                if time.perf_counter() - send_time > 1:
                    print(Fore.RED + "Start signal timeout \a")
                    break
            
            ser.read_all()  # Clear serial buffer
            
            trial_count += 1
            
            # Display cue information
            cue = str(port + 1)
            print(Fore.CYAN + f"Cue given: {cue}, catch: {'CATCH' if catch == 1 else 'NORMAL'}")
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
                
                # Wait for trial outcome
                while True:
                    time.sleep(0.001)
                    weight(rd, timer, scales_data)  # Continue updating scales data
                    
                    incoming = ser.readline().decode("utf-8").strip()
                    if len(incoming) > 1:
                        if incoming[0] == "C":
                            time.sleep(0.1)
                            ser.read_all()
                            if incoming[1] == str(port + 1):
                                print(Fore.GREEN + "Reward taken")
                                print(Fore.CYAN + f"Trials: {trial_count}")
                                successes += 1
                                print(Fore.CYAN + f"Successes: {successes}")
                                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")
                                
                                if trial_count >= number_of_trials and number_of_trials != 0:
                                    m_break = True
                                    
                                print(TRIAL_PRINT_DELIMITER)
                                break
                            
                            if incoming[1] != str(port + 1):
                                if incoming[1] == "F":
                                    print(Fore.RED + "Trial timeout")
                                    log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                    
                                    if trial_count >= number_of_trials and number_of_trials != 0:
                                        m_break = True
                                        
                                    print(TRIAL_PRINT_DELIMITER)
                                    break
                                else:
                                    print(Fore.RED + f"Port {incoming[1]} touched, reward not given")
                                    log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                    
                                    if trial_count >= number_of_trials and number_of_trials != 0:
                                        m_break = True
                                        
                                    print(TRIAL_PRINT_DELIMITER)
                                    break
                    
                    if time.perf_counter() - receive_time > TRIAL_TIMEOUT:
                        print(Fore.RED + '\a' + f"Serial error, timeout: {incoming}")
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