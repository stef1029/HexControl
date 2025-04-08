"""
Arduino communication utilities.
"""

import time
import serial
from colorama import Fore

def get_rig_port(rig):
    """
    Map rig number to serial port.
    
    Args:
        rig (int): Rig number
        
    Returns:
        str: Serial port name
    
    Raises:
        ValueError: If rig number is invalid
    """
    rig_ports = {
        None: "COM4",
        1: "COM4",
        2: "COM11",
        3: "COM39",
        4: "COM6"
    }
    
    if rig not in rig_ports:
        raise ValueError("Invalid rig number.")
    
    return rig_ports[rig]

def setup_serial_connection(port):
    """
    Setup and return a serial connection to the Arduino.
    
    Args:
        port (str): Serial port name
        
    Returns:
        serial.Serial: Configured serial connection
        
    Raises:
        serial.SerialException: If connection fails
    """
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
            time.sleep(1)

def check_port_was_received(ser, receive_time, trial_timeout=11):
    """
    Check if the port command was received by the Arduino.
    
    Args:
        ser (serial.Serial): Serial connection
        receive_time (float): Time when command was sent
        trial_timeout (int): Timeout in seconds
        
    Returns:
        tuple: (incoming message, error flag)
    """
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
            ser.read_all()  # Clear serial buffer
            error = True
            break      
    return incoming, error

def setup_arduino_case(ser, case_number):
    """
    Send case selection command to Arduino and wait for acknowledgment.
    
    Args:
        ser (serial.Serial): Serial connection
        case_number (int): Case number to set
        
    Returns:
        bool: True if acknowledgment received, False otherwise
    """
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
    """
    Wait for start signal from Arduino.
    
    Args:
        ser (serial.Serial): Serial connection
        
    Returns:
        bool: True if start signal received, False otherwise
    """
    print(Fore.CYAN + "Waiting for start signal from arduino.")
    ser.read_all()  # Clear serial buffer
    start_timeout = time.perf_counter() + 10  # 10 second timeout
    while time.perf_counter() < start_timeout:
        incoming = ser.read().decode()
        if incoming == "S":
            print(Fore.GREEN + f"Start signal received {time.strftime('%H%M%S')}")
            ser.read_all()  # Clear serial buffer
            return True
        time.sleep(0.1)
    
    print(Fore.RED + "Error: No start signal received from Arduino")
    return False