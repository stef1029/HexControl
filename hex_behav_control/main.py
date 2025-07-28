import os
import json
import time
import argparse
import traceback
from pathlib import Path
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Import common utilities
from common.arduino import setup_serial_connection, get_rig_port
from common.scales import Scales, test_scales
from common.utils import start_subprocess, get_cam_serial_number
from common.params import load_config, parse_arguments

# Import phase modules dynamically
from phases import get_phase_module

# Global variables
log = []
metadata = {}
scales_data = []
tic = 0
rd = None

def timer():
    """Return time since session start"""
    global tic
    toc = time.perf_counter()       
    return toc - tic

def get_user_input_for_session(params=None):
    """Collect user inputs to configure the session"""
    global rd
    
    # Initialize with default parameters if none provided
    if params is None:
        params = {}
    
    # Get basic parameters
    params["mouse_id"] = params.get("mouse_id") or input("Enter mouse ID: ")
    
    try:
        params["mouse_weight"] = params.get("mouse_weight") or float(input("Enter mouse weight (g): "))
    except:
        print("Invalid input. Must be a number. Do not include letters or units.")
        params["mouse_weight"] = float(input("Enter mouse weight (g): "))
    
    # Behavior phase
    if not params.get("phase"):
        try:
            params["phase"] = input("Enter behaviour phase (1-9): ")
        except:
            print("Invalid input. Must be a number (1-9). Do not include letters or units.")
            params["phase"] = input("Enter behaviour phase (1-9): ")
    
    # Number of trials
    try:
        params["number_of_trials"] = params.get("number_of_trials") or int(input("Enter number of desired trials for session (0 = unlimited): ") or "0")
    except:
        print("Invalid input. Must be a number. Do not include letters or units.")
        params["number_of_trials"] = int(input("Enter number of desired trials for session (0 = unlimited): "))
    
    # Get phase-specific parameters using the appropriate phase module
    try:
        phase_module = get_phase_module(params["phase"])
        if phase_module:
            phase_params = phase_module.get_phase_params(params)
            params.update(phase_params)
        else:
            print(f"Warning: Phase {params['phase']} module not found. Continuing with basic parameters.")
    except ImportError:
        print(f"Warning: Phase {params['phase']} module not found. Continuing with basic parameters.")
    except Exception as e:
        print(f"Error loading phase module: {e}")
    
    # Option to save configuration
    save_config = input("Save this configuration for future use? (y/[n]): ").lower() or "n"
    if save_config == "y":
        config_name = input("Enter a name for this configuration: ")
        if config_name:
            # Create configs directory if it doesn't exist
            os.makedirs("configs", exist_ok=True)
            # Save only the user input parameters (exclude runtime parameters)
            user_params = {k: v for k, v in params.items() if k not in 
                         ["rig", "fps", "window_width", "window_height", "output_path", "date_time"]}
            with open(f"configs/{config_name}.json", "w") as f:
                json.dump(user_params, f, indent=4)
            print(f"Configuration saved as 'configs/{config_name}.json'")
    
    return params

def setup_scales_after_arduino(rig):
    """Setup scales and optionally perform a scales test after Arduino has started"""
    global rd
    
    try:
        rd = Scales(rig=rig)
        print(f"Initialized scales for rig {rig}")
        
        # Offer to test scales
        do_scales_test = input("Do scales test? (y/[n]): ").lower() or "n"
        if do_scales_test == "y":
            test_scales(rd)
            
        return True
    except Exception as e:
        print(f"Error initializing scales: {e}")
        print(f"Proceeding with no scales. Some functionality may be limited.")
        return False

def behaviour(session_params):
    """Main behavior function using the session parameters dictionary"""
    global tic, metadata, rd
    
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
        except Exception as e:
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
        metadata = {}
        metadata["Rig"] = rig
        metadata["Mouse ID"] = mouse_ID
        metadata["Date and time"] = date_time
        metadata["Behaviour phase"] = phase
        metadata["FPS"] = fps
        metadata["Number of trials"] = "Not set" if number_of_trials == 0 else number_of_trials
        metadata["Mouse weight"] = mouse_weight
        
        # Load and run appropriate phase module
        try:
            phase_module = get_phase_module(phase)
            if phase_module:
                # Initialize timer
                tic = time.perf_counter()
                
                # Run the phase
                trial_count = phase_module.run_phase(
                    ser=ser, 
                    session_params=session_params, 
                    metadata=metadata,
                    rd=rd,
                    timer=timer,
                    log=log,
                    scales_data=scales_data
                )
            else:
                print(f"Phase {phase} not implemented")
                trial_count = 0
        except ImportError:
            print(f"Error: Phase {phase} module not found.")
            trial_count = 0
        
    except Exception as e:
        print(e)
        traceback.print_exc()
        trial_count = 0
    
    finally:
        # Send termination signal with a shorter command
        try:
            # Handle scales disconnection first
            if rd:
                try:
                    print(Fore.YELLOW + "Disconnecting scales...")
                    # Send stop command to scales
                    rd.ser.write(b'e')
                    time.sleep(0.5)  # Give it time to process
                    rd.ser.close()
                    print(Fore.GREEN + "Scales disconnected successfully.")
                except Exception as e:
                    print(Fore.RED + f"Error disconnecting scales: {e}")
                    
            # Send shorter termination command to Arduino
            ser.write(b'E')
            print(Fore.YELLOW + "Termination signal sent to Arduino.")
            # Wait a moment for Arduino to process
            time.sleep(0.5)
            
            # Wait for acknowledgment
            ack_received = False
            ack_timeout = time.perf_counter() + 3.0  # 3 second timeout
            
            while time.perf_counter() < ack_timeout:
                if ser.in_waiting > 0:
                    response = ser.readline().decode('utf-8').strip()
                    if response == "OK":
                        print(Fore.GREEN + "Arduino acknowledged termination.")
                        ack_received = True
                        break
                time.sleep(0.1)
            
            if not ack_received:
                print(Fore.RED + "Warning: No acknowledgment received from Arduino.")
        except Exception as e:
            print(Fore.RED + f"Error in termination process: {e}")
            
        
        # Save session data (your existing code)
        metadata["Total trials"] = trial_count
        metadata["End time"] = datetime.now().strftime("%y%m%d%H%M%S")
        metadata["Logs"] = log
        metadata["Scales data"] = scales_data
        
        # Existing code to save metadata and close connection
        filename = f"{foldername}_Phase_{phase}_behaviour_data.json"
        try:
            with open(f"{str(Path(output_path) / filename)}", "w") as f:
                json.dump(metadata, f, indent=4)
        except Exception as e:
            print(f"Error saving metadata: {e}")
        
        try:
            ser.close()
        except:
            pass
        
        print("Program finished")

