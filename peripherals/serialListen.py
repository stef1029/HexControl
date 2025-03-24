import serial
import json
import csv
import datetime
import keyboard
import time
from datetime import datetime
import os
import argparse
from pathlib import Path
import h5py
import numpy as np
import asyncio
from collections import deque
import traceback
import threading
import tkinter as tk

from read import Scales

exit_key = "esc"

test = False

class StatusWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Script Status")
        self.root.geometry("300x100")
        self.status_label = tk.Label(self.root, text="Initializing...", font=("Helvetica", 14))
        self.status_label.pack(expand=True)
        self.update_flag = True

    def update_status(self, message):
        if self.update_flag:
            self.status_label.config(text=message)
            self.root.update()

    def close_window(self):
        self.update_flag = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

# async def check_signal_files(file_path_1, stop_event):
#     while not stop_event.is_set():
#         if os.path.exists(file_path_1):
#             stop_event.set()  # Signal to stop the loop
#             break
#         await asyncio.sleep(1)  # Check every 1s

async def check_signal_files(file_path_1, stop_event):
    if test:
        def esc_key_monitor():
            keyboard.wait('esc')  # Wait until the ESC key is pressed
            if not stop_event.is_set():
                stop_event.set()  # Signal to stop the loop

        # Start a separate thread to monitor for the ESC key press
        esc_thread = threading.Thread(target=esc_key_monitor, daemon=True)
        esc_thread.start()

    try:
        while not stop_event.is_set():
            if os.path.exists(file_path_1):
                stop_event.set()  # Signal to stop the loop
                break
            await asyncio.sleep(1)  # Check every 1s
    finally:
        if test:
            # Clean up the keyboard hooks if necessary
            keyboard.unhook_all()


def save_to_hdf5_and_json(foldername, output_path, mouse_ID, date_time, messages_from_arduino, message_counter, full_messages, start, end, error_messages):
    message_ids = np.array([message[0] for message in messages_from_arduino], dtype=np.uint32)
    message_data = np.array([message[1] for message in messages_from_arduino], dtype=np.uint64)

    channel_indices = (
        "SPOT2", "SPOT3", "SPOT4", "SPOT5", "SPOT6", "SPOT1", "SENSOR6", "SENSOR1",
        "SENSOR5", "SENSOR2", "SENSOR4", "SENSOR3", "BUZZER4", "LED_3", "LED_4",
        "BUZZER3", "BUZZER5", "LED_2", "LED_5", "BUZZER2", "BUZZER6", "LED_1",
        "LED_6", "BUZZER1", "VALVE4", "VALVE3", "VALVE5", "VALVE2", "VALVE6",
        "VALVE1", "GO_CUE", "NOGO_CUE", "CAMERA", "SCALES"
    )

    num_channels = len(channel_indices)
    num_messages = len(message_data)

    # Create a 2D NumPy array to hold the channel data
    channel_data_array = np.zeros((num_messages, num_channels), dtype=np.uint8)

    # Convert message data to binary and populate channel_data_array
    for i, message in enumerate(message_data):
        binary_message = np.array(list(np.binary_repr(message, width=num_channels)), dtype=np.uint8)
        binary_message = binary_message[::-1]  # Reverse bits to align LSB with first channel
        channel_data_array[i] = binary_message

    # Estimate timestamps for each message:
    duration = end - start
    timestamps = np.linspace(0, duration, num_messages)

    # Prepare HDF5 file
    save_file_name = f"{foldername}-ArduinoDAQ.h5"
    output_file = output_path / save_file_name

    # Prepare JSON file
    json_file_name = f"{foldername}-ArduinoDAQ.json"
    json_output_file = output_path / json_file_name

    data_to_save = {
        "mouse_ID": mouse_ID,
        "date_time": date_time,
        "time": str(datetime.now()),
        "No_of_messages": num_messages,
        "reliability": (full_messages / message_counter) * 100,
        "time_taken": end - start,
        "messages_per_second": num_messages / (end - start),
        "message_ids": message_ids.tolist(),  # Convert NumPy arrays to lists for JSON
        "timestamps": timestamps.tolist(),
        "channel_data": {channel: channel_data_array[:, idx].tolist() for idx, channel in enumerate(channel_indices)},  # Convert data to lists
        "error_messages": error_messages  # Already in list form
    }

    # Write to JSON file
    with open(json_output_file, 'w') as json_file:
        json.dump(data_to_save, json_file, indent=4)

    with h5py.File(output_file, 'w') as h5f:
        # Save metadata as attributes
        h5f.attrs['mouse_ID'] = mouse_ID
        h5f.attrs['date_time'] = date_time
        h5f.attrs['time'] = str(datetime.now())
        h5f.attrs['No_of_messages'] = num_messages
        h5f.attrs['reliability'] = (full_messages / message_counter) * 100
        h5f.attrs['time_taken'] = end - start
        h5f.attrs['messages_per_second'] = num_messages / (end - start)

        # Save message IDs
        h5f.create_dataset('message_ids', data=message_ids, compression='gzip')

        h5f.create_dataset('timestamps', data=timestamps, compression='gzip')

        # Save channel data under a group
        channel_group = h5f.create_group('channel_data')
        for idx, channel in enumerate(channel_indices):
            channel_group.create_dataset(channel, data=channel_data_array[:, idx], compression='gzip')

        # Save error messages if any, ensuring all messages are converted to strings
        if error_messages:
            error_messages_str = [str(err_msg) for err_msg in error_messages]  # Ensure everything is a string
            error_messages_np = np.array(error_messages_str, dtype=object)
            h5f.create_dataset('error_messages', data=error_messages_np, compression='gzip', dtype=h5py.string_dtype())

