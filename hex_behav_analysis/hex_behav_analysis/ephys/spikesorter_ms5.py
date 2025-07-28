"""
Spike sorting pipeline for processing tetrode recordings using MountainSort5.

This module provides functionality to preprocess ephys data and perform spike sorting
on tetrode recordings from Axona systems.
"""

import os
import shutil
import numpy as np
from pathlib import Path
import configparser
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import warnings
import logging

import spikeinterface as si
import spikeinterface.extractors as se
import spikeinterface.preprocessing as spre
import spikeinterface.sorters as ss
import spikeinterface.postprocessing as spost
import spikeinterface.qualitymetrics as sqm
import spikeinterface.exporters as sexp

from probeinterface import read_probeinterface


def parse_axona_scaling(set_file_path):
    """
    Parse Axona .set file to extract ADC scaling parameters.
    
    Parameters
    ----------
    set_file_path : Path
        Path to the .set file
        
    Returns
    -------
    tuple
        (adc_fullscale_mv, channel_gains) where channel_gains is a dict
    """
    config = configparser.ConfigParser()
    
    with open(set_file_path, 'r') as f:
        lines = f.readlines()
    
    adc_fullscale_mv = None
    channel_gains = {}
    
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 2:
            if parts[0] == 'ADC_fullscale_mv':
                adc_fullscale_mv = float(parts[1])
            elif parts[0].startswith('gain_ch_'):
                ch_num = int(parts[0].split('_')[2])
                channel_gains[ch_num] = float(parts[1])
    
    return adc_fullscale_mv, channel_gains


def preprocess_recording(recording):
    """
    Apply preprocessing pipeline optimised for MountainSort5 on tetrode recordings.
    
    Parameters
    ----------
    recording : BaseRecording
        Raw recording to preprocess
        
    Returns
    -------
    BaseRecording
        Preprocessed recording ready for spike sorting
    """
    print("Starting preprocessing pipeline for MountainSort...")
    
    # Step 1: Bandpass filter (300-6000 Hz for MountainSort)
    print("Step 1: Applying bandpass filter (300-6000 Hz)...")
    recording_preprocessed = spre.bandpass_filter(
        recording, 
        freq_min=300.0, 
        freq_max=6000.0,
        margin_ms=5.0
    )
    
    # Step 2: Detect bad channels
    print("Step 2: Detecting bad channels...")
    bad_channel_ids, channel_labels = spre.detect_bad_channels(
        recording_preprocessed,
        method='mad',
        std_mad_threshold=5,
        psd_hf_threshold=0.02,
        dead_channel_threshold=-0.5,
        noisy_channel_threshold=1.0,
        outside_channel_threshold=-0.75,
        n_neighbors=3,
        seed=0,
        chunk_duration_s=0.5
    )
    
    print(f"   Found {len(bad_channel_ids)} bad channels: {bad_channel_ids}")
    
    # Step 3: Handle bad channels
    if len(bad_channel_ids) > 0:
        print("Step 3: Removing bad channels...")
        all_channel_ids = recording_preprocessed.get_channel_ids()
        good_channel_ids = [ch for ch in all_channel_ids if ch not in bad_channel_ids]
        recording_preprocessed = recording_preprocessed.channel_slice(channel_ids=good_channel_ids)
        print(f"   Continuing with {len(good_channel_ids)} channels")
    else:
        print("Step 3: No bad channels to remove")
    
    # Step 4: Common median reference
    print("Step 4: Applying common median reference...")
    recording_preprocessed = spre.common_reference(
        recording_preprocessed,
        reference='global',
        operator='median'
    )
    
    # Step 5: Remove DC offset
    print("Step 5: Removing DC offset...")
    recording_preprocessed = spre.center(
        recording_preprocessed,
        mode='median'
    )
    
    # Step 6: Whiten the data
    print("Step 6: Whitening data...")
    recording_preprocessed = spre.whiten(
        recording_preprocessed,
        dtype='float32',
        apply_mean=True,
        mode='local',
        radius_um=100.0,
        regularize=True
    )
    
    print("Preprocessing complete!")
    return recording_preprocessed


