from datetime import datetime
from pathlib import Path
import os
import subprocess
import time
import json

# ============= USER-EDITABLE PARAMETERS =============
# Edit these values before running the script

# Config path - location of the global configuration file
CONFIG_PATH = r"C:\dev\projects\config.json"

# Rigs to use (comma-separated)
RIGS_IN_USE = "1,2"

# Output directory where data will be saved
OUTPUT_FOLDER = r"c:\test_output"

# Mouse IDs for each rig (same order as rigs)
# MICE = ["mtaq14-1i", "mtaq14-1j"]
MICE = ["mtaq11-3b", "mtaq13-3a"]

# Mouse weights (in grams) for each rig (same order as rigs)
WEIGHTS = [15, 15]

# Optional: Saved configuration names to load (same order as rigs)
# Use empty string "" or None if no config should be loaded for a particular rig
LOAD_CONFIGS = [None, None]

# Optional: Phases to run (same order as rigs)
# If not specified, the user will be prompted for each rig
PHASES = [None, None]

# Common parameters for all rigs
FPS = 30
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 1024

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
        self.load_configs = LOAD_CONFIGS
        self.phases = PHASES
        
        # Ensure all lists have the same length
        self.validate_inputs()
        
        # Start the session
        self.start_recording()
        self.start_sk()
        
    def validate_inputs(self):
        """Ensure all input lists have appropriate lengths."""
        num_rigs = len(self.rigs_in_use)
        
        # Check and adjust mice list
        if len(self.mice) < num_rigs:
            print(f"Warning: Not enough mouse IDs specified. Using 'test' for remaining rigs.")
            self.mice.extend(["test"] * (num_rigs - len(self.mice)))
        elif len(self.mice) > num_rigs:
            # print(f"Warning: More mouse IDs than rigs. Using only the first {num_rigs}.")
            self.mice = self.mice[:num_rigs]
            
        # Check and adjust weights list
        if len(self.weights) < num_rigs:
            print(f"Warning: Not enough weights specified. Using 20.0g for remaining rigs.")
            self.weights.extend([20.0] * (num_rigs - len(self.weights)))
        elif len(self.weights) > num_rigs:
            # print(f"Warning: More weights than rigs. Using only the first {num_rigs}.")
            self.weights = self.weights[:num_rigs]
            
        # Check and adjust configs list
        if len(self.load_configs) < num_rigs:
            self.load_configs.extend([None] * (num_rigs - len(self.load_configs)))
        elif len(self.load_configs) > num_rigs:
            self.load_configs = self.load_configs[:num_rigs]
            
        # Check and adjust phases list
        if len(self.phases) < num_rigs:
            self.phases.extend([None] * (num_rigs - len(self.phases)))
        elif len(self.phases) > num_rigs:
            self.phases = self.phases[:num_rigs]
            
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
                # print(f"Started timer script")
            except Exception as e:
                print(f"Warning: Could not start timer script: {e}")

        print(f"Starting {len(self.rigs_in_use)} rig(s)...")

        for i, rig in enumerate(self.rigs_in_use):
            # Get parameters for this rig
            mouse = self.mice[i]
            weight = self.weights[i]
            load_config = self.load_configs[i] if i < len(self.load_configs) else None
            phase = self.phases[i] if i < len(self.phases) else None
            
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
            
            # Add load_config parameter if specified
            if load_config and load_config.lower() != "none":
                command += f'--load_config "{load_config}" '
                
            # Add phase parameter if specified
            if phase and phase.lower() != "none":
                command += f'--phase "{phase}" '

            # Define the command to open a new terminal with a custom title
            terminal_title = f"RIG {rig} - {mouse}"
            terminal_command = (
                f'start "{terminal_title}" cmd /c "title {terminal_title} && '
                f'cd /d "{self.code_base_path}" && '  # Change to code directory first
                f'{command}"'
            )
            
            # Print info
            print(f"Starting rig {rig} with mouse {mouse} (weight: {weight}g)")
            if load_config:
                print(f"  Loading configuration: {load_config}")
            if phase:
                print(f"  Running phase: {phase}")
                
            # Execute the command
            subprocess.Popen(terminal_command, shell=True)
            
            # Brief pause between starting each rig
            time.sleep(2)
            
        print(f"All rigs started. Data will be saved to {self.output_path}")

def main():
    BeginSession()

if __name__ == '__main__':
    main()