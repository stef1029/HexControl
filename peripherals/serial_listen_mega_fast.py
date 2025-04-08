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
from colorama import init, Fore, Style
init()

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


async def check_signal_files(file_path_1, stop_event, rig_number):
    if test:
        def esc_key_monitor():
            keyboard.wait('esc')
            if not stop_event.is_set():
                stop_event.set()

        esc_thread = threading.Thread(target=esc_key_monitor, daemon=True)
        esc_thread.start()

    try:
        while not stop_event.is_set():
            # Check for camera completion signal
            if os.path.exists(file_path_1):
                print(Fore.YELLOW + "ArduinoDAQ:" + Style.RESET_ALL + f"Received camera end signal from: {file_path_1}")
                stop_event.set()
                break
                
            await asyncio.sleep(1)  # Check every 1s
            
    finally:
        if test:
            keyboard.unhook_all()


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

    # Create signal file path for connection status
    if rig is None:
        connection_signal_file = output_path / "arduino_connected.signal"
    else:
        connection_signal_file = output_path / f"rig_{rig}_arduino_connected.signal"

    backup_csv_path = output_path / f"{foldername}-backup.csv"

    # Configure COM port based on rig number
    if rig is None:
        COM_PORT = "COM2"
    elif rig == "1":
        COM_PORT = "COM12"
    elif rig == "2":
        COM_PORT = "COM18"
    elif rig == "3":
        COM_PORT = "COM48"
    elif rig == "4":
        COM_PORT = "COM17"
    else:
        raise ValueError("Rig number not recognised")
    
    connection_established = False
    
    try:
        print(f"Connecting to Arduino Mega on {COM_PORT}...")
        ser = serial.Serial(COM_PORT, 115200, timeout = 1)  # open serial port
        time.sleep(3)
    except serial.SerialException:
        print("Serial-listen connection not found, trying again...")
        try:
            ser = serial.Serial(COM_PORT, 115200, timeout = 1)
            time.sleep(3)
        except serial.SerialException:
            print("Failed to connect to Arduino Mega after retry.")
            return

    # Test connection by sending start signal and waiting for response
    try:
        ser.write("s".encode("utf-8"))  # send start signal to Arduino
        ser.reset_input_buffer()
        response = ser.read_until(b"s", 5)  # Wait up to 5 seconds for response
        
        if b"s" in response:
            print("Arduino Mega connection established successfully.")
            connection_established = True
            
            # Create signal file to indicate connection is established
            with open(connection_signal_file, 'w') as f:
                f.write(f"Arduino Mega connection established at {datetime.now()}")
        else:
            print(f"Arduino Mega did not respond correctly. Response: {response}")
            return
    except Exception as e:
        print(f"Error during Arduino Mega communication: {e}")
        return

    if not connection_established:
        print("Failed to establish proper connection with Arduino Mega.")
        return

    start = time.perf_counter()
    message_counter = 0
    full_messages = 0
    error_messages = []

    stop_event = asyncio.Event()
    
    # Start the task to check for signal file asynchronously with error handling
    try:
        # Path to the camera signal file based on rig number
        if rig == "1":
            signal_file_path = output_path / "rig_1_camera_finished.signal" 
        elif rig == "2":
            signal_file_path = output_path / "rig_2_camera_finished.signal" 
        elif rig == "3":
            signal_file_path = output_path / "rig_3_camera_finished.signal"
        elif rig == "4":
            signal_file_path = output_path / "rig_4_camera_finished.signal"
        else:
            signal_file_path = output_path / "camera_finished.signal"
            
        asyncio.create_task(check_signal_files(signal_file_path, stop_event, rig))
    except Exception as e:
        print(f"Error while starting signal file check task: {e}")

    backup_interval = 5  # Time in seconds to save backups
    last_backup_time = time.perf_counter()

    while not stop_event.is_set():
        if ser.in_waiting > 9:
            # Get timestamp as soon as we detect a message
            current_time = time.perf_counter() - start
            
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

                # Store message with its timestamp
                messages_from_arduino.append([original_message_ID, original_message, current_time])
                backup_buffer.append([original_message_ID, original_message, current_time])

                # Optional: Uncomment to enable serial monitor output
                # print(f"Time: {current_time:.6f} ID: {original_message_ID:032b} Data: {original_message:040b}")

                full_messages += 1
            else:
                error_messages.append([message_counter, message.hex(), current_time])
                # print(Fore.RED + "ArduinoDAQ:" + Style.RESET_ALL + f"Error: Invalid message length {len(message)}. Message: {message.hex()}")

            message_counter += 1

        # Backup the data every interval
        current_time = time.perf_counter()
        if current_time - last_backup_time >= backup_interval:
            last_backup_time = current_time
            if save_to_backup_csv(backup_csv_path, list(backup_buffer)):
                backup_buffer.clear()  # Clear backup buffer after confirming successful write

        await asyncio.sleep(0)  # Yield control to allow the event loop to run other tasks

    end = time.perf_counter()

    print(Fore.YELLOW + "ArduinoDAQ:" + Style.RESET_ALL + "Signal files detected, stopping loop.")
    
    # Send end signal multiple times to ensure it's received
    for i in range(3):
        ser.write(b"e")  # Send end signal as a byte string
        time.sleep(0.1)

    # Close the serial connection
    ser.close()  # close port

    # Call the save function
    save_to_hdf5_and_json(foldername, output_path, mouse_ID, date_time, list(messages_from_arduino), message_counter, full_messages, start, end, error_messages)

