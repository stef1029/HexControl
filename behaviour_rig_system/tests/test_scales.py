"""
Scales System Test Script
=========================

Tests the scales system by:
1. Reading weights for a few seconds
2. Detecting threshold crossing events
3. Saving all data to CSV and verifying the file

Usage:
    python -m tests.test_scales

Requirements:
    - Scales hardware connected
    - ScalesLink package installed
    - Correct COM port and baud rate configured in rigs.yaml
"""

import time
from datetime import datetime
from pathlib import Path

import yaml


# =============================================================================
# CONFIGURATION - Edit these values as needed
# =============================================================================

RIG = 1
THRESHOLD = 15.0  # grams - for event detection
TEST_SAVE_PATH = Path("D:/behaviour_data/test_output")

# =============================================================================


def load_scales_config(rig: int) -> dict:
    """Load scales configuration from rigs.yaml for the given rig number."""
    config_path = Path(__file__).parent.parent / "config" / "rigs.yaml"
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    for rig_config in config.get("rigs", []):
        rig_name = rig_config.get("name", "")
        try:
            rig_num = int(rig_name.split()[-1])
            if rig_num == rig:
                scales_config = rig_config.get("scales")
                if scales_config is None:
                    raise ValueError(f"No scales configuration found for {rig_name}")
                return scales_config
        except (ValueError, IndexError):
            continue
    
    raise ValueError(f"Rig {rig} not found in config")


def main():
    from ScalesLink import Scales, ScalesConfig
    
    print("=" * 60)
    print("  Scales System Test")
    print("=" * 60)
    
    # Setup
    TEST_SAVE_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    log_file = TEST_SAVE_PATH / f"scales_test_{timestamp}.csv"
    
    print(f"  Rig: {RIG}")
    print(f"  Threshold: {THRESHOLD}g")
    print(f"  Save file: {log_file}")
    print()
    
    # Load config
    print("Loading scales config from rigs.yaml...")
    scales_yaml = load_scales_config(RIG)
    print(f"  COM Port: {scales_yaml['com_port']}")
    print(f"  Baud Rate: {scales_yaml['baud_rate']}")
    
    config = ScalesConfig.from_yaml_dict(scales_yaml)
    
    # Start scales with logging
    print("\nStarting scales (with CSV logging)...")
    scales = Scales(config, log_path=log_file)
    scales.start()
    
    time.sleep(2)  # Let scales stabilise
    
    # --- Part 1: Read weights ---
    print("\n" + "-" * 60)
    print("PART 1: Reading weights")
    print("-" * 60)
    
    for i in range(10):
        weight = scales.get_weight()
        if weight is not None:
            print(f"  [{i+1}/10] Weight: {weight:.2f}g")
        else:
            print(f"  [{i+1}/10] Weight: None")
        time.sleep(0.5)
    
    # --- Part 2: Threshold events ---
    print("\n" + "-" * 60)
    print("PART 2: Threshold event detection")
    print("-" * 60)
    print(f"  Threshold: {THRESHOLD}g")
    print(f"  Detecting crossings for 20 seconds...")
    print(f"  (Add/remove weight to trigger events, or wait)")
    print()
    
    current_weight = scales.get_weight()
    above_threshold = current_weight is not None and current_weight > THRESHOLD
    last_above = above_threshold
    events = []
    
    start_time = time.time()
    while time.time() - start_time < 20:
        weight = scales.get_weight()
        if weight is not None:
            now_above = weight > THRESHOLD
            
            if now_above != last_above:
                direction = "UP" if now_above else "DOWN"
                event_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                events.append({"time": event_time, "direction": direction, "weight": weight})
                print(f"  ✓ [{event_time}] Crossed {direction} - {weight:.2f}g")
                last_above = now_above
        
        time.sleep(0.05)
    
    print(f"\n  Events detected: {len(events)}")
    
    # --- Stop scales ---
    print("\nStopping scales...")
    scales.stop()
    
    # --- Part 3: Verify saved data ---
    print("\n" + "-" * 60)
    print("PART 3: Verifying saved data")
    print("-" * 60)
    
    if log_file.exists():
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        print(f"  ✓ File created: {log_file.name}")
        print(f"  ✓ File size: {log_file.stat().st_size} bytes")
        print(f"  ✓ Total lines: {len(lines)} ({len(lines)-1} data rows)")
        print(f"\n  Header: {lines[0].strip()}")
        print(f"\n  First 3 data rows:")
        for line in lines[1:4]:
            print(f"    {line.strip()}")
        print(f"\n  Last 3 data rows:")
        for line in lines[-3:]:
            print(f"    {line.strip()}")
    else:
        print(f"  ✗ File not found: {log_file}")
    
    # --- Summary ---
    print("\n" + "=" * 60)
    print("  Test Complete!")
    print("=" * 60)
    print(f"  Data saved to: {log_file}")


if __name__ == "__main__":
    main()
