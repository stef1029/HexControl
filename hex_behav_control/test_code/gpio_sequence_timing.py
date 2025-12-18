"""GPIO Sequential Timing Test
===========================

This script repeatedly drives two rig GPIO pins HIGH in immediate sequence,
holds them for a short time, then drives them LOW in sequence.

Use this when you want to measure the timing skew between two outputs on an
oscilloscope when the pins are controlled by two separate commands.

Notes:
    - This uses the standard reliable command path in `BehaviourRigLink`, so
      each GPIO set waits for an acknowledgement.
    - If you need both pins to change state truly simultaneously, you will
      likely need a single firmware command that sets both pins at once.

Usage:
    Connect the rig, set SERIAL_PORT and pins below, then run:
        python gpio_sequence_timing.py
"""

import time

import serial

from rig_link import (
    BehaviourRigLink,
    GPIOMode,
    log_message,
    reset_arduino_via_dtr,
)


def run_sequence(
    link: BehaviourRigLink,
    first_pin: int,
    second_pin: int,
    *,
    num_cycles: int,
    high_time_s: float,
    low_time_s: float,
) -> None:
    """Toggle two GPIO pins HIGH then LOW, sequentially, for a number of cycles."""

    # Ensure both pins are configured as outputs and start LOW
    link.gpio_configure(first_pin, GPIOMode.OUTPUT)
    link.gpio_configure(second_pin, GPIOMode.OUTPUT)
    link.gpio_off(first_pin)
    link.gpio_off(second_pin)

    log_message(
        f"Starting GPIO sequence: first={first_pin}, second={second_pin}, "
        f"cycles={num_cycles}, high_time={high_time_s}s, low_time={low_time_s}s"
    )

    for i in range(num_cycles):
        # Rising edges (sequential)
        link.gpio_on(first_pin)
        link.gpio_on(second_pin)

        if high_time_s > 0:
            time.sleep(high_time_s)

        # Falling edges (sequential)
        link.gpio_off(first_pin)
        link.gpio_off(second_pin)

        if low_time_s > 0 and i < num_cycles - 1:
            time.sleep(low_time_s)

        # Light progress logging (avoid spamming)
        if (i + 1) % 25 == 0 or (i + 1) == num_cycles:
            log_message(f"Completed {i + 1}/{num_cycles} cycles")


def main() -> None:
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    SERIAL_PORT = "COM7"
    BAUD_RATE = 115200
    SERIAL_TIMEOUT = 0.1

    HANDSHAKE_TIMEOUT = 3.0

    FIRST_PIN = 4
    SECOND_PIN = 5

    NUM_CYCLES = 2000
    HIGH_TIME_S = 0.05
    LOW_TIME_S = 0.20

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    log_message(f"Opening serial port {SERIAL_PORT} at {BAUD_RATE} baud...")

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT) as ser:
        log_message("Serial port opened successfully")
        reset_arduino_via_dtr(ser)
        log_message("Arduino reset complete")

        with BehaviourRigLink(ser) as link:
            log_message("Sending handshake...")
            link.send_hello()
            link.wait_hello(timeout=HANDSHAKE_TIMEOUT)
            log_message("Handshake successful - rig connected")

            try:
                run_sequence(
                    link,
                    FIRST_PIN,
                    SECOND_PIN,
                    num_cycles=NUM_CYCLES,
                    high_time_s=HIGH_TIME_S,
                    low_time_s=LOW_TIME_S,
                )
            finally:
                # Leave outputs in a safe state
                try:
                    link.gpio_off(FIRST_PIN)
                    link.gpio_off(SECOND_PIN)
                except Exception:
                    pass

                log_message("Shutting down rig...")
                link.shutdown()

    log_message("GPIO sequential timing test complete")


if __name__ == "__main__":
    main()
