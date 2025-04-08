import h5py
import numpy as np
import matplotlib.pyplot as plt

def plot_multiple_channels(arduino_daq_h5_path, channel_names):
    """
    Plots multiple channels from the ArduinoDAQ data as separate subplots and
    prints the sampling rate (samples per second) for each channel.
    
    Args:
        arduino_daq_h5_path (str): Path to the ArduinoDAQ .h5 file.
        channel_names (list): List of channel names to plot.
    """
    # Open the HDF5 file
    with h5py.File(arduino_daq_h5_path, 'r') as daq_h5:
        # Create figure with subplots
        fig, axes = plt.subplots(len(channel_names), 1, figsize=(12, 3*len(channel_names)))
        
        # Get timestamps once
        daq_timestamps = np.array(daq_h5['timestamps'])
        
        # Calculate total duration in seconds
        duration = daq_timestamps[-1] - daq_timestamps[0]
        
        # Handle case of single channel (axes not being array)
        if len(channel_names) == 1:
            axes = [axes]
        
        # Plot each channel
        for ax, channel in zip(axes, channel_names):
            try:
                channel_data = np.array(daq_h5['channel_data'][channel])
                
                # Calculate samples per second
                num_samples = len(channel_data)
                samples_per_second = num_samples / duration if duration > 0 else 0
                
                # Print sampling rate information
                print(f"Channel: {channel}")
                print(f"  Number of samples: {num_samples}")
                print(f"  Duration: {duration:.3f} seconds")
                print(f"  Sampling rate: {samples_per_second:.2f} samples/second")
                
                # Plot the data
                ax.plot(daq_timestamps, channel_data, label=channel)
                ax.set_ylabel('Signal')
                
                # Add sampling rate information to the legend
                ax.legend([f"{channel} ({samples_per_second:.2f} Hz)"], loc='upper right')
                
                # Only show x-label for bottom subplot
                if ax == axes[-1]:
                    ax.set_xlabel('Time (s)')
            except KeyError:
                ax.text(0.5, 0.5, f'Channel "{channel}" not found', 
                       horizontalalignment='center',
                       verticalalignment='center')
                ax.set_ylabel('N/A')
                print(f"Channel: {channel} - Not found in dataset")
    
    # Add overall title
    plt.suptitle('ArduinoDAQ Signals')
    plt.tight_layout()
    plt.show()

def main():
    # === Fill in these variables ===
    # Provide the path to your ArduinoDAQ .h5 file
    arduino_daq_h5_path = r"D:\test_output\250407_194019\250407_194025_test1\250407_194025_test1-ArduinoDAQ.h5"
    
    # List all channels you want to plot
    channel_names = ["CAMERA", "SCALES"]  # Add or modify channels as needed

    # Call the plotting function
    plot_multiple_channels(arduino_daq_h5_path, channel_names)

if __name__ == "__main__":
    main()