import keyboard
import time
import serial
from datetime import datetime
import random
from Scripts.read import Scales
import csv
import os
import json
import subprocess
from pathlib import Path
import argparse
import traceback
from colorama import init, Fore, Style

global rd
rd = 0

exit_key = 'esc'

LEDs = ["q", "w", "e", "r", "t", "y"]
reward_port = ["1", "2", "3", "4", "5", "6"] 
speaker = ["a", "s", "d", "f", "g", "h"]
error = ["z", "x", "c", "v", "b", "n"]

log = []
metadata = {}
scales_data = []  

# First, let's define common utility functions for phase setup and execution

trial_timeout = 11

most_recent_scales_value = 0
def weight(test = False):
    global most_recent_scales_value
    global scales_data
    # Returns weight from scales. If no new data, returns most recent value.
    # Also adds scales data to scales_data list.
    raw = rd.get_mass()
    if 'ID' in raw:
        id = raw['ID']
        data = raw['value']
        if data != None:
            most_recent_scales_value = data
            if test == False:
                scales_data.append([timer(), data, id])
            return data
        else:
            return most_recent_scales_value
    elif 'value' in raw:
        data = raw['value']
        if data != None:
            most_recent_scales_value = data
            if test == False:
                scales_data.append([timer(), data])
            return data
        else:
            return most_recent_scales_value

def pressure_plate(mouse_weight, wait_time): # grams, seconds
    # Returns True if mouse_weight consistently above threshold for wait_time seconds.
    # Checks enters a loop and breaks immediately if weight is below threshold. 
    # If weight is above threshold, enters another loop which returns True if weight above threshold for wait_time seconds.
    # Breaks loops if weight goes below threshold too quickly.
    scales_tic = time.perf_counter()
    def scales_timer():
        scales_toc = time.perf_counter()
        return scales_toc - scales_tic
    
    while True:
        reading = weight()
        if reading > mouse_weight:
            while True:
                if weight() < mouse_weight:
                    return (False, timer())
                    
                if scales_timer() > wait_time: 
                    # print("thresh")
                    return (True, timer())

        break
    return (False, timer())

UP = "\033[1A"; CLEAR = '\x1b[2K'
def test_scales():
    # Checks if scales are working by printing weight to console.
    print("Scales test. Press Q to exit")
    while True:
        reading = weight(test = True)
        print(UP, end = CLEAR)          # DAN:  If scales values not showing, move this line below the print(reading) line.
        print(reading)
        
        if keyboard.is_pressed('q'):
            print(UP, end = CLEAR)
            break

global tic
tic = 0
def timer():
    global tic
    toc = time.perf_counter()       
    return toc - tic

def check_port_was_received(ser, receive_time):
    while True:
        time.sleep(0.001)
        error = False
        incoming = ser.readline().decode("utf-8").strip()  
        if len(incoming) > 1:
            if incoming[0] == "R":
                ser.read_all()
                break
        if time.perf_counter() - receive_time > trial_timeout:
            print(f"Serial error, timeout 1: {incoming} \a")
            ser.read_all()                      # Clear serial buffer
            error = True
            break      
    return incoming, error

def get_rig_port(rig):
    rig_ports = {
        None: "COM4",
        1: "COM4",
        2: "COM11",
        3: "COM21",
        4: "COM6"
    }
    
    if rig not in rig_ports:
        raise ValueError("Invalid rig number.")
    
    return rig_ports[rig]

def setup_serial_connection(port):
    """Setup and return a serial connection to the Arduino"""
    tries = 0
    max_tries = 2
    
    while tries < max_tries:
        try:
            ser = serial.Serial(port, 9600, timeout=0)
            time.sleep(2)  # wait for arduino to boot up
            ser.read_all()  # Clear serial buffer
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            return ser
        except serial.SerialException:
            print(f"Serial connection not found on {port}, trying again...")
            tries += 1
            if tries >= max_tries:
                raise

def setup_arduino_case(ser, case_number):
    """Send case selection command to Arduino and wait for acknowledgment"""
    print(Fore.CYAN + f"Sending case selection to arduino: {case_number}")
    ser.read_all()  # Clear serial buffer
    ser.write(f"CASE:{case_number}\n".encode())
    
    # Wait for acknowledgment
    ack_timeout = time.perf_counter() + 5  # 5 second timeout
    while time.perf_counter() < ack_timeout:
        response = ser.readline().decode("utf-8").strip()
        if response == f"CASE_ACK:{case_number}":
            print(Fore.GREEN + "Arduino acknowledged case selection")
            return True
        time.sleep(0.1)
    
    print(Fore.RED + "Warning: No acknowledgment received from Arduino")
    return False

