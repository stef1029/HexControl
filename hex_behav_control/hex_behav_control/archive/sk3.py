

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

def behaviour(new_mouse_ID=None, new_date_time=None, new_path=None, rig=None, fps=30, mouse_weight=None):
    try:
        exit_key = 'esc'

        if rig == None:
            port = "COM4"
        elif rig == 1:
            port = "COM4"
        elif rig == 2:
            port = "COM11"
        elif rig == 3:
            port = "COM21"
        elif rig == 4:
            port = "COM6"
        else:
            raise ValueError("Invalid rig number.")

        try:
            ser = serial.Serial(port, 9600, timeout=0)
            time.sleep(2)  # wait for arduino to boot up
        except serial.SerialException:
            print(f"Serial connection not found on {port}, trying again...")
            ser = serial.Serial(port, 9600, timeout=0)
            time.sleep(2)  # wait for arduino to boot up

        ser.read_all()  # Clear serial buffer
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        global tic
        print("Setup in progress...")

        test = "n"
        test = input("Test? (y/[n]): ")
        if test == "y":
            if new_mouse_ID == None:
                mouse_ID = "test"
            else:
                mouse_ID = new_mouse_ID
            mouse_weight = 20
            number_of_trials = 5
            do_scales_test = "n"
            try:
                phase = input("Enter behaviour phase (1-9): ")
            except:
                print("Invalid input. Must be a number (1-9). Do not include letters or units.")
                phase = input("Enter behaviour phase (1-9): ")
        else:
            # Mouse ID saved
            if new_mouse_ID == None:
                mouse_ID = input("Enter mouse ID: ")
            else:
                mouse_ID = new_mouse_ID

            # Mouse weight entered. Catches invalid inputs and instructs to try again
            if weight == None:
                try:
                    mouse_weight = float(input("Enter mouse weight (g): "))
                except:
                    print("Invalid input. Must be a number. Do not include letters or units.")
                    mouse_weight = float(input("Enter mouse weight (g): "))

            # Offers option to test scales with known weight before starting experiment
            do_scales_test = input("Do scales test? (y/[n]): ")
            if do_scales_test == "y":
                test_scales()
            else:
                pass

            # Choose behaviour phase:
            try:
                phase = input("Enter behaviour phase (1-9): ")
            except:
                print("Invalid input. Must be a number (1-9). Do not include letters or units.")
                phase = input("Enter behaviour phase (1-9): ")

            number_of_trials = 0
            try:
                number_of_trials = int(input("Enter number of desired trials for session (0 = unlimited):"))
            except:
                print("Invalid input. Must be a number. Do not include letters or units.")
                number_of_trials = int(input("Enter number of desired trials for session (0 = unlimited):"))

        # Map phase to Arduino case select number
        phase_to_case_map = {
            "0": 0,  # Flush function
            "1": 2,  # Phase 1
            "2": 2,  # Phase 2
            "3": 3,  # Phase 3
            "3b": 3, # Phase 3b
            "3c": 3, # Phase 3c
            "4": 3,  # Phase 4
            "4b": 3, # Phase 4b
            "4c": 3, # Phase 4c
            "5": 4,  # Phase 5
            "6": 3,  # Phase 6
            "7": 3,  # Phase 7
            "8": 3,  # Phase 8
            "9": 3,  # Phase 9
            "9b": 3, # Phase 9b
            "9c": 6, # Phase 9c (wait time)
            "10": 8, # LED catch trial
            "test": 5, # Learning test
        }
        
        case_select = phase_to_case_map.get(phase, 3)  # Default to 3 if not found
        
        trial_count = 0
        successes = 0
        reward_count = 0

        if new_date_time == None:
            date_time = f"{datetime.now():%y%m%d_%H%M%S}"
        else:
            date_time = new_date_time

        foldername = f"{date_time}_{mouse_ID}"

        if new_path == None:
            output_path = os.path.join(os.getcwd(), foldername)
            os.mkdir(output_path)
        else:
            output_path = new_path

        metadata["Rig"] = rig
        metadata["Mouse ID"] = mouse_ID
        metadata["Date and time"] = date_time
        metadata["Behaviour phase"] = phase
        metadata["FPS"] = fps
        metadata["Arduino case"] = case_select

        if number_of_trials == 0:
            metadata["Number of trials"] = "Not set"
        if number_of_trials != 0:
            metadata["Number of trials"] = number_of_trials

        if do_scales_test == "y":
            metadata["Scales tested?"] = "Yes"
        else:
            metadata["Scales tested?"] = "No"

        metadata["Mouse weight"] = mouse_weight
        mouse_weight_offset = 2
        m_break = False
        trial_print_delimiter = "----------------------------------------"

        # Send the case select command to Arduino before starting
        print(f"Sending case select {case_select} to Arduino...")
        command = f"SET:{case_select}\n"
        print(command)
        ser.write(command.encode())
        
        # Wait for acknowledgment from Arduino
        ack_received = False
        start_time = time.perf_counter()
        while not ack_received and time.perf_counter() - start_time < 5:  # 5-second timeout
            time.sleep(0.1)
            if ser.in_waiting:
                response = ser.readline().decode('utf-8', errors='replace').strip()
                if response.startswith("ACK:SET:"):
                    ack_received = True
                    print(f"Arduino acknowledged case select: {response}")

        if not ack_received:
            print("Warning: No acknowledgment received from Arduino. Continuing anyway...")
        
        # Now wait for the start signal from Arduino
        print("Waiting for start signal from Arduino...")
        ser.read_all()  # Clear serial buffer
        
        # Wait for the start signal ('S')
        start_signal_received = False
        start_time = time.perf_counter()
        while not start_signal_received and time.perf_counter() - start_time < 10:  # 10-second timeout
            if ser.in_waiting:
                data = ser.read().decode('utf-8', errors='replace')
                if data == "S":
                    start_signal_received = True
                    print(f"Start signal received {datetime.now().strftime('%H%M%S')}")
                    ser.read_all()  # Clear any remaining buffer

        if not start_signal_received:
            print("Warning: No start signal received from Arduino. Check connections and try again.")
            return

        # Start timer
        tic = time.perf_counter()
        
        # The rest of the function for phase 9c
        if phase == "9c":
            print(Fore.CYAN + "Full Task with waiting period: In phase 9, reward is given at 6 ports randomly. Incorrect touches are penalised.")
            
            audio = input("Audio cue? (y/n): ").strip().lower()
            wait_duration = input("Enter wait duration (ms): ").strip()
            cue_duration = input("Enter cue duration (ms) (0 = unlimited) (1 = mixed): ").strip()

            if audio == "n":
                num_ports = 6
                try:
                    num_ports = int(input("Enter number of ports (1-6): ").strip())
                except ValueError:
                    print(Fore.RED + "Invalid number of ports, must be a number.")
                    try:
                        num_ports = int(input("Enter number of ports (1-6): ").strip())
                    except ValueError:
                        raise ValueError("Invalid number of ports")
                    
                ports_in_use = []
                if num_ports == 6:
                    ports_in_use = [0, 1, 2, 3, 4, 5]
                elif num_ports < 6:
                    for i in range(num_ports):
                        port = int(input(f"Enter port {i+1}/{num_ports}: ").strip())
                        ports_in_use.append(port - 1)
                else:
                    raise ValueError("Invalid number of ports")
                        
                metadata["Port"] = [(port + 1) for port in ports_in_use]
                number_of_ports = len(ports_in_use)
                if number_of_trials != 0:
                    trial_order = []
                    for i in range(number_of_trials):
                        trial_order.append(i % number_of_ports)

                    random.shuffle(trial_order)

            # The rest of the phase 9c implementation remains the same...
            # ... (implementation continues)
            
            # Send Arduino cue_duration
            ser.write(f"{cue_duration}".encode())
            
            # Listen for confirmation
            start = time.perf_counter()
            while True:
                time.sleep(0.001)
                incoming = ser.readline().decode("utf-8").strip()
                if len(incoming) > 0:
                    print(Fore.GREEN + f"Cue duration confirmed: {incoming}")
                    break
                if time.perf_counter() - start > 1:
                    print(Fore.RED + "Confirmation timeout")
                    break
            
            # The rest of your phase 9c implementation remains unchanged
            
        # Rest of the behaviour function for other phases...
        # ...

    except Exception as e:
        print(e)
        traceback.print_exc()

    finally:
        # ---------------- Write log lists to file -------------------------------------------- #
        metadata["Total trials"] = trial_count
        metadata["End time"] = datetime.now().strftime("%y%m%d%H%M%S")
        metadata["Logs"] = log
        metadata["Scales data"] = scales_data

        filename = f"{foldername}_Phase_{phase}_behaviour_data.json"
        # Save metadata to json file
        with open(f"{str(Path(output_path) / filename)}", "w") as f:
            json.dump(metadata, f, indent=4)
        
        ser.close()
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
        # Parse arguments and set default values
        args = parse_arguments()
        rig = args.rig if args.rig is not None else 3
        session_folder = args.path if args.path is not None else r"D:\test_output"
        mouse_id = args.mouse if args.mouse is not None else "test"
        mouse_weight = args.weight if args.weight is not None else 20.0
        fps = args.fps if args.fps is not None else 30
        window_width = args.window_width if args.window_width is not None else 640
        window_height = args.window_height if args.window_height is not None else 512
        config_json = args.config_json if args.config_json is not None else r"C:\Behaviour\config.json"

        # Set main directories and load configuration
        config = load_config(config_json)

        # Set up output directories
        date_time = datetime.now().strftime("%y%m%d_%H%M%S")
        session_folder_name = f"{date_time}_{mouse_id}"
        output_path = str(os.path.join(session_folder, session_folder_name))
        os.mkdir(output_path)

        # Retrieve paths from config
        python_exe = config.get("PYTHON_PATH")
        serial_listen_script = config.get("SERIAL_LISTEN")
        camera_exe = config.get("BEHAVIOUR_CAMERA")

        # Start serial listener
        serial_listen_command = [python_exe, serial_listen_script, 
                                 "--id", mouse_id, 
                                 "--date", date_time, 
                                 "--path", output_path, 
                                 "--rig", str(rig)]
        p1 = start_subprocess(serial_listen_command, "ArduinoDAQ")
        time.sleep(10)

        # Start camera tracking
        tracker_command = [camera_exe, 
                           "--id", mouse_id, 
                           "--date", date_time, 
                           "--path", output_path, 
                           "--serial_number", get_cam_serial_number(rig), 
                           "--fps", str(fps), 
                           "--windowWidth", str(window_width), 
                           "--windowHeight", str(window_height)]

        p0 = start_subprocess(tracker_command, "Camera Script")

        # Initialize behavior function with scale
        global rd
        rd = Scales(rig=rig)
        behaviour(new_path=output_path, new_mouse_ID=mouse_id, new_date_time=date_time, rig=rig, fps=fps, mouse_weight=mouse_weight)

    except Exception as e:
        print("Error in main function")
        traceback.print_exc()

if __name__ == "__main__":
    main()