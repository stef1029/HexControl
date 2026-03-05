"""
Scales Server-Client System Test
================================

Tests the scales system using the server-client architecture (as used by the main GUI):
1. Starts the ScalesLink server subprocess
2. Connects via ScalesClient and reads weights
3. Shuts down the server gracefully
4. Verifies the saved CSV data

All configuration (scales board name, COM port resolution) is loaded
automatically from rigs.yaml and the board registry.

Usage:
    Edit the configuration section below, then run:
        python tests/test_scales.py
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ===========================================================================
# CONFIGURATION — edit these values for your setup
# ===========================================================================
RIG_NUMBER = 4
CONFIG_PATH = Path(r"C:\Dev\projects\rigs_config.yaml")      # Path to rigs.yaml
BOARD_REGISTRY_PATH = Path(r"C:\Dev\projects\board_registry.json")  # Path to board registry
TEST_DURATION = 10                                    # Seconds to read weights
TEST_SAVE_PATH = Path("D:/behaviour_data/test_output")
# ===========================================================================

# ---------------------------------------------------------------------------
# Ensure the behaviour_rig_system root is on sys.path so we can import
# core.board_registry and the ScalesLink package.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent                     # behaviour_rig_system/
_HEX_BEHAV_CONTROL = _PROJECT_DIR.parent              # hex_behav_control/
_SCALESLINK_SRC = _HEX_BEHAV_CONTROL / "ScalesLink" / "src"  # ScalesLink/src/

for _p in (_PROJECT_DIR, _SCALESLINK_SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import yaml  # type: ignore
from core.board_registry import BoardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_rig_entry(config_path: Path, rig_number: int) -> dict:
    """
    Load the rig entry for *rig_number* from *config_path* (rigs.yaml).

    Returns the rig dict (with keys like ``scales``, ``board_name``, etc.)
    Raises SystemExit if the file or rig entry is not found.
    """
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    rigs = config.get("rigs", [])
    if not rigs:
        print("ERROR: No rigs defined in config file")
        sys.exit(1)

    if rig_number < 1 or rig_number > len(rigs):
        print(f"ERROR: Rig {rig_number} not found (config has {len(rigs)} rig(s))")
        sys.exit(1)

    return rigs[rig_number - 1]


def main():
    from ScalesLink import ScalesClient
    
    # ------------------------------------------------------------------
    # Load rig config
    # ------------------------------------------------------------------
    rig_entry = load_rig_entry(CONFIG_PATH, RIG_NUMBER)
    scales_yaml = rig_entry.get("scales")
    if scales_yaml is None:
        print(f"ERROR: No scales configuration found for Rig {RIG_NUMBER}")
        return
    
    print("=" * 60)
    print("  Scales Server-Client System Test")
    print("=" * 60)
    
    # Setup paths
    TEST_SAVE_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    log_file = TEST_SAVE_PATH / f"scales_test_{timestamp}.csv"
    
    print(f"  Rig            : {RIG_NUMBER}")
    print(f"  Config file    : {CONFIG_PATH}")
    print(f"  Test duration  : {TEST_DURATION}s")
    print(f"  Save file      : {log_file}")
    print()
    
    # Load config from rigs.yaml
    print("Loading scales config from rigs.yaml...")

    # Resolve COM port via board registry
    board_name = scales_yaml.get("board_name", "")
    baud_rate = scales_yaml.get("baud_rate", 115200)
    if board_name:
        registry = BoardRegistry(BOARD_REGISTRY_PATH)
        com_port = registry.find_board_port(board_name)
        print(f"  Board: {board_name} -> {com_port}")
    else:
        com_port = scales_yaml["com_port"]
    
    tcp_port = scales_yaml.get("tcp_port", 5100)
    is_wired = scales_yaml.get("is_wired", False)
    calibration_scale = scales_yaml.get("calibration_scale", 1.0)
    calibration_intercept = scales_yaml.get("calibration_intercept", 0.0)
    
    print(f"  Board: {board_name}")
    print(f"  Resolved Port: {com_port}")
    print(f"  Baud Rate: {baud_rate}")
    print(f"  TCP Port: {tcp_port}")
    print(f"  Is Wired: {is_wired}")
    print(f"  Calibration: scale={calibration_scale}, intercept={calibration_intercept}")
    
    # --- Part 1: Start server subprocess ---
    print("\n" + "-" * 60)
    print("PART 1: Starting scales server subprocess")
    print("-" * 60)
    
    command = [
        sys.executable,
        "-m", "ScalesLink.server",
        "--port", com_port,
        "--baud", str(baud_rate),
        "--tcp", str(tcp_port),
        "--log", str(log_file),
        "--scale", str(calibration_scale),
        "--intercept", str(calibration_intercept),
    ]
    
    if is_wired:
        command.append("--wired")
    
    print(f"  Command: {' '.join(command)}")
    print()
    
    server_process = subprocess.Popen(
        command,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print(f"  ✓ Server started (PID: {server_process.pid})")
    
    # Wait for server to initialise
    print("  Waiting for server to initialise...")
    time.sleep(3)
    
    # Check process is still running
    if server_process.poll() is not None:
        print(f"  ✗ Server terminated unexpectedly (exit code: {server_process.returncode})")
        return
    
    print("  ✓ Server is running")
    
    # --- Part 2: Connect client ---
    print("\n" + "-" * 60)
    print("PART 2: Connecting client")
    print("-" * 60)
    
    client = ScalesClient(tcp_port=tcp_port)
    
    # Retry ping a few times
    connected = False
    for attempt in range(5):
        if client.ping(timeout=2.0):
            connected = True
            break
        print(f"  Ping attempt {attempt + 1}/5 failed, retrying...")
        time.sleep(1)
    
    if not connected:
        print("  ✗ Failed to connect to server")
        server_process.terminate()
        return
    
    print("  ✓ Client connected (ping successful)")
    
    # --- Part 3: Read weights ---
    print("\n" + "-" * 60)
    print(f"PART 3: Reading weights for {TEST_DURATION} seconds")
    print("-" * 60)
    
    readings = []
    start_time = time.time()
    read_count = 0
    
    while time.time() - start_time < TEST_DURATION:
        weight = client.get_weight()
        read_count += 1
        
        if weight is not None:
            readings.append(weight)
            elapsed = time.time() - start_time
            print(f"  [{elapsed:5.1f}s] Weight: {weight:.2f}g")
        
        time.sleep(0.5)
    
    print()
    print(f"  Total requests: {read_count}")
    print(f"  Successful readings: {len(readings)}")
    if readings:
        print(f"  Weight range: {min(readings):.2f}g - {max(readings):.2f}g")
        print(f"  Average weight: {sum(readings)/len(readings):.2f}g")
    
    # --- Part 4: Shutdown server ---
    print("\n" + "-" * 60)
    print("PART 4: Shutting down server")
    print("-" * 60)
    
    if client.shutdown():
        print("  ✓ Shutdown command acknowledged")
    else:
        print("  ✗ Shutdown command failed")
    
    # Wait for process to terminate
    time.sleep(2)
    
    if server_process.poll() is not None:
        print(f"  ✓ Server process terminated (exit code: {server_process.returncode})")
    else:
        print("  ! Server still running, terminating...")
        server_process.terminate()
        server_process.wait(timeout=5)
        print("  ✓ Server terminated")
    
    # --- Part 5: Verify saved data ---
    print("\n" + "-" * 60)
    print("PART 5: Verifying saved data")
    print("-" * 60)
    
    if log_file.exists():
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        print(f"  ✓ File created: {log_file.name}")
        print(f"  ✓ File size: {log_file.stat().st_size} bytes")
        print(f"  ✓ Total lines: {len(lines)} ({len(lines)-1} data rows)")
        
        if lines:
            print(f"\n  Header: {lines[0].strip()}")
            
            if len(lines) > 1:
                print(f"\n  First 3 data rows:")
                for line in lines[1:4]:
                    print(f"    {line.strip()}")
                
                if len(lines) > 4:
                    print(f"\n  Last 3 data rows:")
                    for line in lines[-3:]:
                        print(f"    {line.strip()}")
    else:
        print(f"  ✗ File not found: {log_file}")
    
    # --- Summary ---
    print("\n" + "=" * 60)
    print("  Test Complete!")
    print("=" * 60)
    print(f"  Server-client communication: {'✓ OK' if connected else '✗ FAILED'}")
    print(f"  Weight readings: {len(readings)}/{read_count}")
    print(f"  Data saved to: {log_file}")


if __name__ == "__main__":
    main()