def wait_for_start_signal(ser):
    """Wait for start signal from Arduino"""
    print(Fore.CYAN + "Waiting for start signal from arduino.")
    ser.read_all()  # Clear serial buffer
    start_timeout = time.perf_counter() + 10  # 10 second timeout
    while time.perf_counter() < start_timeout:
        incoming = ser.read().decode()
        if incoming == "S":
            print(Fore.GREEN + f"Start signal received {datetime.now().strftime('%H%M%S')}")
            ser.read_all()  # Clear serial buffer
            return True
        time.sleep(0.1)
    
    print(Fore.RED + "Error: No start signal received from Arduino")
    return False

def process_port_selection(phase_params):
    """Process port selection based on phase parameters"""
    if "port" in phase_params:
        # Port already specified in params
        return phase_params["port"]
    else:
        # Ask user for port
        port = int(input("Enter port number (1-6): ")) - 1
        return port

def handle_user_input_for_phase(phase, params):
    """Collect phase-specific user inputs"""
    phase_params = {}
    
    if phase == "2":
        # Phase 2 specific parameters
        if "port" not in params:
            port = int(input("Enter port number (1-6): ")) - 1
            phase_params["port"] = port
        else:
            phase_params["port"] = params["port"]
    
    elif phase == "9c":
        # Full Task with waiting period
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
    
    # ...add other phases here
    
    return phase_params

def run_phase_2(ser, session_params):
    """Run Phase 2 experiment"""
    # Extract parameters
    port = session_params.get("port", 0)
    mouse_weight = session_params.get("mouse_weight", 20)
    mouse_weight_offset = 2
    number_of_trials = session_params.get("number_of_trials", 0)
    
    # Setup
    print("Phase 2: Reward given for over-threshold scales readings.")
    print("In phase 2, reward is only given at one port.")
    print("Use setting 2 on arduino")
    
    # Setup Arduino
    setup_arduino_case(ser, 2)
    
    # Wait for start signal
    if not wait_for_start_signal(ser):
        return False
    
    # Start timer
    global tic
    tic = time.perf_counter()
    
    # Setup metadata
    metadata["Port"] = port + 1
    metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
    metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]
    
    # Main experiment loop
    m_break = False
    trial_count = 0
    trial_print_delimiter = "----------------------------------------"
    
    rd.clear_buffer()
    while True:
        state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, 0.2)
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
                    weight()  # Call pressure_plate to continue updating scales_data list
                    incoming = ser.readline().decode("utf-8").strip()  # Read arduino port number
                    
                    if len(incoming) > 1 and incoming[0] == "C":
                        ser.read_all()
                        if incoming[1] == str(port+1):
                            print("Reward taken")
                            print(f"Trials: {trial_count}")
                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")  # Add time to log
                            
                            if trial_count >= number_of_trials and number_of_trials != 0:
                                m_break = True
                                
                            print(trial_print_delimiter)
                            break
                            
                        if incoming[1] != str(port+1):
                            if incoming[1] == "F":
                                print("Trial timeout")
                                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                
                                if trial_count >= number_of_trials and number_of_trials != 0:
                                    m_break = True
                                    
                                print(trial_print_delimiter)
                                break
                            else:
                                print(f"Port {incoming[1]} touched")
                                log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                
                    if time.perf_counter() - receive_time > trial_timeout:
                        print(f"Serial error, timeout: {incoming}")
                        ser.read_all()  # Clear serial buffer
                        print(trial_print_delimiter)
                        break
                        
                    if keyboard.is_pressed(exit_key):  # If exit key is pressed, end program
                        m_break = True
                        
                    if m_break:
                        break
                        
        if keyboard.is_pressed(exit_key):  # If exit key is pressed, end program
            m_break = True
            
        if m_break:
            break
            
    return trial_count