def save_to_backup_csv(backup_csv_path, backup_buffer):
    try:
        with open(backup_csv_path, 'a', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerows(backup_buffer)
        return True
    except Exception as e:
        print(f"Error while saving to backup CSV: {e}")
        return False

async def listen(new_mouse_ID=None, new_date_time=None, new_path=None, rig=None):
    messages_from_arduino = deque()
    backup_buffer = deque()

    if new_mouse_ID is None:
        mouse_ID = input(r"Enter mouse ID (no '.'s): ")
    else:
        mouse_ID = new_mouse_ID

    if new_date_time is None:
        date_time = f"{datetime.now():%y%m%d_%H%M%S}"
    else:
        date_time = new_date_time

    foldername = f"{date_time}_{mouse_ID}"

    if new_path is None:
        output_path = Path(os.path.join(os.getcwd(), foldername))
        os.mkdir(output_path)
    else:
        output_path = Path(new_path)

    backup_csv_path = output_path / f"{foldername}-backup.csv"

    if rig is None:
        COM_PORT = "COM2"
    elif rig == "1":
        COM_PORT = "COM17"
    elif rig == "2":
        COM_PORT = "COM18"
    elif rig == "3":
        COM_PORT = "COM17"
    elif rig == "4":
        COM_PORT = "COM17"
    else:
        raise ValueError("Rig number not recognised")

    try:
        ser = serial.Serial(COM_PORT, 115200, timeout = 1)  # open serial port
        time.sleep(3)
    except serial.SerialException:
        print("Serial-listen connection not found, trying again...")
        ser = serial.Serial(COM_PORT, 115200, timeout = 1)
        time.sleep(3)

    ser.write("s".encode("utf-8"))  # send start signal to Arduino
    ser.reset_input_buffer()
    ser.read_until(b"s")

    start = time.perf_counter()
    message_counter = 0
    full_messages = 0
    error_messages = []

    stop_event = asyncio.Event()
    if rig == "1":
        signal_file_path = output_path/"rig_1_camera_finished.signal" 
    elif rig == "2":
        signal_file_path = output_path/"rig_2_camera_finished.signal" 
    elif rig == "3":
        signal_file_path = output_path/"rig_3_camera_finished.signal"
    elif rig == "4":
        signal_file_path = output_path/"rig_4_camera_finished.signal"
    else:
        raise ValueError("Rig number not recognised")

    # Start the task to check for signal file asynchronously with error handling
    try:
        asyncio.create_task(check_signal_files(signal_file_path, stop_event))
    except Exception as e:
        print(f"Error while starting signal file check task: {e}")

    backup_interval = 5  # Time in seconds to save backups
    last_backup_time = time.perf_counter()

    while not stop_event.is_set():
        if ser.in_waiting > 9:
            # Read and strip the terminator
            message = ser.read_until(b"\x02\x01")[:-2]

            # Handle first message differently
            if message_counter == 0:
                message = message[1:]

            if len(message) == 9:
                # Extract message number (4 bytes)
                original_message_ID = (
                    (message[0] << 24) |
                    (message[2] << 16) |
                    (message[4] << 8) |
                    message[6]
                )

                # Extract message (5 bytes)
                original_message = (
                    (message[1] << 32) |
                    (message[3] << 24) |
                    (message[5] << 16) |
                    (message[7] << 8) |
                    message[8]
                )

                messages_from_arduino.append([original_message_ID, original_message])
                backup_buffer.append([original_message_ID, original_message])

                # print message as binary number: ----- SERIAL MONITOR -----
                # print(f"{original_message_ID:032b} {original_message:040b}")

                full_messages += 1
            else:
                error_messages.append([message_counter, message.hex()])

            message_counter += 1

        # Backup the data every minute
        current_time = time.perf_counter()
        if current_time - last_backup_time >= backup_interval:
            last_backup_time = current_time
            if save_to_backup_csv(backup_csv_path, list(backup_buffer)):
                backup_buffer.clear()  # Clear backup buffer after confirming successful write

        await asyncio.sleep(0)  # Yield control to allow the event loop to run other tasks

    end = time.perf_counter()

    print("Signal file detected, stopping loop.")
    ser.write(b"e")  # Send end signal as a byte string

    # Call the save function
    save_to_hdf5_and_json(foldername, output_path, mouse_ID, date_time, list(messages_from_arduino), message_counter, full_messages, start, end, error_messages)

    ser.close()  # close port

def main():
    parser = argparse.ArgumentParser(description='Listen to serial port and save data.')
    parser.add_argument('--id', type=str, help='mouse ID')
    parser.add_argument('--date', type=str, help='date_time')
    parser.add_argument('--path', type=str, help='path')
    parser.add_argument('--rig', type=str, help='Rig number')
    args = parser.parse_args()

    if test == True:
        scales = Scales(rig=3)

    mouse_ID = args.id if args.id is not None else "NoID"
    date_time = args.date if args.date is not None else f"{datetime.now():%y%m%d_%H%M%S}"
    path = args.path if args.path is not None else os.path.join(os.getcwd(), f"{date_time}_{mouse_ID}")
    if args.path is None:
        os.mkdir(path)
    rig = args.rig if args.rig is not None else "3"

    try:
        asyncio.run(listen(new_mouse_ID=mouse_ID, new_date_time=date_time, new_path=path, rig=rig))
    except Exception as e:
        print("Error in main function")
        traceback.print_exc()

if __name__ == '__main__':
    main()