from datetime import datetime
from pathlib import Path
import os
import subprocess
import time
import json

# ============= USER-EDITABLE PARAMETERS =============
# Edit these values before running the script

# Config path - location of the global configuration file
# CONFIG_PATH = r"C:\dev\projects\config.json" # large behaviour room
CONFIG_PATH = r"C:\dev\projects\hex_behav_config.json" # small behaviour room


# # Rigs to use (comma-separated)
RIGS_IN_USE = "3"

# Output directory where data will be saved
OUTPUT_FOLDER = r"D:\Pitx2_Chemogenetics"

# Mouse IDs for each rig (same order as rigs)

# MICE = ["mtao107-2a", "mtao106-3a"]
# MICE = ["mtao101-3c", "mtao101-3b"] 

# MICE = ["mtao102-3e", "mtao102-3c"] # *
# MICE = ["mtao106-3b", "mtao101-3g"]# *1
# MICE = ["mtao106-1e", "mtao108-3e"] #*1

# MICE = ["mtao106-3a"]
MICE = ["mtao107-2a"]
# MICE = ["mtao101-3b"]
# MICE = ["mtao101-3c"]
# MICE = ["mtao108-3e"]
# MICE = ["mtao101-3g"]

# MICE = ["mtao107-2a"]

# Pairs for intensive training
# MICE = ["mtao106-3b", "mtao106-1e"]


# Mouse weights (in grams) for each rig (same order as rigs)
WEIGHTS = [12]

# Common parameters for all rigs
FPS = 30
# WINDOW_WIDTH = 1280
# WINDOW_HEIGHT = 1024

WINDOW_WIDTH = 640
WINDOW_HEIGHT = 512

# ======================================================

class BeginSession():
    def __init__(self):
        # Load the configuration file
        with open(CONFIG_PATH, "r") as file:
            self.config = json.load(file)
        
        # Process rig numbers
        self.rigs_in_use = [int(rig) for rig in RIGS_IN_USE.split(",")]
        
        # Base folder where code is found
        self.code_base_path = Path(self.config.get("SENDKEY_FOLDER"))
        
        # Output folder
        self.folder = Path(OUTPUT_FOLDER)
        
        # Get mouse IDs and weights
        self.mice = MICE
        self.weights = WEIGHTS
        
        # Ensure all lists have the same length
        self.validate_inputs()
        
        # Start the session
        self.start_recording()
        self.start_sk()
        
    def validate_inputs(self):
        """Ensure all input lists have appropriate lengths."""
        num_rigs = len(self.rigs_in_use)
        
        # Default values for padding lists
        defaults = {
            'mice': 'test',
            'weights': 20.0,
        }
        
        # List of attributes to validate
        attributes = ['mice', 'weights']
        
        for attr in attributes:
            current_list = getattr(self, attr)
            
            if len(current_list) < num_rigs:
                # Pad with default values
                default_value = defaults[attr]
                padding_needed = num_rigs - len(current_list)
                current_list.extend([default_value] * padding_needed)
                print(f"Warning: Not enough {attr} specified. Using default for remaining rigs.")
                    
            elif len(current_list) > num_rigs:
                # Truncate to required length
                setattr(self, attr, current_list[:num_rigs])
            
    def start_recording(self):
        """Create output directory with timestamp."""
        self.date_time = f"{datetime.now():%y%m%d_%H%M%S}"
        self.output_path = self.folder / self.date_time 
        os.makedirs(self.output_path, exist_ok=True)
        
        print(f"Created output directory: {self.output_path}")

    def start_sk(self):
        """Start the behavior script for each rig."""
        # Get paths from config
        python_exe = self.config.get("PYTHON_PATH")
        timer_path = self.config.get("TIMER_SCRIPT")

        # Start timer script if available
        if timer_path:
            try:
                timer = subprocess.Popen([python_exe, timer_path], shell=False)
            except Exception as e:
                print(f"Warning: Could not start timer script: {e}")

        print(f"Starting {len(self.rigs_in_use)} rig(s)...")

        for i, rig in enumerate(self.rigs_in_use):
            # Get parameters for this rig
            mouse = self.mice[i]
            weight = self.weights[i]
            
            # Path to main.py in the new modular structure
            main_script = self.code_base_path / "main.py"
            
            # Construct the command with the arguments
            command = (
                f'"{python_exe}" "{main_script}" '
                f'--rig {rig} '
                f'--path "{self.output_path}" '
                f'--mouse "{mouse}" '
                f'--weight {weight} '
                f'--fps {FPS} '
                f'--window_width {WINDOW_WIDTH} '
                f'--window_height {WINDOW_HEIGHT} '
                f'--config_json "{CONFIG_PATH}" '
            )
            

            # Define the command to open a new terminal with a custom title
            terminal_title = f"RIG {rig} - {mouse}"
            terminal_command = (
                f'start "{terminal_title}" cmd /c "title {terminal_title} && '
                f'cd /d "{self.code_base_path}" && '  # Change to code directory first
                f'{command}"'
            )
            
            # Print info
            print(f"Starting rig {rig} with mouse {mouse} (weight: {weight}g)")
                
            # Execute the command
            subprocess.Popen(terminal_command, shell=True)
            
            # Brief pause between starting each rig
            time.sleep(2)
            
        print(f"All rigs started. Data will be saved to {self.output_path}")

def main():
    BeginSession()

if __name__ == '__main__':
    main()