"""
Scales Calibration Utility

Interactive calibration routine for scales on behaviour rigs.
Guides you through measuring empty and 100g reference weights,
then outputs the calibration values to copy into the configuration.

Usage:
    Set the parameters below, then run:
        python -m ScalesLink.calibrate
"""

import struct
import sys
import time
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import serial
import yaml

# ── Configuration ─────────────────────────────────────────────
RIGS_CONFIG_PATH: str = r"C:\Dev\projects\rigs_config.yaml"
RIG_NUMBER: int = 4
NUM_READINGS: int = 400          # Number of readings to average
# ──────────────────────────────────────────────────────────────


def run_calibration(
    com_port: str,
    baud_rate: int = 115200,
    is_wired: bool = False,
    num_readings: int = 200,
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
        """Read the most recent raw value from the scales."""
        nonlocal data_buffer

        if is_wired:
            if ser.in_waiting > 0:
                data_buffer.extend(ser.read(ser.in_waiting))

            # Parse ALL complete messages, keep only the last value
            delimiter = b'\x02\x03'
            latest: Optional[float] = None
            while True:
                idx = data_buffer.find(delimiter)
                if idx == -1:
                    break
                msg = data_buffer[:idx]
                data_buffer[:] = data_buffer[idx + 2:]
                if len(msg) == 8:
                    value_bytes = msg[1::2]
                    latest = struct.unpack('>f', value_bytes)[0]
            return latest
        else:
            try:
                line = ser.readline().decode('utf-8').strip()
                return float(line) if line else None
            except (ValueError, UnicodeDecodeError):
                return None

    def collect_readings(n: int = num_readings, label: str = "Reading") -> list[float]:
        """Take n readings and return all values."""
        # Flush stale data: drain, wait for in-flight bytes, drain again
        ser.read_all()
        data_buffer.clear()
        time.sleep(0.5)
        ser.read_all()
        data_buffer.clear()

        readings: list[float] = []

        while len(readings) < n:
            val = read_raw()
            if val is not None:
                readings.append(val)
                print(f"\r  {label} {len(readings)}/{n}...", end="", flush=True)

        print()
        return readings

    def show_readings_plot(readings: list[float], label: str = "Reading") -> None:
        """Show a post-hoc plot of collected readings."""
        n = len(readings)
        xs = list(range(1, n + 1))
        cum_avg = list(np.cumsum(readings) / np.arange(1, n + 1))

        fig, (ax_raw, ax_avg) = plt.subplots(1, 2, figsize=(10, 4))
        fig.suptitle(f"{label}  —  {n} samples  |  mean = {np.mean(readings):.4f}", fontsize=12)

        ax_raw.plot(xs, readings, "b-", linewidth=0.8)
        ax_raw.set_xlabel("Sample #")
        ax_raw.set_ylabel("Raw value")
        ax_raw.set_title("Raw readings")

        ax_avg.plot(xs, cum_avg, "r-", linewidth=1.2)
        ax_avg.set_xlabel("Sample #")
        ax_avg.set_ylabel("Running average")
        ax_avg.set_title("Running mean")

        fig.tight_layout(rect=[0, 0, 1, 0.93])
        plt.show(block=False)

    def show_summary_plot(
        empty_readings: list[float],
        hundred_readings: list[float],
        gradient: float,
        intercept: float,
    ) -> None:
        """Show the calibration summary in a new matplotlib window."""
        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        fig.suptitle("Calibration Summary", fontsize=14, fontweight="bold")

        # --- Panel 1: Distribution of raw readings ---
        ax = axes[0]
        ax.hist(empty_readings, bins=25, alpha=0.7, label="Empty", color="steelblue")
        ax.hist(hundred_readings, bins=25, alpha=0.7, label="100 g", color="coral")
        ax.axvline(np.mean(empty_readings), color="steelblue", ls="--", lw=1.5)
        ax.axvline(np.mean(hundred_readings), color="coral", ls="--", lw=1.5)
        ax.set_xlabel("Raw value")
        ax.set_ylabel("Count")
        ax.set_title("Raw reading distributions")
        ax.legend()

        # --- Panel 2: Calibration line ---
        ax = axes[1]
        empty_mean = np.mean(empty_readings)
        hundred_mean = np.mean(hundred_readings)

        # Plot line across raw range with some padding
        raw_lo = min(empty_mean, hundred_mean)
        raw_hi = max(empty_mean, hundred_mean)
        pad = (raw_hi - raw_lo) * 0.15
        raw_line = np.linspace(raw_lo - pad, raw_hi + pad, 200)
        calibrated = (raw_line - intercept) * gradient / 1000  # mg → g

        ax.plot(raw_line, calibrated, "k-", linewidth=1.5, label="Calibration line")
        ax.scatter(
            [empty_mean, hundred_mean],
            [0, 100],
            s=80, zorder=5, color=["steelblue", "coral"],
            edgecolors="black", linewidths=0.8,
        )
        ax.annotate("Empty (0 g)", (empty_mean, 0), textcoords="offset points",
                     xytext=(10, -15), fontsize=9, color="steelblue")
        ax.annotate("100 g", (hundred_mean, 100), textcoords="offset points",
                     xytext=(10, 10), fontsize=9, color="coral")
        ax.set_xlabel("Raw value")
        ax.set_ylabel("Weight (g)")
        ax.set_title("Two-point calibration")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        # --- Panel 3: Text summary ---
        ax = axes[2]
        ax.axis("off")
        text_lines = [
            f"Samples per point:  {len(empty_readings)}",
            "",
            f"Empty mean:  {empty_mean:.4f}",
            f"Empty std:   {np.std(empty_readings):.4f}",
            "",
            f"100 g mean:  {hundred_mean:.4f}",
            f"100 g std:   {np.std(hundred_readings):.4f}",
            "",
            f"calibration_scale:      {gradient:.6f}",
            f"calibration_intercept:  {intercept:.6f}",
        ]
        ax.text(
            0.05, 0.95, "\n".join(text_lines),
            transform=ax.transAxes, fontsize=11, verticalalignment="top",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8),
        )
        ax.set_title("Values for rigs.yaml")

        fig.tight_layout(rect=[0, 0, 1, 0.93])
        plt.show(block=False)

    try:
        # Empty measurement
        input("1. Empty the scale, then press Enter to continue...")
        print("   Taking readings...")
        empty_readings = collect_readings(num_readings, label="Empty")
        empty = float(np.mean(empty_readings))
        print(f"   Empty reading: {empty:.4f}")
        show_readings_plot(empty_readings, label="Empty")
        print()

        # 100g measurement
        input("2. Place 100g calibration weight on the scale, then press Enter...")
        print("   Waiting for load cell to settle...")
        time.sleep(3)
        print("   Taking readings...")
        hundred_readings = collect_readings(num_readings, label="100 g")
        hundred = float(np.mean(hundred_readings))
        print(f"   100g reading: {hundred:.4f}")
        show_readings_plot(hundred_readings, label="100 g")
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

        # Show summary plot
        show_summary_plot(empty_readings, hundred_readings, gradient, empty)

        # Keep plots open until user closes them
        input("\nPress Enter to close plots and exit...")
        plt.close("all")

    finally:
        if is_wired:
            try:
                ser.write(b'e')  # Stop acquisition
            except:
                pass
        ser.close()


