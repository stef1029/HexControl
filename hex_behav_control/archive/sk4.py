import keyboard
import time
import serial
from datetime import datetime
import random
import csv
import os
import json
import subprocess
from pathlib import Path
import argparse
import traceback
from colorama import init, Fore, Style

from peripherals.read import Scales

# Initialize colorama
init(autoreset=True)

LEDs = ["q", "w", "e", "r", "t", "y"]
reward_port = ["1", "2", "3", "4", "5", "6"] 
speaker = ["a", "s", "d", "f", "g", "h"]
error = ["z", "x", "c", "v", "b", "n"]

log = []
metadata = {}
scales_data = []        # scales_data stores every reading of the scales by the pressure_plate function and saves it with the corresponding timer() time.

global rd
rd = 0

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
    
    # Regular session - collect all parameters
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
    
    # Add phase-specific parameters based on the selected phase
    if user_params["phase"] == "9c":
        # Full Task with waiting period
        user_params["audio_cue"] = input("Audio cue? (y/n): ").strip().lower()
        user_params["wait_duration"] = input("Enter wait duration (ms): ").strip()
        user_params["cue_duration"] = input("Enter cue duration (ms) (0 = unlimited) (1 = mixed): ").strip()
        
        if user_params["audio_cue"] == "n":
            try:
                user_params["num_ports"] = int(input("Enter number of ports (1-6): ").strip())
            except ValueError:
                print(Fore.RED + "Invalid number of ports, must be a number.")
                user_params["num_ports"] = int(input("Enter number of ports (1-6): ").strip())
            
            if user_params["num_ports"] == 6:
                user_params["ports_in_use"] = [0, 1, 2, 3, 4, 5]
            elif user_params["num_ports"] < 6:
                user_params["ports_in_use"] = []
                for i in range(user_params["num_ports"]):
                    port = int(input(f"Enter port {i+1}/{user_params['num_ports']}: ").strip())
                    user_params["ports_in_use"].append(port - 1)
        
        if user_params["audio_cue"] == "y":
            user_params["proportion_audio"] = int(input("Proportion of audio trials (6 = 50:50 audio:visual, 0 = all audio): ").strip())
    
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

def load_session_config(config_name):
    """Load a saved session configuration"""
    try:
        with open(f"configs/{config_name}.json", "r") as f:
            # Only load user input parameters
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file 'configs/{config_name}.json' not found.")
        return None

def behaviour(session_params):
    """Main behavior function using the session parameters dictionary"""
    try:
        exit_key = 'esc'

        rig = session_params.get("rig")
        port = get_rig_port(rig)
        
        try:
            ser = setup_serial_connection(port)
        except serial.SerialException as e:
            print(f"Could not establish serial connection: {e}")
            return
        
        global tic
        
        # Extract parameters from the dictionary
        mouse_ID = session_params.get("mouse_id", "test")
        mouse_weight = session_params.get("mouse_weight", 20)
        phase = session_params.get("phase", "1")
        number_of_trials = session_params.get("number_of_trials", 0)
        date_time = session_params.get("date_time", f"{datetime.now():%y%m%d_%H%M%S}")
        fps = session_params.get("fps", 30)
        
        # Set up counters and flags
        trial_count = 0
        successes = 0
        reward_count = 0
        m_break = False
        
        # Set up folders and metadata
        foldername = f"{date_time}_{mouse_ID}"
        
        if session_params.get("output_path") is None:
            output_path = os.path.join(os.getcwd(), foldername)
            os.makedirs(output_path, exist_ok=True)
        else:
            output_path = session_params.get("output_path")
        
        # Set up metadata - REMOVED any reference to scales test
        metadata["Rig"] = rig
        metadata["Mouse ID"] = mouse_ID
        metadata["Date and time"] = date_time
        metadata["Behaviour phase"] = phase
        metadata["FPS"] = fps
        metadata["Number of trials"] = "Not set" if number_of_trials == 0 else number_of_trials
        metadata["Mouse weight"] = mouse_weight
        
        mouse_weight_offset = 2
        trial_print_delimiter = "----------------------------------------"
        
        # Process specific behavior phase
        if phase == "9c":
            # Full Task with waiting period
            print(Fore.CYAN + "Full Task with waiting period: In phase 9, reward is given at 6 ports randomly, set below. Incorrect touches are penalised.")
            print(Fore.YELLOW + "Use setting 6 on arduino")
            
            audio = session_params.get("audio_cue", "n")
            wait_duration = session_params.get("wait_duration", "1000")
            cue_duration = session_params.get("cue_duration", "0")
            
            # Setup ports based on parameters
            if audio == "n":
                num_ports = session_params.get("num_ports", 6)
                ports_in_use = session_params.get("ports_in_use", [0, 1, 2, 3, 4, 5])
                metadata["Port"] = [(port + 1) for port in ports_in_use]
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
            
            # Send case selection command to Arduino
            print(Fore.CYAN + "Sending case selection to arduino...")
            ser.read_all()  # Clear serial buffer
            ser.write("CASE:6\n".encode())
            
            # Wait for acknowledgment
            ack_timeout = time.perf_counter() + 5  # 5 second timeout
            while time.perf_counter() < ack_timeout:
                response = ser.readline().decode("utf-8").strip()
                if response == "CASE_ACK:6":
                    print(Fore.GREEN + "Arduino acknowledged case selection")
                    break
                time.sleep(0.1)
            else:
                print(Fore.RED + "Warning: No acknowledgment received from Arduino")
            
            # Wait for start signal
            print(Fore.CYAN + "Waiting for start signal from arduino.")
            ser.read_all()  # Clear serial buffer
            start_timeout = time.perf_counter() + 10  # 10 second timeout
            while time.perf_counter() < start_timeout:
                incoming = ser.read().decode()
                if incoming == "S":
                    break
                time.sleep(0.1)
            else:
                print(Fore.RED + "Error: No start signal received from Arduino")
                raise TimeoutError("Arduino did not send start signal")
            
            # Send Arduino cue_duration
            ser.write(f"{cue_duration}".encode())
            
            # Listen for confirmation
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
            
            # Start timer
            tic = time.perf_counter()
            
            # Setup metadata
            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            pause_time = 1
            metadata["Platform pause time"] = pause_time
            metadata["Cue duration"] = cue_duration
            metadata["Wait duration"] = wait_duration
            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]
            
            # Main behavior loop
            rd.clear_buffer()
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

        # Add additional phase implementations here as needed
        
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

