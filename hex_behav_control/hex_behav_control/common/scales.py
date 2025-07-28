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
    Test scales by printing weight readings with timing diagnostics until user presses 'q'.
    
    Args:
        rd (Scales): Scales object
    """
    if rd is None:
        print("Error: Cannot test scales - Scales object (rd) is None!")
        return
        
    print("Scales test with diagnostics. Press Q to exit")
    
    last_message_time = None
    last_print_time = 0
    print_interval = 0.1  # Print every 100ms
    slow_call_threshold = 0.05  # Flag calls slower than 50ms
    
    try:
        while True:
            current_time = time.time()
            
            # Check if it's time to update the display
            if current_time - last_print_time >= print_interval:
                # Time the scales reading operation
                start_time = time.perf_counter()
                reading = weight(rd, test=True)
                end_time = time.perf_counter()
                
                call_duration = end_time - start_time
                
                # Calculate time since last message
                if last_message_time is not None:
                    time_since_last = current_time - last_message_time
                    time_display = f"{time_since_last:.2f}s"
                else:
                    time_display = "N/A"
                
                # Update timing variables
                last_message_time = current_time
                last_print_time = current_time
                
                # Display reading with diagnostics
                print(UP, end=CLEAR)
                base_info = f"Reading: {reading} | Time since last: {time_display}"
                
                # Add warning for slow calls
                if call_duration > slow_call_threshold:
                    print(f"{base_info} | ⚠️  SLOW CALL: {call_duration:.3f}s")
                else:
                    print(f"{base_info} | Call time: {call_duration:.3f}s")
            
            if keyboard.is_pressed('q'):
                print(UP, end=CLEAR)
                print("Scales test completed.")
                break
                
    except Exception as e:
        print(f"Error during scales test: {e}")

# def test_scales(rd):
#     """
#     Test scales by printing weight readings and time since last message until user presses 'q'.
#     Updates display based on timer intervals rather than sleep delays.
    
#     Args:
#         rd (Scales): Scales object
#     """
#     if rd is None:
#         print("Error: Cannot test scales - Scales object (rd) is None!")
#         return
        
#     print("Scales test. Press Q to exit")
    
#     last_message_time = None
#     last_print_time = 0
#     print_interval = 0.1  # Print every 100ms
    
#     try:
#         while True:
#             current_time = time.time()
            
#             # Check if it's time to update the display
#             if current_time - last_print_time >= print_interval:
#                 reading = weight(rd, test=True)
                
#                 # Calculate time since last message
#                 if last_message_time is not None:
#                     time_since_last = current_time - last_message_time
#                     time_display = f"{time_since_last:.2f}s"
#                 else:
#                     time_display = "N/A"
                
#                 # Update last message time
#                 last_message_time = current_time
#                 last_print_time = current_time
                
#                 print(UP, end=CLEAR)
#                 print(f"Current reading: {reading} | Time since last: {time_display}")
            
#             if keyboard.is_pressed('q'):
#                 print(UP, end=CLEAR)
#                 print("Scales test completed.")
#                 break
                
#     except Exception as e:
#         print(f"Error during scales test: {e}")