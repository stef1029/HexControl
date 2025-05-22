from datetime import datetime
from pathlib import Path
import os
import subprocess
import time
import json

config_path = r"C:\dev\projects\hex_behav_config.json"
with open(config_path, "r") as file:
    config = json.load(file)

class BeginSession():

    def __init__(self):
        # self.rigs_in_use = input("Enter the rigs in use (eg: 1, 2): ")
        self.rigs_in_use = "4"
        self.rigs_in_use = [int(rig) for rig in self.rigs_in_use.split(",")]

        # base folder where code is found:
        # self.code_base_path = Path(r"C:\Users\Tripodi Group\October_behaviour_code\Sendkey-multi")
        self.code_base_path = Path(config.get("SENDKEY_FOLDER"))
        
        # Create the output directory:
        self.folder = Path(r"D:\250317_New_rigs_test")
        # self.folder = Path(r"D:\test_output")

        # self.folder = Path(r"E:\Lynn_Jan_MD_Excite")
        # self.folder = Path(r"E:\Dan_December_cohort")
        self.folder = Path(r"E:\Pitx2_Ephys")

        self.start_recording()

        self.start_sk()

    def start_recording(self):


        self.date_time = f"{datetime.now():%y%m%d_%H%M%S}"
        self.output_path = self.folder / self.date_time 
        os.mkdir(self.output_path)


    def start_sk(self):
        """
        Starts the sk.py script
        """
        weights = [15, 15]

        # mice = ["wtjp280-4a", "wtjp280-4b"]
        # mice = ["wtjp271-5b", "wtjp271-5c"]
        # mice = ["wtjp271-5d", "wtjp280-4f"]
        # mice = ["wtjp271-5c"]

        mice = ["mtaq14-1i", "mtaq14-1j"]
        # mice = ["mtaq11-3b", "mtaq13-3a"]

        # mice = ["test1", "test2"]

        FPS = 30
        # window_width = 640
        # window_height = 512
        window_width = 1280
        window_height = 1024

        python_exe = config.get("PYTHON_PATH")
        timer_path = config.get("TIMER_SCRIPT")

        timer = subprocess.Popen([python_exe, timer_path], shell=False)

        for i, rig in enumerate(self.rigs_in_use):
            # Define the paths and the command
            mouse = mice[i]
            weight = weights[i]
            sk = self.code_base_path / r"sk4.py"
            
            # Construct the command with the new arguments
            command = (
                f'"{python_exe}" "{sk}" '
                f'--rig {rig} '
                f'--path "{self.output_path}" '
                f'--mouse "{mouse}" '
                f'--weight {weight} '
                f'--fps {FPS} '
                f'--window_width {window_width} '
                f'--window_height {window_height} '
                f'--config_json "{config_path}" '
            )

            # Define the command to open a new terminal with a custom title, set window size, and run the tracker command
            terminal_title = f"RIG {rig} - {mouse}"
            terminal_command = (
                f'start "{terminal_title}" cmd /c "title {terminal_title} && '
                f'{command}"'
            )
            # Execute the command
            subprocess.Popen(terminal_command, shell=True)

            


def main():
    BeginSession()

if __name__ == '__main__':
    main()