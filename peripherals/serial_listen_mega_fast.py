"""
ArduinoDAQ Data Acquisition Script
=================================

Connects to an Arduino Mega via serial, streams binary‑encoded event messages,
performs incremental NumPy backups, and finally archives data to HDF5 and JSON.
Supports coordination with companion processes (e.g. camera acquisition)
through sentinel "*.signal" files.

Run interactively or from the command line.  See ``main`` for CLI usage.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import argparse
import asyncio
import csv
import glob
import json
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import traceback

# ---------------------------------------------------------------------------
# Third‑party imports
# ---------------------------------------------------------------------------
import keyboard           # Hot‑key support (pip install keyboard)
import numpy as np        # Numeric arrays
import h5py               # HDF5 persistence
import serial             # pyserial
from colorama import init, Fore, Style
from tqdm import tqdm     # Progress bars
import tkinter as tk      # Tiny status window

# Colour output for Windows cmd
init()

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
EXIT_KEY   = "esc"     # Emergency‑stop key (test mode only)
TEST_MODE  = False     # Set to ``True`` to enable hot‑key exit
BAK_INTSEC = 5.0       # Seconds between incremental back‑ups

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

class StatusWindow:
    """Popup window showing current script status."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Script Status")
        self.root.geometry("300x100")
        self.status_label = tk.Label(self.root, text="Initializing…", font=("Helvetica", 14))
        self.status_label.pack(expand=True)
        self.update_flag = True

    def update_status(self, message: str) -> None:
        """Update the status message displayed in the window."""
        if self.update_flag:
            self.status_label.config(text=message)
            self.root.update()

    def close_window(self) -> None:
        """Mark the window as disabled and destroy it."""
        self.update_flag = False
        self.root.destroy()

    def run(self) -> None:  # blocking
        """Start the main event loop of the window."""
        self.root.mainloop()

# ---------------------------------------------------------------------------
# Utility helpers (back‑up housekeeping, sentinel checking)
# ---------------------------------------------------------------------------

def read_all_backups(backup_folder: Path) -> np.ndarray:
    """Return concatenated ndarray of every ``backup-*.npy`` in *backup_folder*."""
    backup_files = sorted(glob.glob(str(backup_folder / "backup-*.npy")))
    if not backup_files:
        return np.empty((0, 3))
    arrays: list[np.ndarray] = []
    for file_path in tqdm(backup_files, desc="Reading backup files", unit="file"):
        try:
            arrays.append(np.load(file_path))
        except Exception as exc:  # noqa: BLE001
            print(f"Error reading {file_path}: {exc}")
    return np.concatenate(arrays) if arrays else np.empty((0, 3))


def delete_backups(backup_folder: Path) -> None:
    """Delete every ``backup-*.npy`` in *backup_folder*."""
    for file_path in glob.glob(str(backup_folder / "backup-*.npy")):
        try:
            os.remove(file_path)
        except Exception as exc:  # noqa: BLE001
            print(f"Error deleting {file_path}: {exc}")


async def watch_sentinel(signal_path: Path, stop_event: asyncio.Event) -> None:
    """Set *stop_event* when *signal_path* appears (camera finished signal)."""
    if TEST_MODE:
        threading.Thread(target=lambda: keyboard.wait(EXIT_KEY) or stop_event.set(), daemon=True).start()

    try:
        while not stop_event.is_set():
            if signal_path.exists():
                print(f"{Fore.YELLOW}ArduinoDAQ:{Style.RESET_ALL} Sentinel detected → stopping acquisition")
                stop_event.set()
                break
            await asyncio.sleep(1)
    finally:
        if TEST_MODE:
            keyboard.unhook_all()

# ---------------------------------------------------------------------------
# Archive writers
# ---------------------------------------------------------------------------

