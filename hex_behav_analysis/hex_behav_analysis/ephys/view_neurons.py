#!/usr/bin/env python3
"""
Script to analyse spike-sorted data across a cohort.
Finds all sessions with spike-sorted data and counts good neurons and MUA per mouse and date.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import numpy as np
from collections import defaultdict
import json

# Import the cohort folder utility
from hex_behav_analysis.utils.Cohort_folder import Cohort_folder


def analyse_spikesorted_sessions(cohort_directory):
    """
    Analyse all sessions in a cohort that have spike-sorted data.
    
    Parameters
    ----------
    cohort_directory : str or Path
        Path to the cohort directory
    
    Returns
    -------
    dict
        Dictionary containing summary statistics organised by mouse
    """
    # Initialise cohort with ephys data scanning enabled
    print(f"Loading cohort from: {cohort_directory}")
    cohort = Cohort_folder(
        cohort_directory,
        OEAB_legacy=False,
        ephys_data=True,
        use_existing_cohort_info=False
    )
    
    # Dictionary to store results organised by mouse
    results = defaultdict(lambda: {
        'sessions': [],
        'total_good_units': 0,
        'total_mua_units': 0,
        'session_details': []
    })
    
    # Iterate through all mice in the cohort
    for mouse_id in cohort.cohort["mice"]:
        print(f"\nProcessing mouse: {mouse_id}")
        
        # Iterate through all sessions for this mouse
        for session_id in cohort.cohort["mice"][mouse_id]["sessions"]:
            session_data = cohort.cohort["mice"][mouse_id]["sessions"][session_id]
            
            # Check if this session has spike-sorter output
            if "spikesorter_output" in session_data:
                spikesorter_info = session_data["spikesorter_output"]
                
                if spikesorter_info.get("has_spikesorter_output", False):
                    # Extract session date from session ID (format: YYMMDD_HHMMSS_mouseID)
                    session_date = session_id[:6]  # YYMMDD
                    session_datetime = datetime.strptime(session_date, "%y%m%d")
                    formatted_date = session_datetime.strftime("%Y-%m-%d")
                    
                    # Path to the phy folder
                    phy_path = Path(spikesorter_info["spikesorter_path"])
                    
                    # Count good units and MUA
                    unit_counts = count_units_by_type(phy_path)
                    good_unit_count = unit_counts['good']
                    mua_unit_count = unit_counts['mua']
                    
                    # Only store session information if there's at least one good unit or MUA
                    if good_unit_count > 0 or mua_unit_count > 0:
                        session_info = {
                            'session_id': session_id,
                            'date': formatted_date,
                            'good_units': good_unit_count,
                            'mua_units': mua_unit_count,
                            'phy_path': str(phy_path)
                        }
                        
                        results[mouse_id]['sessions'].append(session_id)
                        results[mouse_id]['total_good_units'] += good_unit_count
                        results[mouse_id]['total_mua_units'] += mua_unit_count
                        results[mouse_id]['session_details'].append(session_info)
                        
                        print(f"  Session {session_id}: {good_unit_count} good units, {mua_unit_count} MUA")
                    else:
                        print(f"  Session {session_id}: No good units or MUA found (skipping)")
    
    return dict(results)


def count_units_by_type(phy_folder_path):
    """
    Count the number of units by type (good, mua, noise) in a Phy folder.
    
    Parameters
    ----------
    phy_folder_path : Path
        Path to the phy folder containing cluster_group.tsv
    
    Returns
    -------
    dict
        Dictionary with counts for each unit type
    """
    cluster_group_file = phy_folder_path / "cluster_group.tsv"
    
    # Initialise counts
    unit_counts = {
        'good': 0,
        'mua': 0,
        'noise': 0
    }
    
    if not cluster_group_file.exists():
        print(f"    Warning: cluster_group.tsv not found at {cluster_group_file}")
        return unit_counts
    
    try:
        # Read the cluster groups file
        cluster_groups = pd.read_csv(cluster_group_file, sep='\t')
        
        # Count units by type
        for group_type in ['good', 'mua', 'noise']:
            count = len(cluster_groups[cluster_groups['group'] == group_type])
            unit_counts[group_type] = count
        
        return unit_counts
        
    except Exception as e:
        print(f"    Error reading cluster groups: {e}")
        return unit_counts


def print_summary(results):
    """
    Print a formatted summary of the spike-sorted data analysis.
    
    Parameters
    ----------
    results : dict
        Results dictionary from analyse_spikesorted_sessions
    """
    print("\n" + "="*80)
    print("SPIKE-SORTED DATA SUMMARY")
    print("="*80)
    
    total_sessions = 0
    total_good_units = 0
    total_mua_units = 0
    
    for mouse_id, mouse_data in sorted(results.items()):
        if mouse_data['session_details']:  # Only print if mouse has spike-sorted sessions
            print(f"\nMouse: {mouse_id}")
            print(f"  Total good units across all sessions: {mouse_data['total_good_units']}")
            print(f"  Total MUA units across all sessions: {mouse_data['total_mua_units']}")
            print(f"  Number of sessions with units: {len(mouse_data['session_details'])}")
            print(f"\n  Sessions (only showing those with ≥1 good unit or MUA):")
            
            # Sort sessions by date
            sorted_sessions = sorted(mouse_data['session_details'], key=lambda x: x['date'])
            
            for session in sorted_sessions:
                print(f"    {session['date']} - {session['session_id']}: "
                      f"{session['good_units']} good units, {session['mua_units']} MUA")
            
            total_sessions += len(mouse_data['session_details'])
            total_good_units += mouse_data['total_good_units']
            total_mua_units += mouse_data['total_mua_units']
    
    print("\n" + "-"*80)
    print(f"TOTAL: {total_sessions} sessions with units")
    print(f"       {total_good_units} good units total")
    print(f"       {total_mua_units} MUA units total")
    print("="*80)


def create_summary_dataframe(results):
    """
    Create a pandas DataFrame summarising the spike-sorted data.
    
    Parameters
    ----------
    results : dict
        Results dictionary from analyse_spikesorted_sessions
    
    Returns
    -------
    pd.DataFrame
        DataFrame with columns: mouse_id, session_id, date, good_units, mua_units
    """
    data_rows = []
    
    for mouse_id, mouse_data in results.items():
        for session in mouse_data['session_details']:
            data_rows.append({
                'mouse_id': mouse_id,
                'session_id': session['session_id'],
                'date': session['date'],
                'good_units': session['good_units'],
                'mua_units': session['mua_units'],
                'total_units': session['good_units'] + session['mua_units'],
                'phy_path': session['phy_path']
            })
    
    df = pd.DataFrame(data_rows)
    
    # Sort by mouse and date
    if not df.empty:
        df = df.sort_values(['mouse_id', 'date'])
    
    return df


def main():
    """
    Main function to run the spike-sorted data analysis.
    """
    # Define cohort directory
    cohort_directory = "/cephfs2/srogers/Behaviour/2504_pitx_ephys_cohort"
    
    # Analyse spike-sorted sessions
    results = analyse_spikesorted_sessions(cohort_directory)
    
    # Print summary
    print_summary(results)
    
    # Create and save summary DataFrame
    df = create_summary_dataframe(results)
    
    if not df.empty:
        # Save to CSV
        output_file = Path(cohort_directory) / "spike_sorted_summary.csv"
        df.to_csv(output_file, index=False)
        print(f"\nSummary saved to: {output_file}")
        
        # Print some additional statistics
        print("\nAdditional Statistics:")
        print(f"  Sessions with units: {len(df)}")
        print(f"  Average good units per session: {df['good_units'].mean():.1f}")
        print(f"  Average MUA units per session: {df['mua_units'].mean():.1f}")
        print(f"  Average total units per session: {df['total_units'].mean():.1f}")
        print(f"  Good units range: {df['good_units'].min()} - {df['good_units'].max()}")
        print(f"  MUA units range: {df['mua_units'].min()} - {df['mua_units'].max()}")
        
        # Group by mouse
        mouse_summary = df.groupby('mouse_id').agg({
            'session_id': 'count',
            'good_units': ['sum', 'mean'],
            'mua_units': ['sum', 'mean'],
            'total_units': ['sum', 'mean']
        })
        mouse_summary.columns = [
            'n_sessions',
            'total_good_units', 'avg_good_units_per_session',
            'total_mua_units', 'avg_mua_units_per_session',
            'total_all_units', 'avg_all_units_per_session'
        ]
        
        print("\nPer-mouse summary:")
        print(mouse_summary)
        
        # Calculate proportion of good units vs MUA
        print("\nUnit type proportions:")
        total_good = df['good_units'].sum()
        total_mua = df['mua_units'].sum()
        total_all = total_good + total_mua
        if total_all > 0:
            print(f"  Good units: {total_good}/{total_all} ({100*total_good/total_all:.1f}%)")
            print(f"  MUA units: {total_mua}/{total_all} ({100*total_mua/total_all:.1f}%)")
    else:
        print("\nNo spike-sorted sessions found in the cohort.")


if __name__ == "__main__":
    main()