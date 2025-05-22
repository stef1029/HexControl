import h5py
import numpy as np
import matplotlib.pyplot as plt

def compute_pulse_stats(timestamps, signal, threshold=0.5):
    """Compute pulse timings and stats from a digital-like signal."""
    signal = np.array(signal)
    timestamps = np.array(timestamps)

    # Find where signal crosses threshold (rising and falling)
    rising_edges = np.where((signal[:-1] < threshold) & (signal[1:] >= threshold))[0] + 1
    falling_edges = np.where((signal[:-1] >= threshold) & (signal[1:] < threshold))[0] + 1

    # Sanity check: make sure rising and falling are paired
    num_pulses = min(len(rising_edges), len(falling_edges))
    rising_edges = rising_edges[:num_pulses]
    falling_edges = falling_edges[:num_pulses]

    pulse_starts = timestamps[rising_edges]
    pulse_ends = timestamps[falling_edges]
    pulse_widths = pulse_ends - pulse_starts

    ipis = np.diff(pulse_starts)

    stats = {
        'n_pulses': len(pulse_starts),
        'mean_ipi': np.mean(ipis) if len(ipis) > 0 else np.nan,
        'std_ipi': np.std(ipis) if len(ipis) > 0 else np.nan,
        'ipi_range': (np.min(ipis), np.max(ipis)) if len(ipis) > 0 else (np.nan, np.nan),
        'mean_width': np.mean(pulse_widths) if len(pulse_widths) > 0 else np.nan,
        'std_width': np.std(pulse_widths) if len(pulse_widths) > 0 else np.nan,
        'width_range': (np.min(pulse_widths), np.max(pulse_widths)) if len(pulse_widths) > 0 else (np.nan, np.nan),
    }

    return stats, pulse_starts, pulse_ends

def plot_multiple_channels(arduino_daq_h5_path, channel_names):
    with h5py.File(arduino_daq_h5_path, 'r') as daq_h5:
        fig, axes = plt.subplots(len(channel_names), 1, figsize=(12, 3*len(channel_names)))
        daq_timestamps = np.array(daq_h5['timestamps'])
        duration = daq_timestamps[-1] - daq_timestamps[0]

        if len(channel_names) == 1:
            axes = [axes]

        for ax, channel in zip(axes, channel_names):
            try:
                channel_data = np.array(daq_h5['channel_data'][channel])
                num_samples = len(channel_data)
                samples_per_second = num_samples / duration if duration > 0 else 0

                print(f"\nChannel: {channel}")
                print(f"  Number of samples: {num_samples}")
                print(f"  Duration: {duration:.3f} seconds")
                print(f"  Sampling rate: {samples_per_second:.2f} Hz")

                # Compute pulse stats
                stats, pulse_starts, pulse_ends = compute_pulse_stats(daq_timestamps, channel_data)

                print("  Pulse stats:")
                print(f"    Total pulses: {stats['n_pulses']}")
                print(f"    Mean IPI: {stats['mean_ipi']:.3f}s ± {stats['std_ipi']:.3f}")
                print(f"    IPI range: {stats['ipi_range'][0]:.3f} - {stats['ipi_range'][1]:.3f}s")
                print(f"    Mean pulse width: {stats['mean_width']:.3f}s ± {stats['std_width']:.3f}")
                print(f"    Pulse width range: {stats['width_range'][0]:.3f} - {stats['width_range'][1]:.3f}s")

                # Plot the signal
                ax.plot(daq_timestamps, channel_data, label=channel)
                ax.set_ylabel('Signal')
                ax.legend([f"{channel} ({samples_per_second:.2f} Hz)"], loc='upper right')
                
                # Only bottom gets x-label
                if ax == axes[-1]:
                    ax.set_xlabel('Time (s)')
            except KeyError:
                ax.text(0.5, 0.5, f'Channel "{channel}" not found', 
                        horizontalalignment='center',
                        verticalalignment='center')
                ax.set_ylabel('N/A')
                print(f"Channel: {channel} - Not found in dataset")

    plt.suptitle('ArduinoDAQ Signals')
    plt.tight_layout()
    plt.show()

def main():
    arduino_daq_h5_path = r"D:\test_output\250414_210108\250414_210113_test\250414_210113_test-ArduinoDAQ.h5"
    channel_names = ["CAMERA", "SCALES"]
    plot_multiple_channels(arduino_daq_h5_path, channel_names)

if __name__ == "__main__":
    main()