def save_hdf5_json(
    foldername: str,
    output_directory: Path,
    mouse_id: str,
    date_time: str,
    records: list[list[int | float]],
    message_counter: int,
    full_messages: int,
    time_start: float,
    time_end: float,
    error_messages: list[list],
) -> None:
    """Persist parsed data to ``*.h5`` and metadata to ``*.json``."""
    message_ids = np.fromiter((record[0] for record in records), dtype=np.uint32)
    message_words = np.fromiter((record[1] for record in records), dtype=np.uint64)
    timestamps = np.fromiter((record[2] for record in records), dtype=np.float64)

    # Channel map (least‑significant bit first)
    channel_indices = (
        # Removed spotlights  → "SPOT1"‥"SPOT6"
        # Removed buzzers     → "BUZZER1"‥"BUZZER6"
        "SENSOR6", "SENSOR1", "SENSOR5", "SENSOR2", "SENSOR4", "SENSOR3",
        "LED_3",   "LED_4",   "LED_2",   "LED_5",   "LED_1",   "LED_6",
        "VALVE4",  "VALVE3",  "VALVE5",  "VALVE2",  "VALVE6",  "VALVE1",
        "GO_CUE",  "NOGO_CUE", "CAMERA", "SCALES", "LASER",
    )
    num_channels = len(channel_indices)
    num_messages = message_words.size
    channel_data_array = np.zeros((num_messages, num_channels), dtype=np.uint8)

    valid_message_indices: list[int] = []
    binary_list: list[str] = []

    for i, word in tqdm(enumerate(message_words), total=num_messages, desc="Processing messages", unit="msg"):
        try:
            bits = np.binary_repr(word, width=40)[-num_channels:][::-1]
            if len(bits) == num_channels:
                channel_data_array[i] = np.fromiter(bits, dtype=np.uint8)
                valid_message_indices.append(i)
                binary_list.append(bits)
            else:
                error_messages.append([i, f"bit‑count {len(bits)}", timestamps[i]])
        except Exception as exc:  # noqa: BLE001
            error_messages.append([i, str(exc), timestamps[i]])

    valid_message_indices = np.asarray(valid_message_indices)
    if valid_message_indices.size < num_messages:
        skipped_messages = num_messages - valid_message_indices.size
        print(f"Warning: {skipped_messages} malformed messages skipped")
        if valid_message_indices.size:
            message_ids = message_ids[valid_message_indices]
            timestamps = timestamps[valid_message_indices]
            channel_data_array = channel_data_array[valid_message_indices]
        else:  # all bad
            message_ids = timestamps = channel_data_array = np.empty((0,))
            binary_list = []

    reliability = (full_messages / message_counter * 100) if message_counter else 0.0

    metadata_dict = {
        "mouse_ID":             mouse_id,
        "date_time":            date_time,
        "time":                 str(datetime.now()),
        "No_of_messages":       valid_message_indices.size,
        "reliability":          reliability,
        "time_taken":           time_end - time_start,
        "messages_per_second":  (valid_message_indices.size / (time_end - time_start)) if time_end > time_start else 0,
        "message_ids":          message_ids.tolist(),
        "timestamps":           timestamps.tolist(),
        "channel_data_raw":     binary_list,
        "error_messages":       error_messages,
    }

    # JSON
    json_file_path = output_directory / f"{foldername}-ArduinoDAQ.json"
    with open(json_file_path, "w") as file_handle:
        json.dump(metadata_dict, file_handle, indent=4)

    # HDF5
    hdf5_file_path = output_directory / f"{foldername}-ArduinoDAQ.h5"
    with h5py.File(hdf5_file_path, "w") as h5_file:
        h5_file.attrs.update(
            mouse_ID           = mouse_id,
            date_time          = date_time,
            time               = str(datetime.now()),
            No_of_messages     = valid_message_indices.size,
            reliability        = reliability,
            time_taken         = time_end - time_start,
            messages_per_second= metadata_dict["messages_per_second"],
        )
        h5_file.create_dataset("message_ids", data=message_ids, compression="gzip")
        h5_file.create_dataset("timestamps",  data=timestamps, compression="gzip")
        channel_group = h5_file.create_group("channel_data")
        for i, channel_name in enumerate(channel_indices):
            channel_group.create_dataset(channel_name, data=channel_data_array[:, i], compression="gzip")
        if error_messages:
            error_messages_str = np.array([str(e) for e in error_messages], dtype=h5py.string_dtype())
            h5_file.create_dataset("error_messages", data=error_messages_str, compression="gzip")

# ---------------------------------------------------------------------------
# Acquisition coroutine
# ---------------------------------------------------------------------------

