import subprocess
import json
from datetime import datetime
from pathlib import Path


def load_config(config_path):
    with open(config_path, "r") as f:
        return json.load(f)
    
def start_subprocess(command, name):
    print(f"Starting {name}...")
    return subprocess.Popen(command, shell=True)

def setup_output_directory(main_directory, folder_id=None):
    if folder_id is None:
        folder_id = f"{datetime.now():%y%m%d_%H%M%S}"
    output_path = main_directory / folder_id
    output_path.mkdir(parents=True, exist_ok=True)
    return str(output_path), folder_id

config = load_config(r"C:\Behaviour\config.json")

serial_listen_script = config.get("SERIAL_LISTEN")
camera_exe = config.get("BEHAVIOUR_CAMERA")

mouse_id = "test"
rig = 2
window_width = 640
window_height = 512

main_directory = Path(r"D:\2407_July_WT_output")

output_path, folder_id = setup_output_directory(main_directory)

fps = 30

# Start camera tracking
tracker_command = [
    camera_exe, "--id", mouse_id, "--date", folder_id, "--path", output_path, "--rig", str(rig),
    "--fps", str(fps), "--windowWidth", str(window_width), "--windowHeight", str(window_height)
]
p0 = start_subprocess(tracker_command, "Camera Script")