def sort_single_tetrode(tetrode_name, recording_tetrode, output_path, sorting_params, log_dir):
    """
    Sort spikes for a single tetrode using MountainSort5.
    
    Parameters
    ----------
    tetrode_name : str
        Name of the tetrode being processed
    recording_tetrode : BaseRecording
        Recording object for the specific tetrode
    output_path : Path
        Output directory for sorting results
    sorting_params : dict
        Parameters for MountainSort5
    log_dir : Path
        Directory for log files
    
    Returns
    -------
    tuple
        (tetrode_name, sorting_result, n_units, processing_time)
    """
    import logging
    import sys
    
    # Set up logging for this tetrode
    log_file = log_dir / f'tetrode_{tetrode_name}.log'
    
    # Create a logger specific to this tetrode
    logger = logging.getLogger(f'tetrode_{tetrode_name}')
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    logger.handlers = []
    
    # Create file handler
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    # Redirect stdout and stderr to capture all output
    class LoggerWriter:
        def __init__(self, logger, level):
            self.logger = logger
            self.level = level
            self.buffer = ''
            
        def write(self, message):
            if message != '\n':
                self.buffer += message
                if '\n' in self.buffer:
                    lines = self.buffer.split('\n')
                    for line in lines[:-1]:
                        if line.strip():
                            self.logger.log(self.level, line)
                    self.buffer = lines[-1]
        
        def flush(self):
            if self.buffer.strip():
                self.logger.log(self.level, self.buffer)
                self.buffer = ''
    
    # Store original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Redirect stdout and stderr
    sys.stdout = LoggerWriter(logger, logging.INFO)
    sys.stderr = LoggerWriter(logger, logging.ERROR)
    
    start_time = time.time()
    
    try:
        logger.info(f"Starting spike sorting for {tetrode_name}")
        logger.info(f"Output path: {output_path}")
        logger.info(f"Recording: {recording_tetrode.get_num_channels()} channels, "
                   f"{recording_tetrode.get_total_duration():.1f}s duration")
        
        # Run sorting
        sorting = ss.run_sorter(
            'mountainsort5',
            recording_tetrode,
            folder=output_path,
            **sorting_params
        )
        
        # Get results
        n_units = len(sorting.get_unit_ids())
        processing_time = time.time() - start_time
        
        logger.info(f"Spike sorting complete!")
        logger.info(f"Found {n_units} units in {processing_time:.1f} seconds")
        if n_units > 0:
            logger.info(f"Unit IDs: {sorting.get_unit_ids()}")
        
        return tetrode_name, sorting, n_units, processing_time
        
    except Exception as e:
        logger.error(f"ERROR during spike sorting: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return tetrode_name, None, 0, time.time() - start_time
        
    finally:
        # Restore original stdout/stderr
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
        # Close handlers
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)


