"""
General utility functions.
"""

import subprocess

def start_subprocess(command, name):
    """
    Start a subprocess and return the process object.
    
    Args:
        command (list or str): Command to execute
        name (str): Name for logging purposes
        
    Returns:
        subprocess.Popen: Process object
    """
    print(f"Starting {name}...")
    return subprocess.Popen(command, shell=True)

def get_cam_serial_number(rig):
    """
    Get camera serial number based on rig number.
    
    Args:
        rig (int): Rig number
        
    Returns:
        str: Camera serial number
        
    Raises:
        ValueError: If rig number is invalid
    """
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