async def listen(
    new_mouse_id:  str | None = None,
    new_date_time: str | None = None,
    new_path:      str | None = None,
    rig:           str | None = None,
) -> None:
    """Serial acquisition task (top‑level coroutine)."""
    messages_from_arduino: deque[list[int | float]] = deque()
    backup_buffer: deque[list[int | float]] = deque()

    mouse_id  = new_mouse_id or input(r"Enter mouse ID (no '.'s): ")
    date_time = new_date_time or f"{datetime.now():%y%m%d_%H%M%S}"
    foldername = f"{date_time}_{mouse_id}"

    output_path = Path(new_path) if new_path else Path.cwd() / foldername
    output_path.mkdir(exist_ok=True)

    backup_folder = output_path / "backup_files"
    backup_folder.mkdir(exist_ok=True)

    connection_signal_file = output_path / (f"rig_{rig}_arduino_connected.signal" if rig else "arduino_connected.signal")

    # COM‑port determination
    if rig is None:
        com_port = "COM2"
    else:
        com_port = {"1": "COM12", "2": "COM18", "3": "COM30", "4": "COM17"}.get(rig)
        if com_port is None:
            raise ValueError("Rig number not recognised")

    print(f"Connecting to Arduino Mega on {com_port}…")
    try:
        serial_connection = serial.Serial(com_port, 115200, timeout=1)
    except serial.SerialException:
        print("Serial not found → retrying in 3 s…")
        time.sleep(3)
        try:
            serial_connection = serial.Serial(com_port, 115200, timeout=1)
            time.sleep(3)
        except serial.SerialException:
            print("Failed to connect to Arduino Mega after retry.")
            return

    try:
        serial_connection.write(b"s")
        serial_connection.reset_input_buffer()
        if b"s" not in serial_connection.read_until(b"s", 5):
            print("Handshake failed — aborting.")
            return
        print("Arduino Mega connection established.")
        connection_signal_file.write_text(f"Connected at {datetime.now()}")
    except Exception as exc:  # noqa: BLE001
        print(f"Handshake error: {exc}")
        return

    start_time = time.perf_counter()
    message_counter = 0
    full_messages = 0
    error_messages: list[list] = []

    stop_event = asyncio.Event()
    signal_file_path = output_path / (f"rig_{rig}_camera_finished.signal" if rig else "camera_finished.signal")
    asyncio.create_task(watch_sentinel(signal_file_path, stop_event))

    backup_counter = 1
    last_backup_time = time.perf_counter()

    while not stop_event.is_set():
        if serial_connection.in_waiting > 9:
            current_time = time.perf_counter() - start_time
            raw_message = serial_connection.read_until(b"\x02\x01")[:-2]
            if message_counter == 0:  # skip leading 0x00 from Arduino reset
                raw_message = raw_message[1:]
            if len(raw_message) == 9:
                message_id = (raw_message[0] << 24) | (raw_message[2] << 16) | (raw_message[4] << 8) | raw_message[6]
                message_word = (raw_message[1] << 32) | (raw_message[3] << 24) | (raw_message[5] << 16) | (raw_message[7] << 8) | raw_message[8]
                record = [message_id, message_word, current_time]
                messages_from_arduino.append(record)
                backup_buffer.append(record)
                full_messages += 1
            else:
                error_messages.append([message_counter, raw_message.hex(), current_time])
            message_counter += 1

        # periodic back‑up
        current_time = time.perf_counter()
        if current_time - last_backup_time >= BAK_INTSEC and backup_buffer:
            # np.save(backup_folder / f"backup-{backup_counter:04d}.npy", np.array(backup_buffer))
            backup_buffer.clear()
            backup_counter += 1
            last_backup_time = current_time

        await asyncio.sleep(0)  # yield to event‑loop

    # -- acquisition ended -------------------------------------------------
    for _ in range(3):
        serial_connection.write(b"e")
        time.sleep(0.1)
    serial_connection.close()

    if backup_buffer:  # flush remainder
        # np.save(backup_folder / f"backup-{backup_counter:04d}.npy", np.array(backup_buffer))
        pass

    end_time = time.perf_counter()

    # Archive full dataset
    save_hdf5_json(foldername, output_path, mouse_id, date_time, list(messages_from_arduino), 
                  message_counter, full_messages, start_time, end_time, error_messages)

    # Consolidate incremental backups
    # combined_backup = read_all_backups(backup_folder)
    # if combined_backup.size:
    #     np.save(output_path / f"{foldername}-complete-backup.npy", combined_backup)
    #     delete_backups(backup_folder)
    #     print(f"Combined back‑up ({combined_backup.shape[0]} records) written → individual files deleted")

    print(f"{Fore.YELLOW}ArduinoDAQ:{Style.RESET_ALL} finished.")

# ---------------------------------------------------------------------------
# Command‑line interface
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry‑point for command‑line execution.
    
    Command line Args:
        --id: mouse ID (default: NoID)
        --date: date_time stamp (YYMMDD_HHMMSS)
        --path: output directory
        --rig: rig number [1‑4] (default: 3)
    """
    parser = argparse.ArgumentParser(description="Listen to serial port and save data")
    parser.add_argument("--id",   type=str, help="mouse ID",  default="NoID")
    parser.add_argument("--date", type=str, help="date_time stamp (YYMMDD_HHMMSS)")
    parser.add_argument("--path", type=str, help="output directory")
    parser.add_argument("--rig",  type=str, help="rig number [1‑4]", default="3")
    args = parser.parse_args()

    mouse_id = args.id
    date_time = args.date or f"{datetime.now():%y%m%d_%H%M%S}"
    output_path = args.path or str(Path.cwd() / f"{date_time}_{mouse_id}")

    try:
        asyncio.run(listen(new_mouse_id=mouse_id, new_date_time=date_time, new_path=output_path, rig=args.rig))
    except Exception:
        traceback.print_exc()
        input("ArduinoDAQ error — see traceback above.  Press Enter to exit…")


if __name__ == "__main__":
    main()