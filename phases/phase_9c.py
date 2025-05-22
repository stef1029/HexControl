"""
Phase 9c implementation: Full Task with waiting period and success statistics tracking.
"""

import time
import random
import keyboard
from colorama import Fore
from datetime import datetime

from common.arduino import setup_arduino_case, wait_for_start_signal, check_port_was_received
from common.scales import weight, pressure_plate

# Phase-specific constants
PHASE_NUMBER = "9c"
ARDUINO_CASE = 6
EXIT_KEY = 'esc'
TRIAL_TIMEOUT = 11
TRIAL_PRINT_DELIMITER = "----------------------------------------"
MOVING_WINDOW_SIZE = 20  # Last 20 trials for moving success rate

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
    
    # Port selection
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
                # All audio trials
                trial_order = [6] * number_of_trials
                return trial_order, [6]
            else:
                # Mix of audio and visual trials
                total_audio_trials = number_of_trials * proportion_audio // (proportion_audio + 6)
                total_visual_trials = number_of_trials - total_audio_trials
                
                # Create trial order with audio (6) and visual trials from selected ports
                audio_trials = [6] * total_audio_trials
                
                # For visual trials, use the ports specified in ports_in_use
                visual_trials = []
                for i in range(total_visual_trials):
                    port_index = i % len(ports_in_use)
                    visual_trials.append(ports_in_use[port_index])
                
                trial_order = audio_trials + visual_trials
                random.shuffle(trial_order)
                
                # Return the trial order and the complete set of ports including audio marker
                all_ports = ports_in_use.copy()
                if 6 not in all_ports:
                    all_ports.append(6)  # Add audio marker
                
                return trial_order, all_ports
        else:
            if proportion_audio == 0:
                return None, [6]
            else:
                # For unlimited trials, prepare a list of ports to choose from
                # with the right proportion of audio vs visual
                weighted_ports = []
                
                # Add visual ports from the specified ports
                for port in ports_in_use:
                    weighted_ports.append(port)
                
                # Add audio marker (6) with the correct proportion
                for i in range(proportion_audio):
                    weighted_ports.append(6)
                
                # Return the list of weighted ports for random selection
                return None, weighted_ports
    
    return None, ports_in_use

