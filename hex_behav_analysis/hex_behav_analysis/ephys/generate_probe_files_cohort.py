#!/usr/bin/env python3
"""
Generate tetrode probe configuration files for cohort sessions.

This script iterates through all sessions in a cohort, checks if probe files exist,
and generates appropriate tetrode configuration files based on mouse ID.
"""

import json
from pathlib import Path
from probeinterface import ProbeGroup, generate_tetrode, write_probeinterface
import sys
import os

# Add the hex_behav_analysis module to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hex_behav_analysis.utils.Cohort_folder import Cohort_folder


def create_tetrode_probe_file(num_tetrodes, output_path):
    """
    Create a probe configuration file for the specified number of tetrodes.
    
    :param num_tetrodes: Number of tetrodes (4 or 8)
    :param output_path: Path where the JSON file should be saved
    """
    probegroup = ProbeGroup()
    
    if num_tetrodes == 4:
        # Configuration for 4 tetrodes (16 channels)
        for i in range(4):
            # Generate a standard tetrode in 2D
            probe = generate_tetrode(r=15)  # r is the radius of the tetrode bundle in micrometres
            
            # Position tetrodes in a line with 250 micrometre spacing
            probe.move([i * 250, 0])
            
            # Add to group
            probegroup.add_probe(probe)
        
        # Set channel indices (0-15 for 4 tetrodes)
        probegroup.set_global_device_channel_indices(list(range(16)))
        
    elif num_tetrodes == 8:
        # Configuration for 8 tetrodes (32 channels)
        # Arrange 8 tetrodes in a 2x4 grid
        tetrode_index = 0
        for row in range(2):
            for col in range(4):
                # Generate tetrode in 2D
                probe = generate_tetrode(r=15)
                
                # Position in grid with 250 micrometre spacing
                x_pos = col * 250
                y_pos = row * 250
                probe.move([x_pos, y_pos])
                
                # Add to group
                probegroup.add_probe(probe)
                tetrode_index += 1
        
        # Set channel indices (0-31 for 8 tetrodes)
        probegroup.set_global_device_channel_indices(list(range(32)))
    
    else:
        raise ValueError(f"Unsupported number of tetrodes: {num_tetrodes}. Only 4 or 8 are supported.")
    
    # Save the configuration
    write_probeinterface(str(output_path), probegroup)


def process_cohort_probe_files(cohort_directory):
    """
    Process all sessions in a cohort and generate missing probe files.
    
    :param cohort_directory: Path to the cohort directory
    """
    # Define mouse channel configurations
    mouse_configs = {
        # 16 channels (4 tetrodes) - tetrodes 1-4 active
        'mtaq13-3a': {
            'channels': 16,
            'tetrodes': 4,
            'active_tetrodes': list(range(1, 5))
        },
        # 32 channels (8 tetrodes) - tetrodes 1-8 active
        'mtaq11-3b': {
            'channels': 32,
            'tetrodes': 8,
            'active_tetrodes': list(range(1, 9))
        },
        'mtaq14-1j': {
            'channels': 32,
            'tetrodes': 8,
            'active_tetrodes': list(range(1, 9))
        },
        'mtaq14-1i': {
            'channels': 32,
            'tetrodes': 8,
            'active_tetrodes': list(range(1, 9))
        }
    }
    
    # Load cohort data
    print(f"Loading cohort from: {cohort_directory}")
    cohort = Cohort_folder(cohort_directory,
                          OEAB_legacy=False,
                          use_existing_cohort_info=False,
                          ephys_data=True)
    
    # Statistics
    total_sessions = 0
    sessions_with_probe = 0
    sessions_generated = 0
    sessions_skipped = 0
    
    # Iterate through all mice and sessions
    for mouse_id in cohort.cohort["mice"]:
        print(f"\nProcessing mouse: {mouse_id}")
        
        for session_id in cohort.cohort["mice"][mouse_id]["sessions"]:
            total_sessions += 1
            session_data = cohort.cohort["mice"][mouse_id]["sessions"][session_id]
            
            # Check if ephys data exists for this session
            if "ephys_data" not in session_data:
                print(f"  Session {session_id}: No ephys data found, skipping")
                sessions_skipped += 1
                continue
            
            ephys_data = session_data["ephys_data"]
            
            # Check if probe file already exists
            if ephys_data.get("probe_file") is not None:
                print(f"  Session {session_id}: Probe file already exists at {ephys_data['probe_file']}")
                sessions_with_probe += 1
                continue
            
            # Check if this mouse has a known configuration
            if mouse_id not in mouse_configs:
                print(f"  Session {session_id}: Mouse {mouse_id} not in configuration list, skipping")
                sessions_skipped += 1
                continue
            
            # Get the number of tetrodes for this mouse
            num_tetrodes = mouse_configs[mouse_id]['tetrodes']
            
            # Determine the group folder (parent of session folder)
            session_folder = Path(session_data["directory"])
            group_folder = session_folder.parent
            
            # Generate the probe file name
            probe_filename = f"tetrodes_{num_tetrodes}.json"
            probe_filepath = group_folder / probe_filename
            
            # Create the probe file
            try:
                print(f"  Session {session_id}: Generating {probe_filename} in {group_folder}")
                create_tetrode_probe_file(num_tetrodes, probe_filepath)
                sessions_generated += 1
                print(f"    ✅ Successfully created probe file")
            except Exception as e:
                print(f"    ❌ Error creating probe file: {str(e)}")
                sessions_skipped += 1
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total sessions processed: {total_sessions}")
    print(f"Sessions with existing probe files: {sessions_with_probe}")
    print(f"Probe files generated: {sessions_generated}")
    print(f"Sessions skipped: {sessions_skipped}")
    print("="*60)


def main():
    """
    Main function to process cohort and generate probe files.
    """
    # Set the cohort directory
    cohort_directory = r"/cephfs2/srogers/Behaviour/2504_pitx_ephys_cohort"
    
    # Process the cohort
    process_cohort_probe_files(cohort_directory)


if __name__ == "__main__":
    main()