def create_phy_export(sorting, recording_tetrode, tetrode_name, output_folder, available_cpus, log_dir):
    """
    Create SortingAnalyzer and export to Phy format with proper whitening matrix.
    
    This function creates a SortingAnalyzer from the sorting results and exports
    to Phy format, ensuring all required files are generated including the
    whitening matrix.
    
    Parameters
    ----------
    sorting : BaseSorting
        Sorting results from spike sorting
    recording_tetrode : BaseRecording
        Recording for this tetrode
    tetrode_name : str
        Name of the tetrode
    output_folder : Path
        Base output folder
    available_cpus : int
        Number of CPUs to use
    log_dir : Path
        Directory for log files
        
    Returns
    -------
    bool
        Success status
    """
    import logging
    import sys
    import io
    
    # Set up logging for post-processing
    log_file = log_dir / f'postprocessing_tetrode_{tetrode_name}.log'
    
    logger = logging.getLogger(f'postprocessing_{tetrode_name}')
    logger.setLevel(logging.INFO)
    logger.handlers = []
    
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Redirect stdout and stderr to capture ALL output including progress bars
    class LoggerWriter:
        def __init__(self, logger, level):
            self.logger = logger
            self.level = level
            self.buffer = ''
            
        def write(self, message):
            if message != '\n':
                self.buffer += message
                if '\n' in self.buffer:
                    lines = self.buffer.split('\n')
                    for line in lines[:-1]:
                        if line.strip():
                            self.logger.log(self.level, line)
                    self.buffer = lines[-1]
        
        def flush(self):
            if self.buffer.strip():
                self.logger.log(self.level, self.buffer)
                self.buffer = ''
        
        def isatty(self):
            return False  # This prevents progress bars from trying to use terminal features
    
    # Store original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Redirect stdout and stderr
    sys.stdout = LoggerWriter(logger, logging.INFO)
    sys.stderr = LoggerWriter(logger, logging.ERROR)
    
    try:
        tetrode_output_path = output_folder / str(tetrode_name)
        
        # Check if there are any units
        n_units = len(sorting.get_unit_ids())
        if n_units == 0:
            logger.info(f"Skipping post-processing for tetrode {tetrode_name} - no units found")
            return False
        
        logger.info(f"Starting post-processing for tetrode {tetrode_name}")
        logger.info(f"Number of units: {n_units}")
        logger.info(f"Unit IDs: {sorting.get_unit_ids()}")
        
        # Create analyser folder
        analyzer_folder = tetrode_output_path / f'sorting_analyzer_tetrode_{tetrode_name}'
        
        if analyzer_folder.exists():
            shutil.rmtree(analyzer_folder)
        
        # Suppress progress bars for cleaner logs
        si.set_global_job_kwargs(n_jobs=available_cpus, chunk_duration="1s", progress_bar=False)
        
        # Create the SortingAnalyzer
        logger.info("Creating SortingAnalyzer...")
        analyzer = si.create_sorting_analyzer(
            sorting=sorting,
            recording=recording_tetrode,
            format="binary_folder",
            folder=analyzer_folder,
            sparse=False,  # Set to False to ensure we get full channel data
            overwrite=True
        )
        
        # Compute required extensions
        logger.info("Computing required extensions...")
        
        logger.info("  - Computing random spikes...")
        analyzer.compute("random_spikes", 
                        method="uniform",
                        max_spikes_per_unit=500)
        
        logger.info("  - Computing waveforms...")
        analyzer.compute("waveforms", 
                        ms_before=1.0,
                        ms_after=2.0,
                        n_jobs=available_cpus,
                        chunk_duration='1s',
                        progress_bar=False)
        
        logger.info("  - Computing templates...")
        analyzer.compute("templates")
        
        logger.info("  - Computing noise levels...")
        analyzer.compute("noise_levels")
        
        logger.info("  - Computing principal components...")
        analyzer.compute("principal_components", 
                        n_components=3, 
                        mode='by_channel_local',
                        whiten=True)  # Ensure whitening is enabled
        
        logger.info("  - Computing spike amplitudes...")
        analyzer.compute("spike_amplitudes")
        
        logger.info("  - Computing quality metrics...")
        analyzer.compute("quality_metrics",
                        metric_names=['firing_rate', 'presence_ratio', 'isi_violation', 
                                     'amplitude_cutoff', 'snr'])
        
        # Export to Phy
        logger.info("Exporting to Phy format...")
        phy_folder = tetrode_output_path / f'phy_tetrode_{tetrode_name}'
        
        # Export with all required parameters
        sexp.export_to_phy(analyzer, 
                         output_folder=phy_folder, 
                         compute_pc_features=True,
                         compute_amplitudes=True,
                         copy_binary=True,
                         remove_if_exists=True,
                         verbose=False)
        
        # Verify whitening matrix was created
        whitening_mat_path = phy_folder / 'whitening_mat.npy'
        if not whitening_mat_path.exists():
            logger.warning("whitening_mat.npy not created by export_to_phy, creating identity matrix")
            # Create identity whitening matrix as fallback
            n_channels = recording_tetrode.get_num_channels()
            whitening_mat = np.eye(n_channels, dtype=np.float32)
            np.save(whitening_mat_path, whitening_mat)
        
        logger.info(f"Post-processing complete!")
        logger.info(f"Phy folder: {phy_folder}")
        logger.info(f"To view in Phy: phy template-gui {phy_folder / 'params.py'}")
        
        return True
        
    except Exception as e:
        logger.error(f"ERROR during post-processing: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    finally:
        # Restore original stdout/stderr
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
        # Close handlers
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)