def print_success_stats(success_data, cue_type=None):
    """
    Print success statistics based on the current data.
    
    Args:
        success_data (dict): Dictionary containing success statistics
        cue_type (str, optional): Current trial cue type ('audio' or None for visual)
    """
    # Calculate overall success rates
    success_rate = (success_data["successes"] / success_data["total_attempts"]) * 100 if success_data["total_attempts"] > 0 else 0
    print(Fore.CYAN + f"Success Rate: {success_rate:.1f}% ({success_data['successes']}/{success_data['total_attempts']})")
    
    # Calculate recent overall success rate
    recent_trials = success_data["all_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["all_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["all_trial_results"]
    if recent_trials:
        recent_success_rate = (sum(recent_trials) / len(recent_trials)) * 100
        print(Fore.CYAN + f"Recent Overall Success Rate (last {len(recent_trials)} trials): {recent_success_rate:.1f}%")
    
    # Print stats based on trial type
    if cue_type == "audio":
        audio_success_rate = (success_data["audio_successes"] / success_data["audio_attempts"]) * 100 if success_data["audio_attempts"] > 0 else 0
        print(Fore.CYAN + f"Audio Success Rate: {audio_success_rate:.1f}% ({success_data['audio_successes']}/{success_data['audio_attempts']})")
        
        recent_audio_trials = success_data["audio_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["audio_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["audio_trial_results"]
        if recent_audio_trials:
            recent_audio_success_rate = (sum(recent_audio_trials) / len(recent_audio_trials)) * 100
            print(Fore.CYAN + f"Recent Audio Success Rate (last {len(recent_audio_trials)} trials): {recent_audio_success_rate:.1f}%")
    else:
        visual_success_rate = (success_data["visual_successes"] / success_data["visual_attempts"]) * 100 if success_data["visual_attempts"] > 0 else 0
        print(Fore.CYAN + f"Visual Success Rate: {visual_success_rate:.1f}% ({success_data['visual_successes']}/{success_data['visual_attempts']})")
        
        recent_visual_trials = success_data["visual_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["visual_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["visual_trial_results"]
        if recent_visual_trials:
            recent_visual_success_rate = (sum(recent_visual_trials) / len(recent_visual_trials)) * 100
            print(Fore.CYAN + f"Recent Visual Success Rate (last {len(recent_visual_trials)} trials): {recent_visual_success_rate:.1f}%")

def print_final_stats(success_data, audio_cue):
    """
    Print final success statistics at the end of the experiment.
    
    Args:
        success_data (dict): Dictionary containing success statistics
        audio_cue (str): 'y' or 'n' for audio cue
    """
    # Overall statistics
    final_success_rate = (success_data["successes"] / success_data["total_attempts"]) * 100 if success_data["total_attempts"] > 0 else 0
    print(Fore.GREEN + f"\nFinal Results:")
    print(Fore.CYAN + f"Total Trials: {success_data['trial_count']}")
    print(Fore.CYAN + f"Total Attempts: {success_data['total_attempts']}")
    print(Fore.CYAN + f"Total Successes: {success_data['successes']}")
    print(Fore.CYAN + f"Final Success Rate: {final_success_rate:.1f}% ({success_data['successes']}/{success_data['total_attempts']})")
    
    # Recent success rate
    recent_trials = success_data["all_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["all_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["all_trial_results"]
    if recent_trials:
        recent_success_rate = (sum(recent_trials) / len(recent_trials)) * 100
        print(Fore.CYAN + f"Recent Success Rate (last {len(recent_trials)} trials): {recent_success_rate:.1f}%")
    
    # Audio/visual breakdown
    if audio_cue == "y":
        final_audio_success_rate = (success_data["audio_successes"] / success_data["audio_attempts"]) * 100 if success_data["audio_attempts"] > 0 else 0
        final_visual_success_rate = (success_data["visual_successes"] / success_data["visual_attempts"]) * 100 if success_data["visual_attempts"] > 0 else 0
        
        print(Fore.GREEN + f"\nBreakdown by Trial Type:")
        print(Fore.CYAN + f"Audio Trials: {success_data['audio_attempts']}")
        print(Fore.CYAN + f"Audio Successes: {success_data['audio_successes']}")
        print(Fore.CYAN + f"Audio Success Rate: {final_audio_success_rate:.1f}% ({success_data['audio_successes']}/{success_data['audio_attempts']})")
        
        # Recent audio success rate
        recent_audio_trials = success_data["audio_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["audio_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["audio_trial_results"]
        if recent_audio_trials:
            recent_audio_success_rate = (sum(recent_audio_trials) / len(recent_audio_trials)) * 100
            print(Fore.CYAN + f"Recent Audio Success Rate (last {len(recent_audio_trials)} trials): {recent_audio_success_rate:.1f}%")
        
        if success_data["visual_attempts"] > 0:
            print(Fore.CYAN + f"Visual Trials: {success_data['visual_attempts']}")
            print(Fore.CYAN + f"Visual Successes: {success_data['visual_successes']}")
            print(Fore.CYAN + f"Visual Success Rate: {final_visual_success_rate:.1f}% ({success_data['visual_successes']}/{success_data['visual_attempts']})")
            
            # Recent visual success rate
            recent_visual_trials = success_data["visual_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["visual_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["visual_trial_results"]
            if recent_visual_trials:
                recent_visual_success_rate = (sum(recent_visual_trials) / len(recent_visual_trials)) * 100
                print(Fore.CYAN + f"Recent Visual Success Rate (last {len(recent_visual_trials)} trials): {recent_visual_success_rate:.1f}%")
        
        # Performance comparison
        if success_data["audio_attempts"] > 0 and success_data["visual_attempts"] > 0:
            if final_audio_success_rate > final_visual_success_rate:
                performance_diff = final_audio_success_rate - final_visual_success_rate
                print(Fore.YELLOW + f"Performance Analysis: Audio trials had {performance_diff:.1f}% higher success rate")
            elif final_visual_success_rate > final_audio_success_rate:
                performance_diff = final_visual_success_rate - final_audio_success_rate
                print(Fore.YELLOW + f"Performance Analysis: Visual trials had {performance_diff:.1f}% higher success rate")
            else:
                print(Fore.YELLOW + f"Performance Analysis: Audio and visual trials had equal success rates")
            
            # Compare recent performance
            if recent_audio_trials and recent_visual_trials:
                if recent_audio_success_rate > recent_visual_success_rate:
                    recent_diff = recent_audio_success_rate - recent_visual_success_rate
                    print(Fore.YELLOW + f"Recent Performance: Audio trials performed {recent_diff:.1f}% better in the last {MOVING_WINDOW_SIZE} trials")
                elif recent_visual_success_rate > recent_audio_success_rate:
                    recent_diff = recent_visual_success_rate - recent_audio_success_rate
                    print(Fore.YELLOW + f"Recent Performance: Visual trials performed {recent_diff:.1f}% better in the last {MOVING_WINDOW_SIZE} trials")
                else:
                    print(Fore.YELLOW + f"Recent Performance: Audio and visual trials had equal success rates in the last {MOVING_WINDOW_SIZE} trials")

def update_success_data(success_data, is_success, port, cue_type):
    """
    Update success statistics based on trial outcome.
    
    Args:
        success_data (dict): Dictionary containing success statistics
        is_success (bool): Whether the trial was successful
        port (int): The port number
        cue_type (str): 'audio' or port number string for visual
        
    Returns:
        dict: Updated success_data
    """
    # Increment total attempts
    success_data["total_attempts"] += 1
    
    # Update success count if trial was successful
    if is_success:
        success_data["successes"] += 1
    
    # Calculate success rate
    success_data["success_rate"] = (success_data["successes"] / success_data["total_attempts"]) * 100
    
    # Add trial result to overall results list (1 for success, 0 for failure)
    success_data["all_trial_results"].append(1 if is_success else 0)
    
    # Update trial type specific data
    if cue_type == "audio":
        success_data["audio_attempts"] += 1
        if is_success:
            success_data["audio_successes"] += 1
        success_data["audio_success_rate"] = (success_data["audio_successes"] / success_data["audio_attempts"]) * 100
        success_data["audio_trial_results"].append(1 if is_success else 0)
    else:
        success_data["visual_attempts"] += 1
        if is_success:
            success_data["visual_successes"] += 1
        success_data["visual_success_rate"] = (success_data["visual_successes"] / success_data["visual_attempts"]) * 100
        success_data["visual_trial_results"].append(1 if is_success else 0)
    
    return success_data

def update_metadata_with_stats(metadata, success_data, audio_cue):
    """
    Update metadata with success statistics.
    
    Args:
        metadata (dict): Metadata dictionary to update
        success_data (dict): Dictionary containing success statistics
        audio_cue (str): 'y' or 'n' for audio cue
        
    Returns:
        dict: Updated metadata
    """
    # Overall statistics
    final_success_rate = (success_data["successes"] / success_data["total_attempts"]) * 100 if success_data["total_attempts"] > 0 else 0
    metadata["Total Trials"] = success_data["trial_count"]
    metadata["Total Attempts"] = success_data["total_attempts"]
    metadata["Total Successes"] = success_data["successes"]
    metadata["Success Rate"] = f"{final_success_rate:.1f}%"
    metadata["Moving Window Size"] = MOVING_WINDOW_SIZE
    
    # Recent success rate
    recent_trials = success_data["all_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["all_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["all_trial_results"]
    if recent_trials:
        recent_success_rate = (sum(recent_trials) / len(recent_trials)) * 100
        metadata["Recent Success Rate"] = f"{recent_success_rate:.1f}%"
    
    # Audio/visual breakdown
    if audio_cue == "y":
        final_audio_success_rate = (success_data["audio_successes"] / success_data["audio_attempts"]) * 100 if success_data["audio_attempts"] > 0 else 0
        metadata["Audio Trials"] = success_data["audio_attempts"]
        metadata["Audio Successes"] = success_data["audio_successes"]
        metadata["Audio Success Rate"] = f"{final_audio_success_rate:.1f}%"
        
        recent_audio_trials = success_data["audio_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["audio_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["audio_trial_results"]
        if recent_audio_trials:
            recent_audio_success_rate = (sum(recent_audio_trials) / len(recent_audio_trials)) * 100
            metadata["Recent Audio Success Rate"] = f"{recent_audio_success_rate:.1f}%"
        
        if success_data["visual_attempts"] > 0:
            final_visual_success_rate = (success_data["visual_successes"] / success_data["visual_attempts"]) * 100
            metadata["Visual Trials"] = success_data["visual_attempts"]
            metadata["Visual Successes"] = success_data["visual_successes"]
            metadata["Visual Success Rate"] = f"{final_visual_success_rate:.1f}%"
            
            recent_visual_trials = success_data["visual_trial_results"][-MOVING_WINDOW_SIZE:] if len(success_data["visual_trial_results"]) >= MOVING_WINDOW_SIZE else success_data["visual_trial_results"]
            if recent_visual_trials:
                recent_visual_success_rate = (sum(recent_visual_trials) / len(recent_visual_trials)) * 100
                metadata["Recent Visual Success Rate"] = f"{recent_visual_success_rate:.1f}%"
    
    return metadata

def run_phase(ser, session_params, metadata, rd, timer, log, scales_data):
    """
    Run Phase 9c experiment with success statistics tracking.
    
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
    print(Fore.CYAN + "Full Task with waiting period: In phase 9, reward is given at selected ports randomly. Incorrect touches are penalised.")
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
    
    # Add ports in use to metadata
    ports_display = [(port + 1) for port in ports_in_use if port != 6]  # Exclude audio marker from display
    metadata["Ports in use"] = ports_display
    
    # Initialize success tracking data
    success_data = {
        "trial_count": 0,
        "total_attempts": 0,
        "successes": 0,
        "success_rate": 0.0,
        "audio_attempts": 0,
        "audio_successes": 0,
        "audio_success_rate": 0.0,
        "visual_attempts": 0,
        "visual_successes": 0,
        "visual_success_rate": 0.0,
        "all_trial_results": [],
        "audio_trial_results": [],
        "visual_trial_results": []
    }
    
    # Main experiment loop
    m_break = False
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
                    port = trial_order[success_data["trial_count"]]
                except IndexError:
                    port = random.choice(ports_in_use)
            else:
                port = random.choice(ports_in_use)
            
            # Send port to Arduino (adding 1 to non-audio ports, audio is already 6)

            ser.write(f"{port+1}".encode())  # Add 1 to convert from 0-index to 1-index
                
            log.append(f"OUT;{timer():0.4f}")
            success_data["trial_count"] += 1
            
            # Determine if this is an audio or visual trial
            if port == 6:
                cue = "audio"
                actual_port = 0  # For tracking purposes
            else:
                cue = str(port + 1)
                actual_port = port
            
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
                        
                        # Handle timeout as a failure for stats
                        success_data = update_success_data(success_data, False, actual_port, cue)
                        print_success_stats(success_data, cue)
                        print(TRIAL_PRINT_DELIMITER)
                        break
                    
                    if weight(rd, timer, scales_data) > mouse_weight - mouse_weight_offset and timer() - activation_time > wait_time and timer() - activation_time < wait_time + 1:
                        if not wait_complete:
                            ser.write("s".encode())
                            wait_complete = True
                            print(Fore.CYAN + "Wait time complete")
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
                                    # For audio trials (port 6), success is when port 1 is touched
                                    # For visual trials, success is when the selected port is touched
                                    expected_port = "1" if port == 6 else str(port + 1)
                                    if incoming[1] == expected_port:
                                        # Successful trial
                                        success_data = update_success_data(success_data, True, actual_port, cue)
                                        
                                        print(Fore.GREEN + "Reward taken")
                                        print(Fore.CYAN + f"Trials: {success_data['trial_count']}")
                                        print(Fore.CYAN + f"Successes: {success_data['successes']}")
                                        print_success_stats(success_data, cue)
                                        
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")
                                        
                                        if success_data['trial_count'] >= number_of_trials and number_of_trials != 0:
                                            m_break = True
                                            
                                        print(TRIAL_PRINT_DELIMITER)
                                        break
                                    
                                    if incoming[1] != expected_port:
                                        # Failed trial
                                        success_data = update_success_data(success_data, False, actual_port, cue)
                                        
                                        if incoming[1] == "F":
                                            print(Fore.RED + "Trial timeout")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                        else:
                                            print(Fore.RED + f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                        
                                        print_success_stats(success_data, cue)
                                        
                                        if success_data['trial_count'] >= number_of_trials and number_of_trials != 0:
                                            m_break = True
                                            
                                        print(TRIAL_PRINT_DELIMITER)
                                        break
                            
                            if time.perf_counter() - receive_time > TRIAL_TIMEOUT:
                                print(Fore.RED + '\a' + f"Serial error, timeout: {incoming}")
                                
                                # Count timeout as a failure for stats
                                success_data = update_success_data(success_data, False, port, cue)
                                print_success_stats(success_data, cue)
                                
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
    
    # Print final statistics if any trials were completed
    if success_data["total_attempts"] > 0:
        print_final_stats(success_data, audio)
        metadata = update_metadata_with_stats(metadata, success_data, audio)
    
    return success_data["trial_count"]