def main():
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Initialize runtime parameters from CLI arguments
        # These won't be saved in configuration files
        runtime_params = {
            "rig": args.rig if args.rig is not None else 3,
            "fps": args.fps if args.fps is not None else 30,
            "window_width": args.window_width if args.window_width is not None else 640,
            "window_height": args.window_height if args.window_height is not None else 512,
        }
        
        # Initialize user parameters
        user_params = {}
        
        # Command line arguments take precedence over defaults
        if args.mouse:
            user_params["mouse_id"] = args.mouse
        if args.weight:
            user_params["mouse_weight"] = args.weight
        
        # Get user inputs to complete the session setup
        # Merge with existing user_params
        session_params = get_user_input_for_session(user_params)
        
        # Set up output directories
        date_time = datetime.now().strftime("%y%m%d_%H%M%S")
        mouse_id = session_params.get("mouse_id", "test")
        session_folder = args.path if args.path is not None else r"D:\test_output"
        session_folder_name = f"{date_time}_{mouse_id}"
        output_path = str(os.path.join(session_folder, session_folder_name))
        os.makedirs(output_path, exist_ok=True)
        
        # Add runtime parameters and path info to session parameters
        session_params.update(runtime_params)
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
        
        print(Fore.YELLOW + "Starting Arduino DAQ process...")
        arduino_daq_process = start_subprocess(serial_listen_command, "ArduinoDAQ")
        
        # Define the expected signal file path for Arduino connection
        rig_value = session_params["rig"]
        if rig_value is None:
            connection_signal_file = os.path.join(output_path, "arduino_connected.signal")
        else:
            connection_signal_file = os.path.join(output_path, f"rig_{rig_value}_arduino_connected.signal")
        
        # Wait for the connection signal file with timeout
        print(Fore.CYAN + f"Waiting for Arduino connection signal file...")
        connection_timeout = 30  # seconds
        connection_wait_start = time.time()
        connection_established = False
        
        while time.time() - connection_wait_start < connection_timeout:
            if os.path.exists(connection_signal_file):
                connection_established = True
                print(Fore.GREEN + f"Arduino connection confirmed after {time.time() - connection_wait_start:.1f} seconds")
                break
            time.sleep(0.5)  # Check every half second
        
        if not connection_established:
            print(Fore.RED + f"Warning: Arduino connection signal not detected after {connection_timeout} seconds")
            print(Fore.YELLOW + "Checking Arduino process status...")
            
            # Check if the Arduino process is still running
            if arduino_daq_process.poll() is not None:
                print(Fore.RED + f"Error: Arduino DAQ process has terminated with exit code {arduino_daq_process.poll()}")
                input(Fore.RED + "Press Enter to exit.")
                return
            
            # Ask user if they want to continue anyway
            continue_anyway = input(Fore.YELLOW + "Do you want to continue anyway? (not recommended) (y/[n]): ")
            if continue_anyway.lower() != 'y':
                print(Fore.RED + "Terminating process...")
                arduino_daq_process.terminate()
                input(Fore.RED + "Press Enter to exit.")
                return
        
        # MOVED: Initialize scales AFTER Arduino is confirmed connected
        print(Fore.CYAN + "Setting up scales now that Arduino is connected...")
        print("Proceed with scales test if needed.")
        setup_scales_after_arduino(session_params["rig"])
        
        # Start camera tracking
        print(Fore.YELLOW + "Starting camera tracking...")
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
        camera_process = start_subprocess(tracker_command, "Camera Script")
        
        # Run the behavior session
        print(Fore.GREEN + "Starting behavior session...")
        behaviour(session_params)
        
        print(Fore.GREEN + "Behavior session completed. Waiting for processes to finish...")
        
        # Wait for camera and Arduino processes to complete
        print(Fore.YELLOW + "Waiting for camera tracking to complete...")
        camera_process.wait()
        
        print(Fore.YELLOW + "Waiting for Arduino DAQ to complete...")
        arduino_daq_process.wait()
        
        print(Fore.GREEN + "All processes completed successfully.")
        input(Fore.GREEN + "Press Enter to exit.")
        
    except Exception as e:
        print(Fore.RED + "Error in main function")
        traceback.print_exc()
        input(Fore.RED + "Take note of error message. Press Enter to exit")

if __name__ == "__main__":
    main()