def combine_sortings(sorting_dict, recording_dict):
    """
    Combine multiple sorting results from different tetrodes into a single sorting object.
    
    This function takes individual sorting results from each tetrode and combines them
    into a single sorting object that can be exported to Phy without issues.
    
    Parameters
    ----------
    sorting_dict : dict
        Dictionary mapping tetrode names to sorting objects
        {tetrode_name: sorting_object}
    recording_dict : dict
        Dictionary mapping tetrode names to recording objects
        {tetrode_name: recording_object}
        
    Returns
    -------
    combined_sorting : BaseSorting
        Combined sorting object with all units from all tetrodes
    combined_recording : BaseRecording
        Combined recording object with all channels from all tetrodes
    """
    import spikeinterface as si
    
    # Collect all spike trains and create unit mappings
    all_spike_trains = []
    unit_id_offset = 0
    unit_to_tetrode = {}
    new_unit_ids = []
    
    # Also collect channel information for combined recording
    all_channel_ids = []
    channel_to_tetrode = {}
    
    print("\nCombining sorting results:")
    
    for tetrode_name, sorting in sorted(sorting_dict.items()):
        if sorting is None:
            continue
            
        recording = recording_dict[tetrode_name]
        tetrode_channel_ids = recording.get_channel_ids()
        
        # Add channel mappings
        for ch_id in tetrode_channel_ids:
            all_channel_ids.append(ch_id)
            channel_to_tetrode[ch_id] = tetrode_name
        
        # Get units from this tetrode
        unit_ids = sorting.get_unit_ids()
        n_units = len(unit_ids)
        
        print(f"  Tetrode {tetrode_name}: {n_units} units")
        
        if n_units == 0:
            continue
        
        # Create new unit IDs to avoid conflicts
        for original_unit_id in unit_ids:
            # Create new unique unit ID
            new_unit_id = unit_id_offset + original_unit_id
            new_unit_ids.append(new_unit_id)
            
            # Store mapping to tetrode
            unit_to_tetrode[new_unit_id] = tetrode_name
            
            # Get spike train for this unit
            spike_train = sorting.get_unit_spike_train(original_unit_id)
            
            # Add to collection with new unit ID
            all_spike_trains.append({
                'unit_id': new_unit_id,
                'spike_train': spike_train
            })
        
        # Update offset for next tetrode
        unit_id_offset += 1000  # Large offset to keep IDs clearly separated
    
    if len(all_spike_trains) == 0:
        raise ValueError("No units found in any tetrode!")
    
    print(f"\nTotal combined units: {len(all_spike_trains)}")
    
    # Create combined sorting object
    # First, get sampling frequency from any sorting
    sampling_frequency = next(iter(sorting_dict.values())).get_sampling_frequency()
    
    # Create a NumpySorting object with all spike trains
    from spikeinterface.core import NumpySorting
    
    combined_sorting = NumpySorting.from_unit_dict(
        {st['unit_id']: st['spike_train'] for st in all_spike_trains},
        sampling_frequency=sampling_frequency
    )
    
    # Add tetrode group property to each unit
    group_property = [unit_to_tetrode[unit_id] for unit_id in combined_sorting.get_unit_ids()]
    combined_sorting.set_property('group', group_property)
    
    # Create combined recording by concatenating all tetrode recordings
    # This maintains the channel-to-tetrode mapping
    recording_list = []
    for tetrode_name in sorted(recording_dict.keys()):
        if tetrode_name in sorting_dict and sorting_dict[tetrode_name] is not None:
            recording_list.append(recording_dict[tetrode_name])
    
    # Use aggregate_channels to combine recordings
    from spikeinterface import aggregate_channels
    combined_recording = aggregate_channels(recording_list)
    
    # Set channel groups on the combined recording
    channel_groups = {}
    for ch_id in combined_recording.get_channel_ids():
        if ch_id in channel_to_tetrode:
            channel_groups[ch_id] = channel_to_tetrode[ch_id]
    
    combined_recording.set_property('group', list(channel_groups.values()))
    
    print(f"Combined recording: {combined_recording.get_num_channels()} channels")
    
    return combined_sorting, combined_recording