def run_phase_9c(ser, session_params):
    """Run Phase 9c experiment"""
    # Extract parameters
    audio = session_params.get("audio_cue", "n")
    wait_duration = session_params.get("wait_duration", "1000")
    cue_duration = session_params.get("cue_duration", "0")
    mouse_weight = session_params.get("mouse_weight", 20)
    mouse_weight_offset = 2
    number_of_trials = session_params.get("number_of_trials", 0)
    
    # Setup
    print(Fore.CYAN + "Full Task with waiting period: In phase 9, reward is given at 6 ports randomly, set below. Incorrect touches are penalised.")
    print(Fore.YELLOW + "Use setting 6 on arduino")
    
    # Setup ports based on parameters
    if audio == "n":
        num_ports = session_params.get("num_ports", 6)
        ports_in_use = session_params.get("ports_in_use", [0, 1, 2, 3, 4, 5])
        number_of_ports = len(ports_in_use)
        
        if number_of_trials != 0:
            trial_order = []
            for i in range(number_of_trials):
                trial_order.append(i % number_of_ports)
            random.shuffle(trial_order)
    
    if audio == "y":
        proportion_audio = session_params.get("proportion_audio", 6)
        
        if number_of_trials != 0:
            if proportion_audio == 0:
                trial_order = [6] * number_of_trials
            else:
                total_audio_trials = number_of_trials * proportion_audio // (proportion_audio + 6)
                total_visual_trials = number_of_trials - total_audio_trials
                trial_order = [6] * total_audio_trials + [(i % 5) + 1 for i in range(total_visual_trials)]
                random.shuffle(trial_order)
        else:
            if proportion_audio == 0:
                ports_in_use = [6]
            else:
                ports_in_use = [1, 2, 3, 4, 5]
                for i in range(proportion_audio):
                    ports_in_use.append(6)
    
    # Setup Arduino
    setup_arduino_case(ser, 6)
    
    # Wait for start signal
    if not wait_for_start_signal(ser):
        return False
    
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
    
    # Start timer
    global tic
    tic = time.perf_counter()
    
    # Setup metadata
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
    trial_print_delimiter = "----------------------------------------"
    
    rd.clear_buffer()
    pause_time = 1
    
    while True:
        state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)
        if state:
            state = False
            wait_complete = False
            
            # Select port
            if number_of_trials != 0:
                try:
                    port = trial_order[trial_count]
                except IndexError:
                    port = random.choice(ports_in_use)
            else:
                port = random.choice(ports_in_use)
            
            # Send port to Arduino
            ser.write(f"{port+1}".encode())
            log.append(Fore.MAGENTA + f"OUT;{timer():0.4f}")
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
                log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
            except IndexError:
                pass
            
            if not error:
                if incoming[0] == "R":
                    ser.read_all()
                
                wait_time = int(wait_duration) / 1000
                
                # Wait for the mouse on the platform
                while not wait_complete:
                    weight()
                    if timer() - activation_time > wait_time + 1:
                        print(Fore.RED + "wait time timeout")
                        break
                    
                    if weight() > mouse_weight - mouse_weight_offset and timer() - activation_time > wait_time and timer() - activation_time < wait_time + 1:
                        if not wait_complete:
                            ser.write("s".encode())
                            wait_complete = True
                            log.append(Fore.MAGENTA + f"OUT;{timer():0.4f}")
                        
                        time.sleep(0.01)
                        ser.read_all()
                        
                        # Wait for trial outcome
                        while True:
                            time.sleep(0.001)
                            weight()
                            incoming = ser.readline().decode("utf-8").strip()
                            
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all()
                                    if incoming[1] == str(port + 1):
                                        print(Fore.GREEN + "Reward taken")
                                        print(Fore.CYAN + f"Trials: {trial_count}")
                                        successes += 1
                                        print(Fore.CYAN + f"Successes: {successes}")
                                        log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")
                                        
                                        if trial_count >= number_of_trials and number_of_trials != 0:
                                            m_break = True
                                            
                                        print(trial_print_delimiter)
                                        break
                                    
                                    if incoming[1] != str(port + 1):
                                        if incoming[1] == "F":
                                            print(Fore.RED + "Trial timeout")
                                            log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                            
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                                
                                            print(trial_print_delimiter)
                                            break
                                        else:
                                            print(Fore.RED + f"Port {incoming[1]} touched, reward not given")
                                            log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                            
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                                
                                            print(trial_print_delimiter)
                                            break
                            
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(Fore.RED + '\a' + f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                                
                            if keyboard.is_pressed(exit_key):
                                m_break = True
                            
                            if m_break:
                                break
                    
                    if keyboard.is_pressed(exit_key):
                        m_break = True
                    
                    if m_break:
                        break
        
        if keyboard.is_pressed(exit_key):
            m_break = True
        
        if m_break:
            break
    
    return trial_count

def behaviour(session_params):
    """Main behavior function using the session parameters dictionary"""
    try:
        exit_key = 'esc'
        
        # Extract common parameters
        rig = session_params.get("rig")
        phase = session_params.get("phase", "1")
        mouse_ID = session_params.get("mouse_id", "test")
        mouse_weight = session_params.get("mouse_weight", 20)
        number_of_trials = session_params.get("number_of_trials", 0)
        date_time = session_params.get("date_time", f"{datetime.now():%y%m%d_%H%M%S}")
        fps = session_params.get("fps", 30)
        
        # Setup serial connection
        port = get_rig_port(rig)
        try:
            ser = setup_serial_connection(port)
        except serial.SerialException as e:
            print(f"Could not establish serial connection: {e}")
            return
        
        # Set up folders and metadata
        foldername = f"{date_time}_{mouse_ID}"
        
        if session_params.get("output_path") is None:
            output_path = os.path.join(os.getcwd(), foldername)
            os.makedirs(output_path, exist_ok=True)
        else:
            output_path = session_params.get("output_path")
        
        # Set up common metadata
        global metadata
        metadata = {}
        metadata["Rig"] = rig
        metadata["Mouse ID"] = mouse_ID
        metadata["Date and time"] = date_time
        metadata["Behaviour phase"] = phase
        metadata["FPS"] = fps
        metadata["Number of trials"] = "Not set" if number_of_trials == 0 else number_of_trials
        metadata["Mouse weight"] = mouse_weight
        
        # Process specific phase
        trial_count = 0
        if phase == "2":
            trial_count = run_phase_2(ser, session_params)
        elif phase == "9c":
            trial_count = run_phase_9c(ser, session_params)
        # Add more phases here
        else:
            print(f"Phase {phase} not implemented")
            return
        
    except Exception as e:
        print(e)
        traceback.print_exc()
    
    finally:
        # Save session data
        metadata["Total trials"] = trial_count
        metadata["End time"] = datetime.now().strftime("%y%m%d%H%M%S")
        metadata["Logs"] = log
        metadata["Scales data"] = scales_data
        
        filename = f"{foldername}_Phase_{phase}_behaviour_data.json"
        with open(f"{str(Path(output_path) / filename)}", "w") as f:
            json.dump(metadata, f, indent=4)
        
        try:
            ser.close()
        except:
            pass
        
        print("Program finished")

def get_user_input_for_session(params=None):
    """Collect user inputs to configure the session"""
    # Initialize with default parameters if none provided
    if params is None:
        params = {}
    
    # These are user input parameters that will be saved in configuration files
    user_params = {}
    
    print("Proceed until 'waiting for start signal from arduino.'")
    
    # First, offer to test scales (separate from the parameters dictionary)
    do_scales_test = input("Do scales test? (y/[n]): ").lower() or "n"
    if do_scales_test == "y":
        test_scales()
    
    # Get basic parameters
    user_params["mouse_id"] = params.get("mouse_id") or input("Enter mouse ID: ")
    
    try:
        user_params["mouse_weight"] = params.get("mouse_weight") or float(input("Enter mouse weight (g): "))
    except:
        print("Invalid input. Must be a number. Do not include letters or units.")
        user_params["mouse_weight"] = float(input("Enter mouse weight (g): "))
    
    # Behavior phase
    try:
        user_params["phase"] = params.get("phase") or input("Enter behaviour phase (1-9): ")
    except:
        print("Invalid input. Must be a number (1-9). Do not include letters or units.")
        user_params["phase"] = input("Enter behaviour phase (1-9): ")
    
    # Number of trials
    try:
        user_params["number_of_trials"] = params.get("number_of_trials") or int(input("Enter number of desired trials for session (0 = unlimited): ") or "0")
    except:
        print("Invalid input. Must be a number. Do not include letters or units.")
        user_params["number_of_trials"] = int(input("Enter number of desired trials for session (0 = unlimited): "))
    
    # Get phase-specific parameters
    phase_params = handle_user_input_for_phase(user_params["phase"], params)
    user_params.update(phase_params)
    
    # Option to save configuration
    save_config = input("Save this configuration for future use? (y/[n]): ").lower() or "n"
    if save_config == "y":
        config_name = input("Enter a name for this configuration: ")
        if config_name:
            # Create configs directory if it doesn't exist
            os.makedirs("configs", exist_ok=True)
            # Save only the user input parameters
            with open(f"configs/{config_name}.json", "w") as f:
                json.dump(user_params, f, indent=4)
            print(f"Configuration saved as 'configs/{config_name}.json'")
    
    # Merge user parameters into the main params dictionary
    params.update(user_params)
    return params