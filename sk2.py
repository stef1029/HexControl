

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

def behaviour(new_mouse_ID = None, new_date_time = None, new_path = None, rig = None, fps = 30, mouse_weight = None):

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
            port = "COM15"
        else:
            raise ValueError("Invalid rig number.")

        try:
            ser = serial.Serial(port, 9600, timeout=0)
            time.sleep(2) # wait for arduino to boot up
        except serial.SerialException:
            print(f"Serial connection not found on {port}, trying again...")
            ser = serial.Serial(port, 9600, timeout=0)
            time.sleep(2) # wait for arduino to boot up

        ser.read_all()                      # Clear serial buffer
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        global tic
        # def timer():
        #     global tic
        #     toc = time.perf_counter()       
        #     return toc - tic


        print("Proceed until 'waiting for start signal from arduino.'")

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

        if number_of_trials == 0:
            
            metadata["Number of trials"] = "Not set"
        if number_of_trials != 0:
            
            metadata["Number of trials"] = number_of_trials

        if do_scales_test == "y":                       # Scales test?
                
            metadata["Scales tested?"] = "Yes"   
        else:
            
            metadata["Scales tested?"] = "No"


        metadata["Mouse weight"] = mouse_weight

        mouse_weight_offset = 2

        m_break = False

        trial_print_delimiter = "----------------------------------------"

        #------------------------ Manual control ------------------------#

        if phase == "0":
            print("""\nManual control. 
                \n\rUse setting 1 on arduino.
                \n\rPress M to exit.""")

            lettersAndNumbers = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 
                            'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 
                            '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', ' ']
            while True:
            # Activate reward solenoids
                for character in lettersAndNumbers:   
                    if keyboard.is_pressed(f'{character}'):
                        ser.write(f"{character}".encode())
                        time.sleep(0.2)


                incoming = ser.readline()
                if len(incoming) > 0:
                    print(incoming)

                if keyboard.is_pressed(exit_key):
                    ser.write(f"{character}".encode())
                    break

        #------------------------ PHASE 1 ------------------------#
        if phase == "1":
            print("\nPhase 1: Reward given for sub-threshold scales readings.")
            print("In phase 1, reward is only given at one port.")
            print("Use setting 2 on arduino")

            # Prompt user for port number:
            try: port = int(input("Enter port number (1-6): ")) - 1
            except ValueError: 
                # Allow a second chance if user inputs wrong thing:
                print("Invalid input. Must be a number (1-6). Do not include letters or units.")
                port = int(input("Enter port number (1-6): "))
            
            # Add port number to metadata:
            metadata["Port"] = port + 1

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer

            # Loops, waiting for start signal from arduino.
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            
            # Once start signal received, clear the serial buffer, print the time and start session timer:
            ser.read_all()                      # Clear serial buffer
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.
            # From here, timer() will give time since start signal received from arduino.

            # What percentage of mouse weight will the threshold be?:
            percentage = 20 / 100

            # I believe this is an old test to avoid the error fixed by having non-zero threshold time for the scales, so may be redundant:
            given = False
            
            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]

            # clear buffer of scales readings to make up to date:
            rd.clear_buffer()

            # This is the main session loop. It will run until the user presses 'm' to end the program.
            while True:
                ser.read_all()                      # Clear serial buffer                 # Below: if threshold time is set to zero you get errors with immediate reward giving after taking.
                state, activation_time = pressure_plate(mouse_weight * percentage, 0.2)               # If mouse_weight is above threshold for 0.2 seconds, returns True.
                if state:                        # If mouse_weight is above threshold for 0.2 seconds, returns True.
                    if given == False:
                        ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                        given = True
                        log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Reward given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer                  
                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.     
                            weight()                                      # Call weight() to continue updating scales_data list.

                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all()                      # Clear serial buffer
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        given = False
                                        print(f"Trials: {trial_count}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log
                                        if trial_count >= number_of_trials and number_of_trials != 0:
                                            m_break = True
                                        print(trial_print_delimiter)
                                        break      
                                    if incoming[1] != str(port+1):
                                        if incoming[1] == "F":
                                            print("Trial timeout")
                                            given = False
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
                                ser.read_all()                      # Clear serial buffer
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True
                                
                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break




        #------------------------ PHASE 2 ------------------------#
        if phase == "2":
            # In phase 2, reward is only given when the mouse fully stands on the platform.
            # The scales threshold is therefore set to be near the body weight of the mouse.
            # The arduino should also log incorrect port touches but not react to them.


            print("Phase 2: Reward given for over-threshold scales readings.")
            print("In phase 2, reward is only given at one port.")
            print("Use setting 2 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            metadata["Port"] = port + 1
            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
                
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break 
                
            ser.read_all()                      # Clear serial buffer
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.


            # Set negative offset for mouse weight so it's not looking for the exact weight given earlier.

            
            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, 0.2)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    ser.read_all()                      # Clear serial buffer
                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Reward given")

                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    time.sleep(0.01)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            time.sleep(0.01)
                            ser.read_all()                      # Clear serial buffer

                            while True:
                                time.sleep(0.001)
                                # Wait for arduino to say that reward has been taken.
                                weight()                                # Call pressure_plate to continue updating scales_data list.
                                incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                                if len(incoming) > 1:
                                    if incoming[0] == "C":
                                        ser.read_all() 
                                        if incoming[1] == str(port+1):
                                            print("Reward taken")
                                            print(f"Trials: {trial_count}")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.

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
                                    ser.read_all()                      # Clear serial buffer
                                    print(trial_print_delimiter)
                                    break
                                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                    m_break = True
                                    
                                if m_break == True:
                                    break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break



        # ------------------------ PHASE 3 ------------------------#

        # Phase 3 is where the visiting of incorrect ports gets penalised.
        # The code should wait for the scales to reach threshold, then send a signal to the arduino to prime the reward port.
        # The arduino code should complement this and use the sensors to determine if the mouse is at the correct port.


        if phase == "3":
            print("Phase 3: Reward given for correct port visits. LED cue given at port.")          # May potentially need a non-penalised phase 3 before this.
            print("In phase 3, reward is only given at one port.")
            print("Use setting 3 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            metadata["Port"] = port + 1

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]    
            m_break = False

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, 0.2)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    ser.read_all()                      # Clear serial buffer
                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if len(incoming) > 1 and incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer                 # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
                                        if trial_count >= number_of_trials and number_of_trials != 0:
                                            m_break = True
                                        print(trial_print_delimiter)
                                        break      
                                    if incoming[1] != str(port):
                                        if incoming[1] == "F":
                                            print("Trial timeout")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                                        else:
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                ser.read_all()                      # Clear serial buffer
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True
                            
                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break



        # ------------------------ PHASE 4 ------------------------#
        if phase == "4":
            print("Phase 4: Reward given for correct port visits. Mouse must wait on platform momentarily before cue is given.")
            print("In phase 4, reward is only given at one port.")
            print("Use setting 3 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            metadata["Port"] = port + 1

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]
            m_break = False

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                # Call pressure_plate to continue updating scales_data list.
                            # if len(ser.in_waiting) > 0:
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                ser.read_all()                      # Clear serial buffer
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break


        # ------------------------ Learning test ------------------------


        if phase == "test":
            print("This is a learning test session. Mice are given a reward repeatedly at one port, then the cue location is changed.")
            print("This is to test what phase of learning the mouse is at.")
            print("Use setting 5 on arduino")
            print("Make sure parameters are set in arduino code.")

            portA = 0
            portB = 2
            
            metadata["Port"] = [portA + 1, portB + 1]

            initial_series_length = 5
            test_length = 10
            total_trials = initial_series_length + test_length

            metadata["Initial series length"] = initial_series_length
            metadata["Test length"] = test_length
            

            trial_order = []
            for i in range(0, initial_series_length):
                trial_order.append(portA)
            for i in range(initial_series_length, initial_series_length + test_length):
                trial_order.append(portB)

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    # Select the port to give cue at either from shuffled list or randomly:
                    
                    port = trial_order[trial_count]
                    
                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(portA+1) or (incoming[1] == str(portB+1) and trial_count > initial_series_length):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
                                        if trial_count >= total_trials:
                                            m_break = True
                                        print(trial_print_delimiter)
                                        break      
                                    if incoming[1] != str(portA+1) or (incoming[1] != str(portB+1) and trial_count > initial_series_length):
                                        if incoming[1] == "F":
                                            print("Trial timeout")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                            if trial_count >= total_trials:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                                        else:
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= total_trials:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break            

        # ------------------------ PHASE 5 ------------------------#
        if phase == "5":
            # In phase 5, port 3 is introduced. Mice are allowed to explore to find it, so incorrect ports are not penalised.
            # Incorrect port touches are logged though.
            # Basically phase 1 again but with proper platform etiquette 

            print("Phase 5: New port introduced. Mice allowed to explore, incorrect touches not penalised.")
            print("In phase 5, reward is only given at one, new, port.")
            print("Use setting 4 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            metadata["Port"] = port + 1

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break

        # ------------------------ PHASE 6 ------------------------#
        if phase == "6":
            # In phase 6, port 3 the reward port, and incorrect touches are penalised.
            print("Phase 6: Port 3. Incorrect touches are penalised.")
            print("In phase 6, reward is only given at one port.")
            print("Use setting 3 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            metadata["Port"] = port + 1

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:   
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break


        # ------------------------ PHASE 7 ------------------------#
        if phase == "7":
            print("In phase 7, reward is given at 2 ports randomly, port A and port B. Incorrect touches are penalised.")
            print("Use setting 3 on arduino")
            port_a = int(input("Enter port A number (1-6): ")) - 1
            port_b = int(input("Enter port B number (1-6): ")) - 1
            
            metadata["Port"] = [port_a + 1, port_b + 1]

            if number_of_trials != 0:       # If number_of_trials has been set:
                trial_order = []
                for i in range(0, number_of_trials):            # Generates a random sequence but with equal proportions of port A and port B.
                    if i < number_of_trials/2:
                        trial_order.append(port_a)
                    else:
                        trial_order.append(port_b)
                random.shuffle(trial_order)
            ports_in_use = [port_a, port_b]

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    # Select the port to give cue at either from shuffled list or randomly:
                    if number_of_trials != 0:
                        port = trial_order[trial_count]
                    else:
                        port = random.choice(ports_in_use)

                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print(f"Cue given: {port+1}, time: {datetime.now().strftime('%H%M%S')}")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                             # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
                                        if trial_count >= number_of_trials and number_of_trials != 0:
                                            m_break = True
                                        print(trial_print_delimiter)
                                        break      
                                    if incoming[1] != str(port+1):
                                        if incoming[1] == "F":
                                            print(f"Trial timeout")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                                        else:
                                            print(f"Port {incoming[1]} touched, reward not given.")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break                               

        # ------------------------ PHASE 8 ------------------------#
        if phase == "8":
            print("In phase 8, reward is given at x ports randomly, set below. Incorrect touches are penalised.")
            print("Use setting 3 on arduino")
            try: number_of_ports = int(input("Enter number of ports to use (1-6): "))
            except ValueError: number_of_ports = int(input("Error: Enter an integer. Enter number of ports to use (1-6): "))
            
            ports_in_use = []
            if number_of_ports > 6:
                number_of_ports = 6
            if number_of_ports == 6:
                ports_in_use = [0, 1, 2, 3, 4, 5]
            else:
                for i in range(0, number_of_ports):
                    port = int(input(f"Enter port {i+1} number (1-6): ")) - 1
                    ports_in_use.append(port)

            
            
            metadata["Port"] = [(port + 1) for port in ports_in_use]


            if number_of_trials != 0:       # If number_of_trials has been set:
                trial_order = []
                for i in range(number_of_trials):             # Generates a random sequence but with equal proportions of port A and port B.
                    trial_order.append(i % number_of_ports)

                random.shuffle(trial_order)

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    # Select the port to give cue at either from shuffled list or randomly:
                    if number_of_trials != 0:
                        port = trial_order[trial_count]
                    else:
                        port = random.choice(ports_in_use)

                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break

                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break            


        # ------------------------ PHASE 9 ------------------------#

        if phase == "9":
            print(Fore.CYAN + "Full Task: In phase 9, reward is given at 6 ports randomly, set below. Incorrect touches are penalised.")
            print(Fore.YELLOW + "Use setting 3 on arduino")

            ports_in_use = [0, 1, 2, 3, 4, 5]
            metadata["Port"] = [(port + 1) for port in ports_in_use]
            number_of_ports = 6

            if number_of_trials != 0:  # If number_of_trials has been set:
                trial_order = []
                for i in range(number_of_trials):  # Generates a random sequence but with equal proportions of port A and port B.
                    trial_order.append(i % number_of_ports)
                random.shuffle(trial_order)

            # Startup finished, now waits for start signal from arduino
            print(Fore.CYAN + "Waiting for start signal from arduino.")
            ser.read_all()  # Clear serial buffer
            while True:
                incoming = ser.read().decode('utf-8', errors='replace')
                if incoming == "S":
                    break

            print(Fore.GREEN + f"Start signal received {datetime.now().strftime('%H%M%S')}")

            ser.read_all()  # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()  # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)  # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:
                    # Select the port to give cue at either from shuffled list or randomly:
                    if number_of_trials != 0:
                        port = trial_order[trial_count]
                    else:
                        port = random.choice(ports_in_use)

                    ser.write(f"{port + 1}".encode())  # Send reward port number to arduino.
                    log.append(Fore.MAGENTA + f"OUT;{timer():0.4f}")  # Add time to log.

                    trial_count += 1
                    print(Fore.CYAN + f"Cue given: {port + 1}")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if not error:
                        if incoming[0] == "R":
                            ser.read_all()  # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()  # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()  # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all()
                                    if incoming[1] == str(port + 1):
                                        print(Fore.GREEN + "Reward taken")
                                        print(Fore.CYAN + f"Trials: {trial_count}")
                                        successes += 1
                                        print(Fore.CYAN + f"Successes: {successes}")
                                        log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")  # Add time to log.
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
                                print(Fore.RED + f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                                m_break = True

                            if m_break:
                                break

                if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                    m_break = True

                if m_break:
                    break



        # ------------------------ PHASE 3b ------------------------#

        if phase == "3b":
            print("""Phase 3b: Reward given for correct port visits. 
                \n\rRandomly chooses between audio and LED cue given at port.
                \n\rAudio port is always port 1.""")         
            # May potentially need a non-penalised phase 3 before this.
            print("In phase 3, reward is only given at one correct port.")
            print("Use setting 3 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            
            metadata["Port"] = port + 1

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")

            if number_of_trials != 0:       # If number_of_trials has been set:
                cue_order = []
                for i in range(0, number_of_trials):            # Generates a random sequence but with equal proportions of audio and visual cues.
                    if i < number_of_trials/2:
                        cue_order.append(port+1)
                    else:
                        cue_order.append("7")
                random.shuffle(cue_order)

            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            m_break = False

            pause_time = 1

            metadata["Pause time"] = pause_time
            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    signal = ""
                    if number_of_trials != 0:
                        signal = cue_order[trial_count]
                    else:
                        signal = random.choice([port+1, "7"])

                    ser.write(f"{signal}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print(f"Cue given: {signal}")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True
                            
                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break

        # ------------------------ PHASE 3c ------------------------#

        # Phase 3 is where the visiting of incorrect ports gets penalised.
        # The code should wait for the scales to reach threshold, then send a signal to the arduino to prime the reward port.
        # The arduino code should complement this and use the sensors to determine if the mouse is at the correct port.


        if phase == "3c":
            print("Phase 3c: Reward given for correct port visits. GO tone given after user set time sat on platform.")          # May potentially need a non-penalised phase 3 before this.
            print("In phase 3, reward is only given at one port.")
            print("Use setting 3 on arduino")
            # port = int(input("Enter port number (1-6): ")) - 1
            port = 7
            correct_port = 1

            metadata["Port"] = correct_port
            platform_time = int(input("Mouse time on platform before cue (ms): "))
            metadata["Platform time"] = platform_time

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]    
            m_break = False

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, (0.2 + (platform_time/1000)))               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(correct_port):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
                                        if trial_count >= number_of_trials and number_of_trials != 0:
                                            m_break = True
                                        print(trial_print_delimiter)
                                        break      
                                    if incoming[1] != str(correct_port):
                                        if incoming[1] == "F":
                                            print("Trial timeout")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F")
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                                        else:
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                ser.read_all()                      # Clear serial buffer
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True
                            
                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break

        # ------------------------ PHASE 4b ------------------------#
        if phase == "4b":
            print("""Phase 4b: Audio and visual mixed. Reward given for correct port visits. 
                \rMouse must wait on platform momentarily before cue is given.""")
            print("In phase 4, reward is only given at one port.")
            print("Use setting 3 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            metadata["Port"] = port + 1

            if number_of_trials != 0:       # If number_of_trials has been set:
                cue_order = []
                for i in range(0, number_of_trials):            # Generates a random sequence but with equal proportions of audio and visual cues.
                    if i < number_of_trials/2:
                        cue_order.append(port+1)
                    else:
                        cue_order.append("7")
                random.shuffle(cue_order)

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            m_break = False

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    signal = ""
                    if number_of_trials != 0:
                        signal = cue_order[trial_count]
                    else:
                        signal = random.choice([port+1, "7"])

                    ser.write(str(signal).encode())                            # Send reward port number to arduino.                        # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    cue = "audio" if signal == "7" else str(port+1)
                    port = 0 if signal == "7" else port
                    trial_count += 1
                    print(f"Cue given: {cue}")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break

        # ------------------------ PHASE 4c ------------------------#
        if phase == "4c":
            print("""Phase 4c: Just audio. Reward given for correct port visits. 
                \rMouse must wait on platform momentarily before cue is given.""")
            print("For reteaching audio signal after visual cue learning")
            print("In phase 4, reward is only given at one port.")
            print("Use setting 3 on arduino")
            port = int(input("Enter port number (1-6): ")) - 1
            metadata["Port"] = port + 1



            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            m_break = False

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    signal = ""

                    signal = "7"

                    ser.write(f"{signal}".encode())                            # Send reward port number to arduino.                        # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    trial_count += 1
                    print("Cue given")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break

    # ------------------------ PHASE 9b ------------------------#

        if phase == "9b":
            print("""Full Task with audio trials: 
                \n\rIn phase 9, reward is given at 6 ports randomly, set below. Incorrect touches are penalised.
                \n\rAudio trials also randomly mixed in.""")
            print("Use setting 3 on arduino")

            proportion_audio = input("Proportion of audio trials (6 = 50:50 audio:visual): ")
            
            ports_in_use = [0, 1, 2, 3, 4, 5]

            for i in range(0, int(proportion_audio)):
                ports_in_use.append(6)

            metadata["Port"] = [(port + 1) for port in ports_in_use]
            number_of_ports = len(ports_in_use)

            if number_of_trials != 0:       # If number_of_trials has been set:
                trial_order = []
                for i in range(number_of_trials):             # Generates a random sequence but with equal proportions of port A and port B.
                    trial_order.append(i % number_of_ports)

                random.shuffle(trial_order)         # this chunk currently not working

            # Startup finished, now waits for start signal from arduino
            print("Waiting for start signal from arduino.")
            ser.read_all()                      # Clear serial buffer
            while True:
                incoming = ser.read().decode()          # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            
            print(f"Start signal received {datetime.now().strftime('%H%M%S')}") 

            ser.read_all()                      # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()           # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "arduino time (ms)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)               # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:   
                    # Select the port to give cue at either from shuffled list or randomly:
                    if number_of_trials != 0:
                        port = trial_order[trial_count]
                    else:
                        port = random.choice(ports_in_use)

                    ser.write(f"{port+1}".encode())                          # Send reward port number to arduino.
                    log.append(f"OUT;{timer():0.4f}")                                   # Add time to log.      

                    cue = str(port+1)
                    if port == 6:   # correct for detecting audio cue correct touches.
                        port = 0
                        cue = "audio"

                    trial_count += 1
                    print(f"Cue given: {cue}")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if error == False:
                        if incoming[0] == "R":
                            ser.read_all()                      # Clear serial buffer

                        while True:
                            time.sleep(0.001)
                            # Wait for arduino to say that reward has been taken.
                            weight()                                 # Call pressure_plate to continue updating scales_data list.
                            incoming = ser.readline().decode("utf-8").strip()                                          # Read arduino port number.
                            if len(incoming) > 1:
                                if incoming[0] == "C":
                                    ser.read_all() 
                                    if incoming[1] == str(port+1):
                                        print("Reward taken")
                                        print(f"Trials: {trial_count}")
                                        successes += 1
                                        print(f"Successes: {successes}")
                                        log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")                        # Add time to log.
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
                                            print(f"Port {incoming[1]} touched, reward not given")
                                            log.append(f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};F") 
                                            if trial_count >= number_of_trials and number_of_trials != 0:
                                                m_break = True
                                            print(trial_print_delimiter)
                                            break
                            if time.perf_counter() - receive_time > trial_timeout:
                                print(f"Serial error, timeout: {incoming}")
                                print(trial_print_delimiter)
                                break
                            if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                                m_break = True

                            if m_break == True:
                                break
                    
                if keyboard.is_pressed(exit_key):                                            # If m is pressed, end program.
                    m_break = True

                if m_break == True:
                    break            

        # ------------------------ PHASE 9 waiting period version------------------------#

        if phase == "9c":
            print(Fore.CYAN + "Full Task with waiting period: In phase 9, reward is given at 6 ports randomly, set below. Incorrect touches are penalised.")
            print(Fore.YELLOW + "Use setting 6 on arduino")

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
                if number_of_trials != 0:       # If number_of_trials has been set:
                    trial_order = []
                    for i in range(number_of_trials):             # Generates a random sequence but with equal proportions of port A and port B.
                        trial_order.append(i % number_of_ports)

                    random.shuffle(trial_order)

            if audio == "y":
                proportion_audio = int(input("Proportion of audio trials (6 = 50:50 audio:visual, 0 = all audio): ").strip())

                if number_of_trials != 0:
                    if proportion_audio == 0:
                        # If 0 is entered, all trials are audio
                        trial_order = [6] * number_of_trials  # All cues will be audio
                    else:
                        # Calculate audio and visual trial counts
                        total_audio_trials = number_of_trials * proportion_audio // (proportion_audio + 6)
                        total_visual_trials = number_of_trials - total_audio_trials
                        
                        # Initialize trial_order list with the correct proportion of audio and visual trials
                        trial_order = [6] * total_audio_trials + [(i % 5) + 1 for i in range(total_visual_trials)]  # Exclude port 0 from visual trials
                        
                        # Shuffle the trial_order to randomize the order of trials
                        random.shuffle(trial_order)
                else:
                    if proportion_audio == 0:
                        ports_in_use = [6]  # Only audio port is in use
                    else:
                        ports_in_use = [1, 2, 3, 4, 5]  # Exclude port 0 from visual ports
                        for i in range(0, int(proportion_audio)):
                            ports_in_use.append(6)


            # Startup finished, now waits for start signal from arduino
            print(Fore.CYAN + "Waiting for start signal from arduino.")
            ser.read_all()  # Clear serial buffer
            while True:
                incoming = ser.read().decode()  # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break

            # send arduino cue_duration:
            ser.write(f"{cue_duration}".encode())
            # listen for confirmation:
            start = time.perf_counter()
            while True:
                time.sleep(0.001)
                incoming = ser.readline().decode("utf-8").strip()
                if len(incoming) > 0:  # waits for second "S" from arduino after cue_duration has been downloaded
                    print(Fore.GREEN + f"Start signal received {datetime.now().strftime('%H%M%S')}")
                    break
                if time.perf_counter() - start > 1:
                    print(Fore.RED + "Start signal timeout")
                    break

            ser.read_all()  # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()  # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            pause_time = 1

            metadata["Platform pause time"] = pause_time
            metadata["Cue duration"] = cue_duration
            metadata["Wait duration"] = wait_duration

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:  # loop that waits for the pressure plate to be activated
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)  # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:
                    state = False
                    wait_complete = False
                    # Select the port to give cue at either from shuffled list or randomly:
                    if number_of_trials != 0:
                        try:
                            port = trial_order[trial_count]
                        except IndexError:
                            port = random.choice(ports_in_use)
                    else:
                        port = random.choice(ports_in_use)

                    ser.write(f"{port+1}".encode())  # Send reward port number to arduino.
                    log.append(Fore.MAGENTA + f"OUT;{timer():0.4f}")  # Add time to log.
                    trial_count += 1

                    if port == 6:
                        cue = "audio"
                        port = 0
                    else:
                        cue = str(port + 1)

                    print(Fore.CYAN + f"Cue given: {cue}")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if not error:
                        if incoming[0] == "R":
                            ser.read_all()  # Clear serial buffer

                        wait_time = int(wait_duration) / 1000

                        while not wait_complete:  # wait for the 'wait_time' amount and check if the mouse is still on the platform
                            weight()
                            if timer() - activation_time > wait_time + 1:
                                print(Fore.RED + "wait time timeout")
                                break
                            if weight() > mouse_weight - mouse_weight_offset and timer() - activation_time > wait_time and timer() - activation_time < wait_time + 1:

                                if not wait_complete:
                                    ser.write("s".encode())
                                    wait_complete = True
                                    log.append(Fore.MAGENTA + f"OUT;{timer():0.4f}")

                                time.sleep(0.01)  # an attempt at making sure no random junk from the arduino makes it into the next bit of code
                                ser.read_all()  # Clear serial buffer

                                while True:  # wait for signal about trial success or failure
                                    time.sleep(0.001)
                                    # Wait for arduino to say that reward has been taken.
                                    weight()  # Call pressure_plate to continue updating scales_data list.
                                    incoming = ser.readline().decode("utf-8").strip()  # Read arduino port number.
                                    if len(incoming) > 1:
                                        if incoming[0] == "C":
                                            ser.read_all()
                                            if incoming[1] == str(port + 1):
                                                print(Fore.GREEN + "Reward taken")
                                                print(Fore.CYAN + f"Trials: {trial_count}")
                                                successes += 1
                                                print(Fore.CYAN + f"Successes: {successes}")
                                                log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")  # Add time to log.
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
                                    if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                                        m_break = True

                                    if m_break:
                                        break

                            if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                                m_break = True

                            if m_break:
                                break

                if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                    m_break = True

                if m_break:
                    break

        # ------------------------ LED catch trial experiment ------------------------#

        if phase == "10":
            print(Fore.CYAN + "LED catch trial task")
            print(Fore.YELLOW + "Use setting 8 on arduino")

            # Get cue duration:
            cue_duration = input("Enter cue duration (ms) (0 = unlimited) (1 = mixed): ").strip()
            # Get catch trial type:
            catch_type = input("Enter catch trial type (w = wait time, l = led brightness): ").strip()
            if catch_type not in ["w", "l"]:
                print(Fore.RED + "Invalid catch trial type")
                catch_type = input("Enter catch trial type (w = wait time, l = led brightness): ").strip()


            if catch_type == "l":
                try:
                    catch_brightness = int(input("Enter led brightness (1-10000): ").strip())
                except ValueError:
                    print(Fore.RED + "Invalid led brightness")
                    catch_brightness = int(input("Enter dimmer led brightness (1-10000): ").strip())

            catch_wait = None
            if catch_type == "w":
                try:
                    catch_wait = int(input("Enter longer wait time (ms): ").strip())/1000
                    catch_brightness = 10000
                except ValueError:
                    print(Fore.RED + "Invalid wait time")
                    catch_wait = float(input("Enter longer wait time (ms): ").strip())/1000

            ports_in_use = []
            ports_in_use = [0, 1, 2, 3, 4, 5]
                    
            metadata["Port"] = [(port + 1) for port in ports_in_use]
            metadata["Catch_trial_type"] = catch_type
            metadata["Catch_brightness"] = catch_brightness
            metadata["Catch_wait"] = catch_wait


            # set up random trial order:
            number_of_ports = len(ports_in_use)
            if number_of_trials != 0:       # If number_of_trials has been set:
                trial_order = []
                for i in range(number_of_trials):             # Generates a random sequence but with equal proportions of port A and port B.
                    trial_order.append(i % number_of_ports)

                random.shuffle(trial_order)

            # Generate catch trial order: (list of 0s and 1s, longer than needed, with 1s spaced out 1 in 5)
            frequency = 5
            length = 1000
            space = 3
            num_ones = length // frequency
            num_zeros = length - num_ones
            catch_sequence = [0] * length # Start with a list of zeros and insert ones with the constraint
            possible_positions = [i for i in range(0, length, space)]       # List of possible positions for ones, initially spaced out to avoid adjacent ones
            one_positions = random.sample(possible_positions, num_ones)     # Randomly choose positions for the 1s
            for pos in one_positions:
                catch_sequence[pos] = 1

            # Startup finished, now waits for start signal from arduino
            print(Fore.CYAN + "Waiting for start signal from arduino.")
            ser.read_all()  # Clear serial buffer
            while True:
                incoming = ser.read().decode()  # Arduino code: " Serial.print('S'); "
                if incoming == "S":
                    break
            time.sleep(0.1)
            ser.read_all()  # Clear serial buffer

            # send arduino cue_duration:
            ser.write(f"{cue_duration}".encode())
            # listen for confirmation:
            while True:
                time.sleep(0.001)
                incoming = ser.readline().decode("utf-8").strip()
                if len(incoming) > 0:  # waits for second "S" from arduino after cue_duration has been downloaded
                    break
            time.sleep(0.1)
            ser.read_all()  # Clear serial buffer

            # send arduino catch_brightness:
            ser.write(f"{catch_brightness}".encode())
            # listen for confirmation:
            while True:
                time.sleep(0.001)
                incoming = ser.readline().decode("utf-8").strip()
                if len(incoming) > 0:  # waits for second "S" from arduino after catch_brightness has been downloaded
                    print(Fore.GREEN + f"Start signal received {datetime.now().strftime('%H%M%S')}")
                    break

            time.sleep(0.1)
            ser.read_all()  # Clear serial buffer

            # Once start signal received, start timer and create filename at beginning of experiment.
            tic = time.perf_counter()  # Start timer. time.perf_counter() gives time since start of program in seconds.

            metadata["Mouse weight threshold"] = mouse_weight - mouse_weight_offset
            # Set wait time for mouse to pause on platform before reward cue given.
            normal_pause_time = 1
            pause_time = 1

            metadata["Platform pause time"] = pause_time
            metadata["Cue duration"] = cue_duration
            metadata["Catch trial type"] = catch_type
            metadata["Catch brightness"] = catch_brightness
            metadata["Catch wait time"] = catch_wait

            metadata["Headers"] = ["message direction (IN/OUT)", "computer time (s)", "confirmation or new message (R/C)", "port (1-6/F)", "success or failure (T/F)"]

            rd.clear_buffer()
            while True:  # loop that waits for the pressure plate to be activated
                if catch_type == 'w':
                    if catch_sequence[trial_count] == 1:
                        pause_time = catch_wait
                    else:
                        pause_time = normal_pause_time
                state, activation_time = pressure_plate(mouse_weight - mouse_weight_offset, pause_time)  # If mouse_weight is above threshold for 0 seconds, returns True.
                if state:
                    state = False
                    wait_complete = False
                    # Select the port to give cue at either from shuffled list or randomly:
                    if number_of_trials != 0:
                        try:
                            port = trial_order[trial_count]
                        except IndexError:
                            port = random.choice(ports_in_use)
                    else:
                        port = random.choice(ports_in_use)
                    catch = catch_sequence[trial_count]

                    ser.write(f"{port+1}{catch}".encode())  # Send reward port number to arduino.
                    log.append(Fore.MAGENTA + f"OUT;{timer():0.4f}")  # Add time to log.
                    time.sleep(0.1)
                    # wait for S signal from arduino:
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
                    time.sleep(0.1)
                    ser.read_all()  # Clear serial buffer

                    trial_count += 1

                    if port == 6:
                        cue = "audio"
                        port = 0
                    else:
                        cue = str(port + 1)

                    print(Fore.CYAN + f"Cue given: {cue}, catch: {'CATCH' if catch == 1 else 'NORMAL'}")
                    receive_time = time.perf_counter()

                    incoming, error = check_port_was_received(ser, receive_time)
                    try:
                        log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};R")
                    except IndexError:
                        pass
                    if not error:
                        if incoming[0] == "R":
                            ser.read_all()  # Clear serial buffer

                            while True:  # wait for signal about trial success or failure
                                time.sleep(0.001)
                                # Wait for arduino to say that reward has been taken.
                                weight()  # Call pressure_plate to continue updating scales_data list.
                                incoming = ser.readline().decode("utf-8").strip()  # Read arduino port number.
                                if len(incoming) > 1:
                                    if incoming[0] == "C":
                                        time.sleep(0.1)
                                        ser.read_all()
                                        if incoming[1] == str(port + 1):
                                            print(Fore.GREEN + "Reward taken")
                                            print(Fore.CYAN + f"Trials: {trial_count}")
                                            successes += 1
                                            print(Fore.CYAN + f"Successes: {successes}")
                                            log.append(Fore.MAGENTA + f"IN;{timer():0.4f};{incoming[0]};{incoming[1]};T")  # Add time to log.
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
                                if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                                    m_break = True

                                if m_break:
                                    break

                    if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                        m_break = True

                    if m_break:
                        break

                if keyboard.is_pressed(exit_key):  # If m is pressed, end program.
                    m_break = True

                if m_break:
                    break


    except Exception as e:
        print(e)
        # also print traceback:
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
            json.dump(metadata, f, indent = 4)
        
        
        # rd.ser.close()
        # rd.__del__()
        ser.close()

        # ------------------------ End program ------------------------#
        print("Program finished")
        # print("Press Esc to end program")
        # while True:
        #     time.sleep(0.001)
        #     if keyboard.is_pressed(exit_key):                           
        #         break

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

def setup_output_directory(main_directory, folder_id=None):
    if folder_id is None:
        folder_id = f"{datetime.now():%y%m%d_%H%M%S}"
    output_path = main_directory / folder_id
    output_path.mkdir(parents=True, exist_ok=True)
    return str(output_path), folder_id

def start_subprocess(command, name):
    print(f"Starting {name}...")
    return subprocess.Popen(command, shell=True)    

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
        # main_output_path, folder_id = setup_output_directory(main_directory, folder_id)
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
        # print(camera_exe)
        tracker_command = [camera_exe, 
                           "--id", mouse_id, 
                           "--date", date_time, 
                           "--path", output_path, 
                           "--rig", str(rig), 
                           "--fps", str(fps), 
                           "--windowWidth", str(window_width), 
                           "--windowHeight", str(window_height)]
        # ]
        # tracker_command = [
        #     "C:\\Behaviour\\Camera\\x64\\Release\\Camera_to_binary.exe",
        #     "--id", "test1",
        #     "--date", "241202_150537",
        #     "--path", "D:\\test_output\\241202_150536\\241202_150537_test1",
        #     "--rig", "3",
        #     "--fps", "30",
        #     "--windowWidth", "640",
        #     "--windowHeight", "512"
        # ]

        # tracker_command = "C:\\Behaviour\\Camera\\x64\\Release\\Camera_to_binary.exe --id test1 --date 241202_150537 --path D:\\test_output\\241202_150536\\241202_150537_test1 --rig 3 --fps 30 --windowWidth 640 --windowHeight 512"
        # print(f"'{tracker_command}'")
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