def save_to_hdf5_and_json(foldername, output_path, mouse_ID, date_time, messages_from_arduino, message_counter, full_messages, start, end, error_messages):
    message_ids = np.array([message[0] for message in messages_from_arduino], dtype=np.uint32)
    message_data = np.array([message[1] for message in messages_from_arduino], dtype=np.uint64)
    timestamps = np.array([message[2] for message in messages_from_arduino], dtype=np.float64)

    # Updated channel indices for the Mega - removed buzzers and spotlights
    channel_indices = (
        # Removed spotlights: "SPOT1", "SPOT2", "SPOT3", "SPOT4", "SPOT5", "SPOT6",
        # Removed buzzers: "BUZZER1", "BUZZER2", "BUZZER3", "BUZZER4", "BUZZER5", "BUZZER6",
        "SENSOR6", "SENSOR1", "SENSOR5", "SENSOR2", "SENSOR4", "SENSOR3", 
        "LED_3", "LED_4", "LED_2", "LED_5", "LED_1", "LED_6", 
        "VALVE4", "VALVE3", "VALVE5", "VALVE2", "VALVE6", "VALVE1", 
        "GO_CUE", "NOGO_CUE", "CAMERA", "SCALES", "LASER"
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

    # Prepare HDF5 file
    save_file_name = f"{foldername}-ArduinoDAQ.h5"
    output_file = output_path / save_file_name

    # Prepare JSON file
    json_file_name = f"{foldername}-ArduinoDAQ.json"
    json_output_file = output_path / json_file_name

    try:
        reliability = (full_messages / message_counter) * 100
    except ZeroDivisionError:
        reliability = 0

    binary_list = [''.join(str(bit) for bit in row) for row in channel_data_array]

    data_to_save = {
        "mouse_ID": mouse_ID,
        "date_time": date_time,
        "time": str(datetime.now()),
        "No_of_messages": num_messages,
        "reliability": reliability,
        "time_taken": end - start,
        "messages_per_second": num_messages / (end - start),
        "message_ids": message_ids.tolist(),
        "timestamps": timestamps.tolist(),
        "channel_data_raw": binary_list,
        "error_messages": error_messages
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
        h5f.attrs['reliability'] = reliability
        h5f.attrs['time_taken'] = end - start
        h5f.attrs['messages_per_second'] = num_messages / (end - start)

        # Save message IDs and timestamps
        h5f.create_dataset('message_ids', data=message_ids, compression='gzip')
        h5f.create_dataset('timestamps', data=timestamps, compression='gzip')

        # Save channel data under a group
        channel_group = h5f.create_group('channel_data')
        for idx, channel in enumerate(channel_indices):
            channel_group.create_dataset(channel, data=channel_data_array[:, idx], compression='gzip')

        if error_messages:
            error_messages_str = [str(err_msg) for err_msg in error_messages]
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

def main():
    """
    Command line Args:
    --id: mouse ID (default: NoID)
    --date: date_time (default: current date_time)
    --path: path (default: current directory)
    --rig: rig number (default: 3)
    """
    # Make args globally accessible for the check_signal_files function
    global args
    
    parser = argparse.ArgumentParser(description='Listen to serial port and save data.')
    parser.add_argument('--id', type=str, help='mouse ID')
    parser.add_argument('--date', type=str, help='date_time')
    parser.add_argument('--path', type=str, help='path')
    parser.add_argument('--rig', type=str, default='3', help='Rig number (1-4)')
    args = parser.parse_args()

    mouse_ID = args.id if args.id is not None else "NoID"
    date_time = args.date if args.date is not None else f"{datetime.now():%y%m%d_%H%M%S}"
    path = args.path if args.path is not None else os.path.join(os.getcwd(), f"{date_time}_{mouse_ID}")
    if args.path is None:
        os.mkdir(path)

    try:
        asyncio.run(listen(new_mouse_ID=mouse_ID, new_date_time=date_time, new_path=path, rig=args.rig))
    except Exception as e:
        print("Error in main function")
        traceback.print_exc()
        input("ArduinoDAQ error, take note of printed statement. Press Enter to close.")

    print(Fore.YELLOW + "ArduinoDAQ:" + Style.RESET_ALL + "ArduinoDAQ finished.")

if __name__ == '__main__':
    main()