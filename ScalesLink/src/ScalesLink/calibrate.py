"""
Scales Calibration Utility

Interactive calibration routine for scales on behaviour rigs.
Guides you through measuring empty and 100g reference weights,
then outputs the calibration values to copy into the configuration.

Usage:
    python -m ScalesLink.calibrate --port COM7 --baud 115200 --wired
    python -m ScalesLink.calibrate --port COM10 --baud 9600
"""

import argparse
import struct
import time
from typing import Optional

import serial


def run_calibration(
    com_port: str,
    baud_rate: int = 115200,
    is_wired: bool = False,
    num_readings: int = 50,
) -> None:
    """
    Interactive calibration routine for scales.

    Guides the user through measuring empty and 100g reference weights,
    then outputs the calibration values to copy into the configuration.

    Args:
        com_port: Serial port (e.g., "COM7").
        baud_rate: Serial baud rate.
        is_wired: True for wired scales protocol, False for wireless.
        num_readings: Number of readings to average for each measurement.
    """
    print(f"Calibrating scales on {com_port} @ {baud_rate} baud")
    print(f"Protocol: {'wired' if is_wired else 'wireless'}")
    print()

    ser = serial.Serial(com_port, baud_rate, timeout=0.1)
    time.sleep(2)

    if is_wired:
        ser.write(b'e')  # Reset
        ser.write(b't')  # Tare
        time.sleep(3)
        ser.write(b's')  # Start acquisition

    # Buffer for wired scales parsing
    data_buffer = bytearray()

    def read_raw() -> Optional[float]:
        """Read a single raw value from the scales."""
        nonlocal data_buffer

        if is_wired:
            if ser.in_waiting > 0:
                data_buffer.extend(ser.read(ser.in_waiting))
                delimiter = b'\x02\x03'
                idx = data_buffer.find(delimiter)
                if idx != -1:
                    msg = data_buffer[:idx]
                    data_buffer[:] = data_buffer[idx + 2:]
                    if len(msg) == 8:
                        value_bytes = msg[1::2]
                        return struct.unpack('>f', value_bytes)[0]
            return None
        else:
            try:
                line = ser.readline().decode('utf-8').strip()
                return float(line) if line else None
            except (ValueError, UnicodeDecodeError):
                return None

    def average_readings(n: int = num_readings) -> float:
        """Take n readings and return the average."""
        ser.read_all()
        data_buffer.clear()
        total = 0.0
        count = 0
        while count < n:
            val = read_raw()
            if val is not None:
                total += val
                count += 1
                print(f"\r  Reading {count}/{n}...", end="", flush=True)
        print()
        return total / n

    try:
        # Empty measurement
        input("1. Empty the scale, then press Enter to continue...")
        print("   Taking readings...")
        empty = average_readings()
        print(f"   Empty reading: {empty:.4f}")
        print()

        # 100g measurement
        input("2. Place 100g calibration weight on the scale, then press Enter...")
        print("   Taking readings...")
        hundred = average_readings()
        print(f"   100g reading: {hundred:.4f}")
        print()

        # Calculate calibration
        if hundred == empty:
            print("ERROR: Empty and 100g readings are the same!")
            print("       Check that the weight is properly placed on the scales.")
            return

        gradient = 100000 / (hundred - empty)  # 100g = 100000 mg

        print("=" * 60)
        print("CALIBRATION COMPLETE")
        print("=" * 60)
        print()
        print("Add these values to your rigs.yaml configuration:")
        print()
        print(f"    calibration_scale: {gradient:.6f}")
        print(f"    calibration_intercept: {empty:.6f}")
        print()
        print("=" * 60)

    finally:
        if is_wired:
            try:
                ser.write(b'e')  # Stop acquisition
            except:
                pass
        ser.close()


def main():
    """Main entry point for running calibration from command line."""
    parser = argparse.ArgumentParser(
        description='Calibrate scales for behaviour rigs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Calibrate wired scales on COM7
    python -m ScalesLink.calibrate --port COM7 --baud 115200 --wired
    
    # Calibrate wireless scales on COM10
    python -m ScalesLink.calibrate --port COM10 --baud 9600
    
    # Calibrate using board registry name
    python -m ScalesLink.calibrate --board rig_1_scales --wired
    
    # Use more readings for higher precision
    python -m ScalesLink.calibrate --port COM7 --baud 115200 --wired --readings 100
"""
    )
    parser.add_argument(
        '--port', '-p',
        default=None,
        help='Serial port (e.g., COM7, /dev/ttyUSB0). Overridden by --board.'
    )
    parser.add_argument(
        '--board',
        default=None,
        help='Board registry name (e.g., rig_1_scales). Resolves port and baud via board_registry.json.'
    )
    parser.add_argument(
        '--baud', '-b',
        type=int,
        default=None,
        help='Baud rate (default: from registry or 115200)'
    )
    parser.add_argument(
        '--wired', '-w',
        action='store_true',
        help='Use wired protocol (binary messages)'
    )
    parser.add_argument(
        '--readings', '-n',
        type=int,
        default=50,
        help='Number of readings to average (default: 50)'
    )

    args = parser.parse_args()

    # Resolve port: --board takes precedence over --port
    com_port = args.port
    baud_rate = args.baud or 115200

    if args.board:
        try:
            import sys
            from pathlib import Path
            _brs_root = Path(__file__).resolve().parents[3] / "behaviour_rig_system"
            if str(_brs_root) not in sys.path:
                sys.path.insert(0, str(_brs_root))
            from core.board_registry import BoardRegistry
            registry = BoardRegistry()
            com_port = registry.find_board_port(args.board)
            if args.baud is None:
                baud_rate = registry.get_baudrate(args.board)
            print(f"Resolved board '{args.board}' -> {com_port}")
        except Exception as e:
            parser.error(f"Failed to resolve board '{args.board}': {e}")

    if not com_port:
        parser.error("Either --port or --board must be specified")

    run_calibration(
        com_port=com_port,
        baud_rate=baud_rate,
        is_wired=args.wired,
        num_readings=args.readings,
    )


if __name__ == '__main__':
    main()
