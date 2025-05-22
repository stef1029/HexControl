import open_ephys.control as control
import requests
import time
import subprocess
import json
from pathlib import Path
import keyboard
import argparse

exit_key = 'esc'

# Path to the Open Ephys executable
open_ephys_path = "C:\\Program Files\\Open Ephys\\open-ephys.exe"

base_url = "http://localhost:37497/api"

default_config = r"C:\Users\Tripodi Group\Behaviour_code_2\Sendkey-multi\Scripts\default_OE_config"

class Recording():
    def __init__(self, path, rigs):
        # Get paths and folder names:
        self.session_directory = Path(path)
        self.folder_name = self.session_directory.stem
        self.recording_folder_name = f"{self.folder_name}_OEAB_recording"

        self.num_rigs = rigs
        self.expected_signals = self.num_rigs * 2  # Two signals per rig (camera and DAQ)

        # Start OE GUI if not already running. If already open, raise error:
        if not self.is_gui_running():
            subprocess.Popen(open_ephys_path)
            while not self.is_gui_running():
                time.sleep(0.1)
        else:
            raise Exception("Open Ephys GUI is already running")
        
        # Set up the recording:
        self.setup_recording()
        self.record()
        
    # Function to check if Open Ephys GUI is already running
    def is_gui_running(self):
        try:
            response = requests.get(f"{base_url}/status")
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            return False
        
    def setup_recording(self):
        self.gui = control.OpenEphysHTTPServer()
        self.gui.load(default_config)

        # Set the folder name
        self.gui.set_record_path(120, str(self.session_directory))  # I believe this needs to be changed if switching fpga boards
        self.gui.set_base_text(self.recording_folder_name)
    
    def record(self):
        self.gui.record()

        # Create the signal file to indicate that recording has started
        self.create_signal_file()

        while True:
            if keyboard.is_pressed(exit_key):
                self.check_all_signals_received()
                self.gui.idle()
                break
        
        self.gui.quit()

    def create_signal_file(self):
        signal_file = self.session_directory / "recording_started.signal"
        signal_file.touch()

    def check_all_signals_received(self):
        while True:
            signal_files = list(self.session_directory.glob("*.signal"))
            if len(signal_files) >= self.expected_signals:
                for signal_file in signal_files:
                    signal_file.unlink()  # Delete the signal files
                return True

def main():
    parser = argparse.ArgumentParser(description="Run the OEAB GUI")
    parser.add_argument("--path", type=str, help="Path to the recording folder")
    parser.add_argument("--rigs", type=str, help="Number of rigs in use")
    args = parser.parse_args()

    try:
        recording = Recording(args.path, int(args.rigs))
    except Exception as e:
        # save exception to txt file:
        with open("OEAB_error_log.txt", "w") as f:
            f.write(str(e))

if __name__ == "__main__":
    main()