def process_session(session_dict, output_base_dir=None, detection_threshold=5.5, scheme='2'):
    """
    Process a single session through the spike sorting pipeline.
    
    This version sorts tetrodes in parallel for performance, then combines results
    for Phy export to avoid single-unit issues.
    
    Parameters
    ----------
    session_dict : dict
        Session dictionary from Cohort_folder containing ephys_data information
    output_base_dir : Path or str, optional
        Base directory for output. If None, uses parent directory of the .set file
    detection_threshold : float, default=5.5
        Detection threshold in standard deviations for spike detection
    scheme : str, default='2'
        MountainSort5 scheme to use ('1', '2', or '3')
        
    Returns
    -------
    dict
        Results dictionary containing processing information
    """
    start_time = time.time()
    
    # Suppress warnings
    warnings.filterwarnings('ignore')
    
    # Set global job kwargs
    cpu_count = os.cpu_count()
    system_reserved = max(4, int(cpu_count * 0.1))
    available_cpus = cpu_count - system_reserved
    
    global_job_kwargs = dict(n_jobs=available_cpus, chunk_duration="1s")
    si.set_global_job_kwargs(**global_job_kwargs)
    
    print(f"\n{'='*60}")
    print("SPIKE SORTING PIPELINE - PARALLEL WITH COMBINED EXPORT")
    print(f"{'='*60}")
    print(f"Using {available_cpus} CPUs (reserving {system_reserved} for system)")
    
    # Extract session information
    try:
        ephys_data = session_dict["ephys_data"]
        set_file = ephys_data["set"]
        probe_file = ephys_data["probe_file"]
        session_name = Path(set_file).stem
        
        print(f"\nProcessing session: {session_name}")
        print(f"Set file: {set_file}")
        print(f"Probe file: {probe_file}")
    except KeyError as e:
        print(f"ERROR: Missing required ephys_data field: {e}")
        return {
            'success': False,
            'error': f"Missing required field: {e}",
            'processing_time': time.time() - start_time
        }
    
    # Set output directory
    if output_base_dir is None:
        output_folder = Path(set_file).parent / f'spikesorter_output_{session_name}'
    else:
        output_folder = Path(output_base_dir) / session_name / 'spikesorter_output'
    
    # Clean up existing output
    if output_folder.exists():
        print(f"Removing existing output folder: {output_folder}")
        shutil.rmtree(output_folder)
    
    output_folder.mkdir(parents=True, exist_ok=True)
    
    try:
        # Load probe configuration
        print("\nLoading probe configuration...")
        probegroup = read_probeinterface(probe_file)
        print(f"Probe loaded: {probegroup.probes[0].ndim}D configuration")
        
        # Load recording
        print("\nLoading Axona recording...")
        recording = se.read_axona(set_file)
        
        # Parse scaling parameters
        adc_fullscale_mv, channel_gains = parse_axona_scaling(set_file)
        
        # Calculate scaling factors
        adc_bit_range = 2**15
        adc_to_mv = adc_fullscale_mv / adc_bit_range
        
        num_channels = recording.get_num_channels()
        channel_gains_array = np.zeros(num_channels)
        for i in range(num_channels):
            channel_gains_array[i] = channel_gains.get(i, 1.0)
        
        scaling_factors = (adc_to_mv * 1000) / channel_gains_array
        
        print(f"ADC fullscale: {adc_fullscale_mv} mV")
        print(f"Unique gains: {np.unique(channel_gains_array)}")
        
        # Apply scaling
        recording = spre.scale(
            recording,
            gain=scaling_factors,
            dtype='float32'
        )
        
        # Attach probe
        recording.set_probegroup(probegroup, in_place=True)
        
        # Verify probe attachment
        if recording.get_probegroup() is None:
            raise ValueError("Probe attachment failed!")
        
        print(f"Recording duration: {recording.get_total_duration():.1f} seconds")
        print(f"Sampling frequency: {recording.get_sampling_frequency()} Hz")
        
        # Preprocess recording
        recording_preprocessed = preprocess_recording(recording)
        
        # Get tetrode information
        print("\nDetecting tetrodes...")
        channel_groups_data = recording_preprocessed.get_channel_groups()
        
        if isinstance(channel_groups_data, dict):
            tetrode_groups = channel_groups_data
            tetrode_names = list(tetrode_groups.keys())
        else:
            tetrode_names = np.unique(channel_groups_data).tolist()
            tetrode_groups = {}
            for group_name in tetrode_names:
                channel_indices = np.where(channel_groups_data == group_name)[0]
                channel_ids = recording_preprocessed.get_channel_ids()[channel_indices]
                tetrode_groups[group_name] = channel_ids
        
        print(f"Found {len(tetrode_names)} tetrodes")
        
        # Split recording by tetrodes
        recording_by_tetrode = recording_preprocessed.split_by('group')
        
        # Calculate parallelisation strategy
        parallel_tetrodes = min(len(tetrode_names), max(1, available_cpus // 4))
        cpus_per_sorting = max(1, available_cpus // parallel_tetrodes)
        
        print(f"\nParallelisation strategy:")
        print(f"  - Processing up to {parallel_tetrodes} tetrodes in parallel")
        print(f"  - {cpus_per_sorting} CPUs allocated per tetrode")
        
        # MountainSort5 parameters
        sorting_params = dict(
            scheme=scheme,
            detect_threshold=detection_threshold,
            detect_sign=1,
            filter=False,
            whiten=False,
            snippet_T1=20,
            snippet_T2=20,
            scheme1_detect_channel_radius=50,
            scheme2_phase1_detect_channel_radius=50,
            scheme2_detect_channel_radius=50,
            scheme2_max_num_snippets_per_training_batch=10000,
            scheme2_training_duration_sec=60,
            scheme2_training_recording_sampling_mode='initial',
            n_jobs=cpus_per_sorting,
            chunk_duration='1s',
            verbose=False
        )
        
        # Create logs directory
        logs_dir = output_folder / 'logs'
        logs_dir.mkdir(exist_ok=True)
        print(f"Log files will be saved to: {logs_dir}")
        
        # Process tetrodes in parallel (KEEP YOUR EXISTING PARALLEL SORTING CODE)
        print(f"\nStarting parallel spike sorting...")
        sorting_results = {}
        total_units = 0
        
        with ProcessPoolExecutor(max_workers=parallel_tetrodes) as executor:
            future_to_tetrode = {}
            
            for tetrode_name in tetrode_names:
                recording_tetrode = recording_by_tetrode[tetrode_name]
                tetrode_output_path = output_folder / str(tetrode_name)
                
                future = executor.submit(
                    sort_single_tetrode,
                    tetrode_name,
                    recording_tetrode,
                    tetrode_output_path,
                    sorting_params,
                    logs_dir
                )
                future_to_tetrode[future] = tetrode_name
            
            # Process completed sortings
            for future in as_completed(future_to_tetrode):
                tetrode_name, sorting, n_units, proc_time = future.result()
                
                if sorting is not None:
                    sorting_results[tetrode_name] = {
                        'sorting': sorting,
                        'n_units': n_units,
                        'processing_time': proc_time
                    }
                    total_units += n_units
        
        # Check if we have any units
        if total_units == 0:
            print("\nNo units found across any tetrode - skipping export")
            return {
                'success': True,
                'session_name': session_name,
                'output_folder': output_folder,
                'n_tetrodes': len(tetrode_names),
                'n_tetrodes_sorted': len(sorting_results),
                'total_units': 0,
                'processing_time': time.time() - start_time
            }
        
        # COMBINE SORTINGS FOR PHY EXPORT
        print("\n" + "="*60)
        print("COMBINING SORTING RESULTS FOR PHY EXPORT")
        print("="*60)
        
        # Extract just the sorting objects and recordings
        sorting_dict = {name: result['sorting'] for name, result in sorting_results.items()}
        
        # Combine all sortings into one
        combined_sorting, combined_recording = combine_sortings(sorting_dict, recording_by_tetrode)
        
        # Create single Phy export for all tetrodes combined
        print("\nCreating combined Phy export...")
        combined_output_path = output_folder / 'combined'
        combined_output_path.mkdir(exist_ok=True)
        
        # Create SortingAnalyzer for combined data
        analyzer_folder = combined_output_path / 'sorting_analyzer_combined'
        if analyzer_folder.exists():
            shutil.rmtree(analyzer_folder)
        
        print("Creating SortingAnalyzer for combined data...")
        
        # Set sparse to True with radius to maintain tetrode locality
        analyzer = si.create_sorting_analyzer(
            sorting=combined_sorting,
            recording=combined_recording,
            format="binary_folder",
            folder=analyzer_folder,
            sparse=True,
            method="radius",
            radius_um=100,  # This ensures sparsity respects tetrode boundaries
            overwrite=True
        )
        
        # Compute required extensions
        print("Computing required extensions...")
        
        analyzer.compute("random_spikes", 
                        method="uniform",
                        max_spikes_per_unit=500)
        
        analyzer.compute("waveforms", 
                        ms_before=1.0,
                        ms_after=2.0,
                        n_jobs=available_cpus,
                        chunk_duration='1s',
                        progress_bar=False)
        
        analyzer.compute("templates")
        analyzer.compute("noise_levels")
        
        analyzer.compute("principal_components", 
                        n_components=3, 
                        mode='by_channel_local',
                        whiten=True)
        
        analyzer.compute("spike_amplitudes")
        
        analyzer.compute("quality_metrics",
                        metric_names=['firing_rate', 'presence_ratio', 'isi_violation', 
                                     'amplitude_cutoff', 'snr'])
        
        # Export to Phy
        print("Exporting to Phy format...")
        phy_folder = combined_output_path / 'phy_combined'
        sexp.export_to_phy(analyzer, 
                         output_folder=phy_folder, 
                         compute_pc_features=True,
                         compute_amplitudes=True,
                         copy_binary=True,
                         remove_if_exists=True,
                         verbose=False)
        
        # Verify whitening matrix exists
        whitening_mat_path = phy_folder / 'whitening_mat.npy'
        if not whitening_mat_path.exists():
            print("Creating whitening matrix...")
            n_channels = combined_recording.get_num_channels()
            whitening_mat = np.eye(n_channels, dtype=np.float32)
            np.save(whitening_mat_path, whitening_mat)
        
        # Calculate total processing time
        total_processing_time = time.time() - start_time
        
        # Summary
        print("\n" + "="*60)
        print("SPIKE SORTING COMPLETE")
        print("="*60)
        print(f"Session: {session_name}")
        print(f"Total processing time: {total_processing_time:.1f} seconds")
        print(f"Total units found: {total_units}")
        print(f"Tetrodes processed: {len(sorting_results)}/{len(tetrode_names)}")
        print(f"Combined Phy export: {phy_folder}")
        print(f"Output directory: {output_folder}")
        print(f"Log files: {logs_dir}")
        
        print(f"\nTo view in Phy: phy template-gui {phy_folder / 'params.py'}")
        
        # Print summary of units per tetrode
        print("\nUnits per tetrode in combined export:")
        group_property = combined_sorting.get_property('group')
        for tetrode in sorted(set(group_property)):
            n_units = sum(1 for g in group_property if g == tetrode)
            print(f"  Tetrode {tetrode}: {n_units} units")
        
        # Return results
        return {
            'success': True,
            'session_name': session_name,
            'output_folder': output_folder,
            'n_tetrodes': len(tetrode_names),
            'n_tetrodes_sorted': len(sorting_results),
            'total_units': total_units,
            'tetrode_results': {
                name: {
                    'n_units': result['n_units'],
                    'processing_time': result['processing_time']
                }
                for name, result in sorting_results.items()
            },
            'processing_time': total_processing_time,
            'phy_export': phy_folder
        }
        
    except Exception as e:
        print(f"\nERROR: Processing failed - {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': str(e),
            'processing_time': time.time() - start_time
        }