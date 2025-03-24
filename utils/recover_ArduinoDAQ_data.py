import csv
import h5py
import numpy as np
from pathlib import Path
import argparse

def convert_csv_to_h5(backup_csv_path):
    channel_indices = (
        "SPOT2", "SPOT3", "SPOT4", "SPOT5", "SPOT6", "SPOT1", "SENSOR6", "SENSOR1",
        "SENSOR5", "SENSOR2", "SENSOR4", "SENSOR3", "BUZZER4", "LED_3", "LED_4",
        "BUZZER3", "BUZZER5", "LED_2", "LED_5", "BUZZER2", "BUZZER6", "LED_1",
        "LED_6", "BUZZER1", "VALVE4", "VALVE3", "VALVE5", "VALVE2", "VALVE6",
        "VALVE1", "GO_CUE", "NOGO_CUE", "CAMERA", "LASER", 
        "blank3", "blank4", "blank5", "blank6", "blank7", "blank8"
    )

    message_ids = []
    message_data = []

    # Read data from CSV backup
    with open(backup_csv_path, 'r') as csvfile:
        csv_reader = csv.reader(csvfile)
        for row in csv_reader:
            message_ids.append(int(row[0]))
            message_data.append(int(row[1]))

    message_ids = np.array(message_ids, dtype=np.uint32)
    message_data = np.array(message_data, dtype=np.uint64)

    num_channels = len(channel_indices)
    num_messages = len(message_data)

    # Create a 2D NumPy array to hold the channel data
    channel_data_array = np.zeros((num_messages, num_channels), dtype=np.uint8)

    # Convert message data to binary and populate channel_data_array
    for i, message in enumerate(message_data):
        binary_message = np.array(list(np.binary_repr(message, width=num_channels)), dtype=np.uint8)
        binary_message = binary_message[::-1]  # Reverse bits to align LSB with first channel
        channel_data_array[i] = binary_message

    # Estimate timestamps for each message (assuming uniform spacing for now):
    timestamps = np.linspace(0, num_messages, num_messages)

    # Prepare HDF5 file
    output_h5_path = Path(str(backup_csv_path).replace('backup', 'ArduinoDAQ')).with_suffix('.h5')
    with h5py.File(output_h5_path, 'w') as h5f:
        # Save metadata as attributes
        h5f.attrs['file_name'] = output_h5_path.stem
        h5f.attrs['No_of_messages'] = num_messages

        # Save message IDs
        h5f.create_dataset('message_ids', data=message_ids, compression='gzip')

        h5f.create_dataset('timestamps', data=timestamps, compression='gzip')

        # Save channel data under a group
        channel_group = h5f.create_group('channel_data')
        for idx, channel in enumerate(channel_indices):
            channel_group.create_dataset(channel, data=channel_data_array[:, idx], compression='gzip')

def main():
    csv_path = Path(r"E:\September_cohort_ArduinoDAQ\241017_151131\241017_151132_wtjx249-4b\241017_151132_wtjx249-4b-backup.csv")

    convert_csv_to_h5(csv_path)

if __name__ == '__main__':
    main()