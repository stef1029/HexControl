"""
Test script for DAQ connection.

This script tests the DAQ serial listener independently of the GUI.
It starts the DAQ subprocess, waits for connection, and shuts down cleanly.

Usage:
    python -m tests.test_daq_connection
    
Or run directly:
    python tests/test_daq_connection.py
"""

import os
import subprocess
import sys
import time
import threading
import queue
from datetime import datetime
from pathlib import Path

# Configuration - adjust these for your setup
RIG_NUMBER = "1"  # Which rig to test (1-4)
DAQ_BOARD_TAG = "rig_1_daq"  # Board tag in board_registry.json
MOUSE_ID = "test_daq"
CONNECTION_TIMEOUT = 30  # seconds
RUN_DURATION = 10  # seconds to run after connection before stopping

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DAQ_SCRIPT = PROJECT_DIR / "daq" / "serial_listen_mega_fast.py"
BOARD_REGISTRY = PROJECT_DIR / "config" / "board_registry.json"

# Use the same Python as running this script, or specify your conda env
PYTHON_PATH = sys.executable


def output_reader(pipe, output_queue):
    """Read lines from pipe and put them in queue (runs in thread)."""
    try:
        for line in iter(pipe.readline, ''):
            output_queue.put(line.rstrip())
        pipe.close()
    except:
        pass


def main():
    print("=" * 60)
    print("DAQ CONNECTION TEST")
    print("=" * 60)
    print(f"Rig number: {RIG_NUMBER}")
    print(f"DAQ script: {DAQ_SCRIPT}")
    print(f"Python: {PYTHON_PATH}")
    print("-" * 60)
    
    # Check paths exist
    if not DAQ_SCRIPT.exists():
        print(f"ERROR: DAQ script not found: {DAQ_SCRIPT}")
        return 1
    
    # Create temp output folder
    date_time = datetime.now().strftime("%y%m%d_%H%M%S")
    output_folder = Path(f"D:/behaviour_data/test_{date_time}_{MOUSE_ID}")
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {output_folder}")
    
    # Signal file path
    signal_file = output_folder / f"rig_{RIG_NUMBER}_arduino_connected.signal"
    stop_signal_file = output_folder / f"rig_{RIG_NUMBER}_camera_finished.signal"
    print(f"Connection signal: {signal_file}")
    print(f"Stop signal: {stop_signal_file}")
    print("-" * 60)
    
    # Build command
    command = [
        PYTHON_PATH,
        str(DAQ_SCRIPT),
        "--id", MOUSE_ID,
        "--date", date_time,
        "--path", str(output_folder),
        "--rig", RIG_NUMBER,
        "--board-tag", DAQ_BOARD_TAG,
        "--registry", str(BOARD_REGISTRY),
    ]
    
    print("Starting DAQ process...")
    print(f"Command: {' '.join(command)}")
    print("-" * 60)
    
    # Start subprocess
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    
    # Start thread to read output without blocking
    output_queue = queue.Queue()
    reader_thread = threading.Thread(
        target=output_reader, 
        args=(process.stdout, output_queue),
        daemon=True
    )
    reader_thread.start()
    
    print(f"DAQ process started (PID: {process.pid})")
    print("-" * 60)
    print("DAQ OUTPUT:")
    print("-" * 60)
    
    def print_queued_output():
        """Print any output that's been queued up."""
        while True:
            try:
                line = output_queue.get_nowait()
                print(f"  [DAQ] {line}")
            except queue.Empty:
                break
    
    # Wait for connection signal
    start_time = time.time()
    connected = False
    
    while time.time() - start_time < CONNECTION_TIMEOUT:
        print_queued_output()
        
        # Check if signal file exists
        if signal_file.exists():
            elapsed = time.time() - start_time
            print("-" * 60)
            print(f"CONNECTION SUCCESSFUL! ({elapsed:.1f}s)")
            connected = True
            break
        
        # Check if process died
        if process.poll() is not None:
            print_queued_output()
            print("-" * 60)
            print(f"ERROR: DAQ process terminated (exit code: {process.returncode})")
            return 1
        
        time.sleep(0.2)
    
    if not connected:
        print("-" * 60)
        print(f"TIMEOUT: No connection after {CONNECTION_TIMEOUT}s")
        print("Killing process...")
        process.kill()
        return 1
    
    # Let it run for a bit
    print(f"Running for {RUN_DURATION} seconds...")
    print("-" * 60)
    
    run_start = time.time()
    while time.time() - run_start < RUN_DURATION:
        print_queued_output()
        
        # Check if process died
        if process.poll() is not None:
            print(f"DAQ process ended early (exit code: {process.returncode})")
            break
        
        time.sleep(0.5)
    
    print_queued_output()
    
    # Stop by creating the stop signal file (simulating camera finish)
    print("-" * 60)
    print("Creating stop signal file...")
    stop_signal_file.write_text(f"Test stop at {datetime.now()}")
    
    # Wait for graceful shutdown
    print("Waiting for DAQ to finish (max 15s)...")
    try:
        process.wait(timeout=15)
        print(f"DAQ process exited gracefully (code: {process.returncode})")
    except subprocess.TimeoutExpired:
        print("DAQ didn't stop gracefully, killing...")
        process.kill()
        process.wait()
    
    # Print any remaining output
    time.sleep(0.5)
    print_queued_output()
    
    print("-" * 60)
    print("TEST COMPLETE")
    print(f"Check output folder: {output_folder}")
    
    # List output files
    print("\nOutput files:")
    for f in output_folder.iterdir():
        size = f.stat().st_size if f.is_file() else "-"
        print(f"  {f.name} ({size} bytes)" if f.is_file() else f"  {f.name}/")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
