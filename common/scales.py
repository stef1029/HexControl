"""
Scale reading utilities.

This module directly imports the original Scales class and adds utility functions
for working with it in the new modular structure.
"""

import time
import keyboard

# Import the exact Scales class from the original module
from hex_behav_control.peripherals.read import Scales

UP = "\033[1A"
CLEAR = '\x1b[2K'

# Global variable to track most recent scale value
most_recent_scales_value = 0

def weight(rd, timer=None, scales_data=None, test=False):
    """
    Get weight from scales.
    
    Args:
        rd (Scales): Scales object
        timer (function, optional): Timer function for timestamps
        scales_data (list, optional): List to store scale readings
        test (bool): Whether this is a test reading
        
    Returns:
        float: Current weight
    """
    global most_recent_scales_value
    
    if rd is None:
        print("Error: Scales object (rd) is None!")
        return most_recent_scales_value
    
    # Returns weight from scales. If no new data, returns most recent value.
    # Also adds scales data to scales_data list.
    try:
        raw = rd.get_mass()
        
        if 'ID' in raw:
            id = raw['ID']
            data = raw['value']
            if data is not None:
                most_recent_scales_value = data
                if not test and timer and scales_data is not None:
                    scales_data.append([timer(), data, id])
                return data
            else:
                return most_recent_scales_value
                
        elif 'value' in raw:
            data = raw['value']
            if data is not None:
                most_recent_scales_value = data
                if not test and timer and scales_data is not None:
                    scales_data.append([timer(), data])
                return data
            else:
                return most_recent_scales_value
    except Exception as e:
        print(f"Error reading scales: {e}")
        return most_recent_scales_value
    
    return most_recent_scales_value

def pressure_plate(mouse_weight, wait_time, rd, timer=None, scales_data=None):
    """
    Check if weight is consistently above threshold.
    
    Args:
        mouse_weight (float): Weight threshold
        wait_time (float): Time to wait above threshold
        rd (Scales): Scales object
        timer (function, optional): Timer function
        scales_data (list, optional): List to store scale readings
        
    Returns:
        tuple: (state, activation_time)
    """
    # Make sure scales object exists
    if rd is None:
        print("Error: Scales object (rd) is None in pressure_plate function!")
        current_time = timer() if timer else 0
        return (False, current_time)
    
    # Returns True if mouse_weight consistently above threshold for wait_time seconds.
    # Checks enters a loop and breaks immediately if weight is below threshold. 
    # If weight is above threshold, enters another loop which returns True if weight above threshold for wait_time seconds.
    # Breaks loops if weight goes below threshold too quickly.
    scales_tic = time.perf_counter()
    
    def scales_timer():
        scales_toc = time.perf_counter()
        return scales_toc - scales_tic
    
    while True:
        reading = weight(rd, timer, scales_data)
        if reading > mouse_weight:
            while True:
                if weight(rd, timer, scales_data) < mouse_weight:
                    current_time = timer() if timer else 0
                    return (False, current_time)
                    
                if scales_timer() > wait_time:
                    current_time = timer() if timer else 0
                    return (True, current_time)
        break
        
    current_time = timer() if timer else 0
    return (False, current_time)

def test_scales(rd):
    """
    Test scales by printing weight readings until user presses 'q'.
    
    Args:
        rd (Scales): Scales object
    """
    if rd is None:
        print("Error: Cannot test scales - Scales object (rd) is None!")
        return
        
    print("Scales test. Press Q to exit")
    # print("Current reading: ", end="")
    
    try:
        while True:
            reading = weight(rd, test=True)
            print(UP, end=CLEAR)
            print(f"Current reading: {reading}")
            
            if keyboard.is_pressed('q'):
                print(UP, end=CLEAR)
                print("Scales test completed.")
                break
            
            time.sleep(0.1)
    except Exception as e:
        print(f"Error during scales test: {e}")