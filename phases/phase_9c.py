"""
Phase 9c implementation: Full Task with waiting period.
"""

import time
import random
import keyboard
from colorama import Fore

from common.arduino import setup_arduino_case, wait_for_start_signal, check_port_was_received
from common.scales import weight, pressure_plate

# Phase-specific constants
PHASE_NUMBER = "9c"
ARDUINO_CASE = 6
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
    
    # Audio cue setting
    phase_params["audio_cue"] = input("Audio cue? (y/n): ").strip().lower()
    phase_params["wait_duration"] = input("Enter wait duration (ms): ").strip()
    phase_params["cue_duration"] = input("Enter cue duration (ms) (0 = unlimited) (1 = mixed): ").strip()
    
    if phase_params["audio_cue"] == "n":
        try:
            phase_params["num_ports"] = int(input("Enter number of ports (1-6): ").strip())
        except ValueError:
            print(Fore.RED + "Invalid number of ports, must be a number.")
            phase_params["num_ports"] = int(input("Enter number of ports (1-6): ").strip())
        
        if phase_params["num_ports"] == 6:
            phase_params["ports_in_use"] = [0, 1, 2, 3, 4, 5]
        elif phase_params["num_ports"] < 6:
            phase_params["ports_in_use"] = []
            for i in range(phase_params["num_ports"]):
                port = int(input(f"Enter port {i+1}/{phase_params['num_ports']}: ").strip())
                phase_params["ports_in_use"].append(port - 1)
    
    if phase_params["audio_cue"] == "y":
        phase_params["proportion_audio"] = int(input("Proportion of audio trials (6 = 50:50 audio:visual, 0 = all audio): ").strip())
    
    return phase_params

def setup_trial_order(audio, number_of_trials, proportion_audio=6, ports_in_use=None):
    """
    Setup the trial order based on parameters.
    
    Args:
        audio (str): 'y' or 'n' for audio cue
        number_of_trials (int): Number of trials or 0 for unlimited
        proportion_audio (int): Proportion of audio trials
        ports_in_use (list): List of port indices to use
        
    Returns:
        tuple: (trial_order, ports_in_use)
    """
    if ports_in_use is None:
        ports_in_use = [0, 1, 2, 3, 4, 5]
        
    if audio == "n":
        number_of_ports = len(ports_in_use)
        
        if number_of_trials != 0:
            trial_order = []
            for i in range(number_of_trials):
                trial_order.append(i % number_of_ports)
            random.shuffle(trial_order)
            return trial_order, ports_in_use
    
    if audio == "y":
        if number_of_trials != 0:
            if proportion_audio == 0:
                trial_order = [6] * number_of_trials
                return trial_order, [6]
            else:
                total_audio_trials = number_of_trials * proportion_audio // (proportion_audio + 6)
                total_visual_trials = number_of_trials - total_audio_trials
                trial_order = [6] * total_audio_trials + [(i % 5) + 1 for i in range(total_visual_trials)]
                random.shuffle(trial_order)
                return trial_order, ports_in_use
        else:
            if proportion_audio == 0:
                return None, [6]
            else:
                ports = [1, 2, 3, 4, 5]
                for i in range(proportion_audio):
                    ports.append(6)
                return None, ports
    
    return None, ports_in_use

def run_phase(ser, session_params, metadata, rd, timer, log, scales_data):
    """
    Run Phase 9c experiment.
    
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
    audio = session_params.get("audio_cue", "n")
    wait_duration = session_params.get("wait_duration", "1000")
    cue_duration = session_params.get("cue_duration", "0")
    mouse_weight = session_params.get("mouse_weight", 20)
    mouse_weight_offset = 2
    number_of_trials = session_params.get("number_of_trials", 0)
    proportion_audio = session_params.get("proportion_audio", 6)
    ports_in_use = session_params.get("ports_in_use", [0, 1, 2, 3, 4, 5])
    
    # Setup
    print(Fore.CYAN + "Full Task with waiting period: In phase 9, reward is given at 6 ports randomly, set below. Incorrect touches are penalised.")
    print(Fore.YELLOW + f"Use setting {ARDUINO_CASE} on arduino")
    
    # Setup trial order
    trial_order, ports_in_use = setup_trial_order(
        audio, 
        number_of_trials, 
        proportion_audio, 
        ports_in_use
    )
    
    # Setup Arduino
    setup_arduino_case(ser, ARDUINO_CASE)
    
    # Wait for start signal
    if not wait_for_start_signal(ser):
        return 0
    
    # Send cue duration to Arduino
    ser.write(f"{cue_duration}".encode())
    
    # Listen for confirmation
    start = time.perf_counter()
    while True:
        time.sleep(0.001)
        incoming = ser.readline().decode("utf-8").strip()
        if len(incoming) > 0:
            break
        if time.perf_counter() - start > 1:
            print(Fore.RED + "Start signal timeout")
            break
    
    ser.read_all()  # Clear serial buffer
    
    # Update metadata
    metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
    metadata["Platform pause time"] = 1  # Default pause time
    metadata["Cue duration"] = cue_duration
    metadata["Wait duration"] = wait_duration
    metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]
    
    if audio == "n":
        metadata["Port"] = [(port + 1) for port in ports_in_use]
    
    # Main experiment loop
    m_break = False
    trial_count = 0
    successes = 0
    pause_time = 1
    
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
            state = False
            wait_complete = False
            
            # Select port
            if number_of_trials != 0 and trial_order is not None:
                try:
                    port = trial_order[trial_count]
                except IndexError:
                    port = random.choice(ports_in_use)
            else:
                port = random.choice(ports_in_use)
            
            # Send port to Arduino
            ser.write(f"{port+1}".encode())
            log.append(f"OUT;{timer():0.4f}")
            trial_count += 1
            
            if port == 6:
                cue = "audio"
                port = 0
            else:
                cue = str(port + 1)
            
            print(Fore.CYAN + f"Cue given: {cue}")
            receive_time = time.perf_counter()
            
            # Check if port was received
            incoming, error = check_port_was_received(ser, receive_time)
            try:
                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
            except IndexError:
                pass
            
            if not error:
                if incoming[0] == "R":
                    ser.read_all()
                
                wait_time = int(wait_duration) / 1000
                
                # Wait for the mouse on the platform
                while not wait_complete:
                    weight(rd, timer, scales_data)
                    if timer() - activation_time > wait_time + 1:
                        print(Fore.RED + "wait time timeout")
                        break
                    
                    if weight(rd, timer, scales_data) > mouse_weight - mouse_weight_offset and timer() - activation_time > wait_time and timer() - activation_time < wait_time + 1:
                        if not wait_complete:
                            ser.write("s".encode())
                            wait_complete = True
                            log.append(f"OUT;{timer():0.4f}")
                        
                        time.sleep(0.01)
                        ser.read_all()
                        
                        # Wait for trial outcome
                        while True:
                            time.sleep(0.001)
                            weight(rd, timer, scales_data)
                            incoming = ser.readline().decode("utf-8").strip()
                            
                            if len(incoming) > 1:
                                if incoming[0] == "C":
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
        
        if keyboard.is_pressed(EXIT_KEY):
            m_break = True
        
        if m_break:
            break
    
    return trial_count