"""
Test script for Camera.

This script tests the camera executable independently of the GUI.
It starts the camera subprocess, lets it run for a duration, and shuts down cleanly.

All camera output goes directly to this console.

Usage:
    python -m tests.test_camera
    
Or run directly:
    python tests/test_camera.py
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Configuration - adjust these for your setup
CAMERA_SERIAL = "22181614"  # Rig 1 camera serial number
MOUSE_ID = "test_camera"
RUN_DURATION = 10  # seconds to run before stopping

# Camera settings
FPS = 30
WINDOW_WIDTH = 640
WINDOW_HEIGHT = 512

# Paths - adjust CAMERA_EXECUTABLE to your setup
CAMERA_EXECUTABLE = Path(r"C:\dev\projects\behaviour_camera\out\install\vs-release\bin\behaviour_camera.exe")
OUTPUT_BASE = Path(r"D:\behaviour_data")


def main():
    print("=" * 60)
    print("CAMERA TEST")
    print("=" * 60)
    print(f"Camera serial: {CAMERA_SERIAL}")
    print(f"Camera executable: {CAMERA_EXECUTABLE}")
    print(f"FPS: {FPS}, Window: {WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    print("-" * 60)
    
    # Check executable exists
    if not CAMERA_EXECUTABLE.exists():
        print(f"ERROR: Camera executable not found: {CAMERA_EXECUTABLE}")
        print("\nPlease update CAMERA_EXECUTABLE path in this script.")
        return 1
    
    # Create temp output folder
    date_time = datetime.now().strftime("%y%m%d_%H%M%S")
    output_folder = OUTPUT_BASE / f"test_{date_time}_{MOUSE_ID}"
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {output_folder}")
    print("-" * 60)
    
    # Build command
    command = [
        str(CAMERA_EXECUTABLE),
        "--id", MOUSE_ID,
        "--date", date_time,
        "--path", str(output_folder),
        "--serial_number", CAMERA_SERIAL,
        "--fps", str(FPS),
        "--windowWidth", str(WINDOW_WIDTH),
        "--windowHeight", str(WINDOW_HEIGHT),
    ]
    
    print("Starting camera process...")
    print(f"Command: {' '.join(command)}")
    print(f"Working directory: {CAMERA_EXECUTABLE.parent}")
    print("-" * 60)
    print("CAMERA OUTPUT (direct to console):")
    print("-" * 60)
    
    # Start subprocess from the camera's directory so it can find DLLs
    try:
        process = subprocess.Popen(command, cwd=CAMERA_EXECUTABLE.parent)
    except Exception as e:
        print(f"ERROR: Failed to start camera: {e}")
        return 1
    
    print(f"Camera process started (PID: {process.pid})")
    print(f"Running for {RUN_DURATION} seconds...")
    print("(Camera window should appear)")
    print("-" * 60)
    
    # Let it run for the duration
    run_start = time.time()
    while time.time() - run_start < RUN_DURATION:
        # Check if process died
        if process.poll() is not None:
            print("-" * 60)
            print(f"Camera process ended early (exit code: {process.returncode})")
            break
        
        time.sleep(0.5)
    
    # Stop the camera
    if process.poll() is None:
        print("-" * 60)
        print("Stopping camera...")
        
        # Try graceful termination first
        process.terminate()
        
        try:
            process.wait(timeout=5)
            print(f"Camera stopped gracefully (exit code: {process.returncode})")
        except subprocess.TimeoutExpired:
            print("Camera didn't stop gracefully, killing...")
            process.kill()
            process.wait()
            print(f"Camera killed (exit code: {process.returncode})")
    
    print("-" * 60)
    print("TEST COMPLETE")
    print(f"Check output folder: {output_folder}")
    
    # List output files
    print("\nOutput files:")
    try:
        for f in output_folder.iterdir():
            if f.is_file():
                size = f.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024*1024):.1f} MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} bytes"
                print(f"  {f.name} ({size_str})")
            else:
                print(f"  {f.name}/")
    except Exception as e:
        print(f"  Error listing files: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