def main():
    """Main entry point for running calibration."""
    # Load rigs config
    config_path = Path(RIGS_CONFIG_PATH)
    if not config_path.exists():
        print(f"ERROR: Rigs config not found: {config_path}")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    rigs = config.get("rigs", [])
    if RIG_NUMBER < 1 or RIG_NUMBER > len(rigs):
        print(f"ERROR: RIG_NUMBER={RIG_NUMBER} is out of range (1-{len(rigs)})")
        return

    rig = rigs[RIG_NUMBER - 1]
    rig_name = rig.get("name", f"Rig {RIG_NUMBER}")
    scales_cfg = rig.get("scales")
    if not scales_cfg:
        print(f"ERROR: No 'scales' section found for {rig_name}")
        return

    board_name = scales_cfg.get("board_name")
    is_wired = scales_cfg.get("is_wired", False)

    if not board_name:
        print(f"ERROR: No 'board_name' in scales config for {rig_name}")
        return

    baud_rate = scales_cfg.get("baud_rate", 115200)

    # Resolve COM port via board registry
    try:
        _brs_root = Path(__file__).resolve().parents[3] / "behaviour_rig_system"
        if str(_brs_root) not in sys.path:
            sys.path.insert(0, str(_brs_root))
        from core.board_registry import BoardRegistry
        registry = BoardRegistry()
        com_port = registry.find_board_port(board_name)
        print(f"Rig: {rig_name}")
        print(f"Resolved board '{board_name}' -> {com_port} @ {baud_rate}")
    except Exception as e:
        print(f"Failed to resolve board '{board_name}': {e}")
        return

    run_calibration(
        com_port=com_port,
        baud_rate=baud_rate,
        is_wired=is_wired,
        num_readings=NUM_READINGS,
    )


if __name__ == '__main__':
    main()