def load_config(config_path):
    with open(config_path, "r") as f:
        return json.load(f)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rig", type=int, help="Rig number")
    parser.add_argument("--path", type=str, help="Folder ID")
    parser.add_argument("--mouse", type=str, help="Mouse ID")
    parser.add_argument("--weight", type=float, help="Mouse weight")
    parser.add_argument("--fps", type=int, help="Frames per second for video recording")
    parser.add_argument("--window_width", type=int, help="Width of the video window")
    parser.add_argument("--window_height", type=int, help="Height of the video window")
    parser.add_argument("--config_json", type=str, help="Path to the configuration JSON file")
    parser.add_argument("--load_config", type=str, help="Name of saved session configuration to load")
    return parser.parse_args()

def start_subprocess(command, name):
    print(f"Starting {name}...")
    return subprocess.Popen(command, shell=True)

def get_cam_serial_number(rig):
    if rig == 1:
        return "22181614"
    elif rig == 2:
        return "20530175"
    elif rig == 3:
        return "24174008"
    elif rig == 4:
        return "24243513"
    else:
        raise ValueError("Invalid rig number.")

def main():
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Initialize behavior function with scale
        global rd
        rig = args.rig if args.rig is not None else 3
        rd = Scales(rig=rig)
        
        # Initialize session parameters
        session_params = {
            "rig": rig,
            "mouse_id": args.mouse if args.mouse is not None else None,
            "mouse_weight": args.weight,
            "fps": args.fps if args.fps is not None else 30,
            "window_width": args.window_width if args.window_width is not None else 640,
            "window_height": args.window_height if args.window_height is not None else 512,
        }
        
        # Check if we should load a saved configuration
        if args.load_config:
            loaded_params = load_session_config(args.load_config)
            if loaded_params:
                # Update session_params with loaded values, but keep command-line arguments
                for key, value in loaded_params.items():
                    if key not in session_params or session_params[key] is None:
                        session_params[key] = value
                print(f"Loaded configuration: {args.load_config}")
        
        # Get user inputs to complete the session setup
        # Note: This now includes the scales test as a separate first step
        if not args.load_config:
            session_params = get_user_input_for_session(session_params)
        
        # Set up output directories
        date_time = session_params.get("date_time", datetime.now().strftime("%y%m%d_%H%M%S"))
        mouse_id = session_params.get("mouse_id", "test")
        session_folder = args.path if args.path is not None else r"D:\test_output"
        session_folder_name = f"{date_time}_{mouse_id}"
        output_path = str(os.path.join(session_folder, session_folder_name))
        os.makedirs(output_path, exist_ok=True)
        
        # Update session parameters with output path
        session_params["output_path"] = output_path
        session_params["date_time"] = date_time
        
        # Load config if specified
        config_json = args.config_json if args.config_json is not None else r"C:\Behaviour\config.json"
        config = load_config(config_json)
        
        # Retrieve paths from config
        python_exe = config.get("PYTHON_PATH")
        serial_listen_script = config.get("SERIAL_LISTEN")
        camera_exe = config.get("BEHAVIOUR_CAMERA")
        
        # Start serial listener
        serial_listen_command = [
            python_exe, serial_listen_script,
            "--id", mouse_id,
            "--date", date_time,
            "--path", output_path,
            "--rig", str(session_params["rig"])
        ]
        p1 = start_subprocess(serial_listen_command, "ArduinoDAQ")
        time.sleep(10)
        
        # Start camera tracking
        tracker_command = [
            camera_exe,
            "--id", mouse_id,
            "--date", date_time,
            "--path", output_path,
            "--serial_number", get_cam_serial_number(session_params["rig"]),
            "--fps", str(session_params["fps"]),
            "--windowWidth", str(session_params["window_width"]),
            "--windowHeight", str(session_params["window_height"])
        ]
        p0 = start_subprocess(tracker_command, "Camera Script")
        
        # Run the behavior session
        behaviour(session_params)
        
    except Exception as e:
        print("Error in main function")
        traceback.print_exc()

if __name__ == "__main__":
    main()