"""
DAQ Connection Test

Minimal script to verify serial connectivity and handshake with a DAQ Arduino.
Opens the port, sends the handshake byte, waits for acknowledgement, then closes.

Usage:
    python test_connection.py
    
Edit the main() call at the bottom to change the COM port or baud rate.
"""

import sys
import time

import serial


def test_connection(com_port: str, baud_rate: int = 115200, timeout: float = 5.0) -> bool:
    """
    Connect to a DAQ Arduino, perform the handshake, and disconnect.

    Args:
        com_port: Serial port (e.g. "COM10").
        baud_rate: Baud rate (default 115200).
        timeout: Seconds to wait for handshake response.

    Returns:
        True if the handshake succeeded.
    """
    print(f"[1/4] Opening {com_port} at {baud_rate} baud...")
    try:
        ser = serial.Serial(com_port, baud_rate, timeout=1)
    except serial.SerialException as exc:
        print(f"  FAIL - could not open port: {exc}")
        return False

    # Brief pause for Arduino to reset after DTR toggle
    print("[2/4] Waiting for Arduino to reset...")
    time.sleep(2)

    print("[3/4] Sending handshake ('s')...")
    try:
        ser.reset_input_buffer()
        ser.write(b"s")
        response = ser.read_until(b"s", int(timeout))
        if b"s" in response:
            print("  OK - handshake acknowledged")
        else:
            print(f"  FAIL - no acknowledgement within {timeout}s (got: {response!r})")
            ser.close()
            return False
    except Exception as exc:
        print(f"  FAIL - handshake error: {exc}")
        ser.close()
        return False

    print("[4/4] Closing connection...")
    ser.close()
    print("  Done - connection test PASSED")
    return True


if __name__ == "__main__":
    # ---- Edit these to match your setup ----
    success = test_connection(com_port="COM5", baud_rate=115200)
    sys.exit(0 if success else 1)
