"""
Behaviour Rig Ping Timing Script
================================

This script measures the round-trip communication latency between the host
and the behaviour rig. It sends repeated commands and records the time taken
for each acknowledgement to arrive, providing statistics on communication
performance.

The script uses the LED set command as a lightweight ping mechanism, toggling
the LED brightness without any visible effect (setting to current value).

Usage:
    Run this script with the rig connected. Results are printed to stdout
    with individual ping times and summary statistics.
"""

import statistics
import time
from typing import Optional

import serial

from rig_link import (
    BehaviourRigLink,
    log_message,
    reset_arduino_via_dtr,
)


def run_ping_test(
    link: BehaviourRigLink,
    num_pings: int,
    port: int = 0,
    inter_ping_delay: float = 0.05,
) -> list[float]:
    """
    Runs a series of ping tests and returns the round-trip times.

    Each ping sends an LED set command (brightness 0) and measures the time
    until the acknowledgement is received. This provides a measure of the
    full communication round-trip latency.

    Args:
        link: An active BehaviourRigLink connection.
        num_pings: The number of ping measurements to perform.
        port: The LED port to use for pinging (default 0).
        inter_ping_delay: Delay in seconds between pings to avoid flooding.

    Returns:
        A list of round-trip times in milliseconds.
    """
    round_trip_times_ms = []

    for i in range(num_pings):
        start_time = time.perf_counter()

        # Send LED set command (brightness 0 - LED off, minimal side effect)
        link.led_set(port, brightness=0)

        end_time = time.perf_counter()

        # Calculate round-trip time in milliseconds
        rtt_ms = (end_time - start_time) * 1000.0
        round_trip_times_ms.append(rtt_ms)

        log_message(f"Ping {i + 1:3d}/{num_pings}: {rtt_ms:.2f} ms")

        # Small delay between pings to avoid overwhelming the device
        if inter_ping_delay > 0 and i < num_pings - 1:
            time.sleep(inter_ping_delay)

    return round_trip_times_ms


def calculate_statistics(times_ms: list[float]) -> dict[str, float]:
    """
    Calculates summary statistics for a list of timing measurements.

    Args:
        times_ms: List of timing measurements in milliseconds.

    Returns:
        A dictionary containing min, max, mean, median, and standard deviation.
    """
    if not times_ms:
        return {}

    stats = {
        "count": len(times_ms),
        "min_ms": min(times_ms),
        "max_ms": max(times_ms),
        "mean_ms": statistics.mean(times_ms),
        "median_ms": statistics.median(times_ms),
    }

    # Standard deviation requires at least 2 samples
    if len(times_ms) >= 2:
        stats["stdev_ms"] = statistics.stdev(times_ms)
    else:
        stats["stdev_ms"] = 0.0

    return stats


def print_statistics(stats: dict[str, float]) -> None:
    """
    Prints formatted statistics to stdout.

    Args:
        stats: Dictionary of statistics from calculate_statistics().
    """
    print("\n" + "=" * 50)
    print("PING STATISTICS")
    print("=" * 50)
    print(f"  Packets sent:     {int(stats['count'])}")
    print(f"  Minimum RTT:      {stats['min_ms']:.2f} ms")
    print(f"  Maximum RTT:      {stats['max_ms']:.2f} ms")
    print(f"  Mean RTT:         {stats['mean_ms']:.2f} ms")
    print(f"  Median RTT:       {stats['median_ms']:.2f} ms")
    print(f"  Std Deviation:    {stats['stdev_ms']:.2f} ms")
    print("=" * 50)


def main() -> None:
    """
    Main entry point for the ping timing script.

    Connects to the rig, performs a series of ping tests, and reports
    the results with summary statistics.
    """
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    SERIAL_PORT = "COM7"
    BAUD_RATE = 115200
    SERIAL_TIMEOUT = 0.1

    HANDSHAKE_TIMEOUT = 3.0
    NUM_PINGS = 1000
    INTER_PING_DELAY = 0.05  # 50 ms between pings
    PING_PORT = 0  # LED port to use for pinging

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------

    log_message(f"Opening serial port {SERIAL_PORT} at {BAUD_RATE} baud...")

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT) as ser:
        log_message("Serial port opened successfully")
        reset_arduino_via_dtr(ser)
        log_message("Arduino reset complete")

        with BehaviourRigLink(ser) as link:
            # Establish connection
            log_message("Sending handshake...")
            link.send_hello()
            link.wait_hello(timeout=HANDSHAKE_TIMEOUT)
            log_message("Handshake successful - rig connected")

            # Run ping tests
            print("\n" + "=" * 50)
            print(f"STARTING PING TEST ({NUM_PINGS} pings)")
            print("=" * 50 + "\n")

            round_trip_times = run_ping_test(
                link=link,
                num_pings=NUM_PINGS,
                port=PING_PORT,
                inter_ping_delay=INTER_PING_DELAY,
            )

            # Calculate and display statistics
            stats = calculate_statistics(round_trip_times)
            print_statistics(stats)

            # Shutdown cleanly
            log_message("\nShutting down rig...")
            link.shutdown()

    log_message("Ping test complete")


if __name__ == "__main__":
    main()