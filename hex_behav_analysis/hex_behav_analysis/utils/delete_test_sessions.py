#!/usr/bin/env python3
"""
Script to delete test session folders from an ephys cohort.

This script creates a Cohort_folder object, identifies all sessions with 'test' 
in their session ID, and deletes the corresponding folders after confirmation.
Includes safety features like dry-run mode and detailed confirmation prompts.
"""

from pathlib import Path
import shutil
import sys

# Import the Cohort_folder class

from hex_behav_analysis.utils.Cohort_folder import Cohort_folder



def find_test_sessions(cohort_data):
    """
    Find all sessions that have 'test' in their session ID.
    
    Parameters
    ----------
    cohort_data : dict
        The cohort dictionary from Cohort_folder object
        
    Returns
    -------
    list
        List of dictionaries containing test session information
    """
    test_sessions = []
    
    # Iterate through all mice and sessions
    for mouse_id, mouse_data in cohort_data.get("mice", {}).items():
        for session_id, session_data in mouse_data.get("sessions", {}).items():
            # Check if 'test' is in the session ID (case-insensitive)
            if 'test' in session_id.lower():
                session_info = {
                    'mouse_id': mouse_id,
                    'session_id': session_id,
                    'directory': session_data.get('directory'),
                    'phase': session_data.get('raw_data', {}).get('session_metadata', {}).get('phase', 'Unknown'),
                    'has_ephys': session_data.get('ephys_data', {}).get('has_ephys_data', False),
                    'has_spikesorter': session_data.get('spikesorter_output', {}).get('has_spikesorter_output', False)
                }
                test_sessions.append(session_info)
    
    return test_sessions


def display_sessions_to_delete(test_sessions):
    """
    Display detailed information about sessions that will be deleted.
    
    Parameters
    ----------
    test_sessions : list
        List of test session dictionaries
    """
    print("\n" + "="*80)
    print("TEST SESSIONS FOUND:")
    print("="*80 + "\n")
    
    if not test_sessions:
        print("No test sessions found.")
        return
    
    # Group by mouse for better organisation
    sessions_by_mouse = {}
    for session in test_sessions:
        mouse_id = session['mouse_id']
        if mouse_id not in sessions_by_mouse:
            sessions_by_mouse[mouse_id] = []
        sessions_by_mouse[mouse_id].append(session)
    
    total_size = 0
    
    for mouse_id, sessions in sessions_by_mouse.items():
        print(f"\nMouse: {mouse_id}")
        print("-" * 40)
        
        for i, session in enumerate(sessions, 1):
            print(f"\n  {i}. Session ID: {session['session_id']}")
            print(f"     Directory: {session['directory']}")
            print(f"     Phase: {session['phase']}")
            print(f"     Has ephys data: {session['has_ephys']}")
            print(f"     Has spikesorter output: {session['has_spikesorter']}")
            
            # Calculate folder size
            if session['directory'] and Path(session['directory']).exists():
                folder_size = calculate_folder_size(Path(session['directory']))
                print(f"     Folder size: {format_bytes(folder_size)}")
                total_size += folder_size
    
    print(f"\n{'='*80}")
    print(f"Total sessions to delete: {len(test_sessions)}")
    print(f"Total disk space to be freed: {format_bytes(total_size)}")
    print("="*80)


def calculate_folder_size(folder_path):
    """
    Calculate the total size of a folder and its contents.
    
    Parameters
    ----------
    folder_path : Path
        Path to the folder
        
    Returns
    -------
    int
        Total size in bytes
    """
    total_size = 0
    try:
        for item in folder_path.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
    except Exception as e:
        print(f"Warning: Could not calculate size for {folder_path}: {e}")
    return total_size


def format_bytes(size):
    """
    Format bytes into human-readable string.
    
    Parameters
    ----------
    size : int
        Size in bytes
        
    Returns
    -------
    str
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def delete_sessions(test_sessions, dry_run=True):
    """
    Delete the test session folders.
    
    Parameters
    ----------
    test_sessions : list
        List of test session dictionaries
    dry_run : bool
        If True, only simulate deletion without actually deleting
        
    Returns
    -------
    tuple
        (successful_deletions, failed_deletions)
    """
    successful_deletions = []
    failed_deletions = []
    
    for session in test_sessions:
        session_path = Path(session['directory'])
        
        if not session_path.exists():
            print(f"Warning: Directory does not exist: {session_path}")
            failed_deletions.append((session, "Directory not found"))
            continue
        
        try:
            if dry_run:
                print(f"[DRY RUN] Would delete: {session_path}")
            else:
                print(f"Deleting: {session_path}")
                shutil.rmtree(session_path)
                print(f"Successfully deleted: {session_path}")
            successful_deletions.append(session)
        except Exception as e:
            print(f"Error deleting {session_path}: {e}")
            failed_deletions.append((session, str(e)))
    
    return successful_deletions, failed_deletions


def main():
    """
    Main function to delete test sessions from cohort.
    """
    # Define the cohort directory path
    cohort_directory = r"/cephfs2/dwelch/Behaviour/November_cohort/Training"
    
    # Create the Cohort_folder object
    print(f"Loading cohort from: {cohort_directory}")
    print("This may take a few moments as it scans the data...")
    
    try:
        cohort = Cohort_folder(
            cohort_directory,
            OEAB_legacy=False,
            use_existing_cohort_info=False,
            ephys_data=False,
            ignore_tests=False  # Important: We want to include test sessions
        )
    except Exception as e:
        print(f"Error creating Cohort_folder object: {e}")
        sys.exit(1)
    
    # Find all test sessions
    test_sessions = find_test_sessions(cohort.cohort)
    
    if not test_sessions:
        print("\nNo test sessions found in the cohort.")
        sys.exit(0)
    
    # Display sessions to be deleted
    display_sessions_to_delete(test_sessions)
    
    # First confirmation
    print("\n" + "!"*80)
    print("WARNING: This operation will permanently delete the above directories!")
    print("!"*80)
    
    confirm = input("\nDo you want to proceed? Type 'DELETE' to confirm: ")
    
    if confirm != 'DELETE':
        print("Operation cancelled.")
        sys.exit(0)
    
    # Dry run first
    print("\n" + "="*80)
    print("DRY RUN - Simulating deletion:")
    print("="*80 + "\n")
    
    successful_dry, failed_dry = delete_sessions(test_sessions, dry_run=True)
    
    print(f"\nDry run complete: {len(successful_dry)} would be deleted, {len(failed_dry)} would fail")
    
    # Final confirmation
    final_confirm = input("\nProceed with ACTUAL deletion? Type 'YES DELETE' to confirm: ")
    
    if final_confirm != 'YES DELETE':
        print("Operation cancelled.")
        sys.exit(0)
    
    # Actual deletion
    print("\n" + "="*80)
    print("PERFORMING ACTUAL DELETION:")
    print("="*80 + "\n")
    
    successful, failed = delete_sessions(test_sessions, dry_run=False)
    
    # Final report
    print("\n" + "="*80)
    print("DELETION COMPLETE:")
    print("="*80)
    print(f"\nSuccessfully deleted: {len(successful)} sessions")
    print(f"Failed to delete: {len(failed)} sessions")
    
    if failed:
        print("\nFailed deletions:")
        for session, error in failed:
            print(f"  - {session['session_id']}: {error}")
    
    # Save a log of what was deleted
    log_file = Path(cohort_directory) / "deleted_test_sessions_log.txt"
    with open(log_file, 'w') as f:
        f.write("Test Sessions Deletion Log\n")
        f.write(f"Cohort: {cohort_directory}\n")
        f.write(f"Date: {cohort.cohort.get('Time refreshed', 'Unknown')}\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Successfully deleted ({len(successful)}):\n")
        for session in successful:
            f.write(f"  - {session['session_id']} ({session['directory']})\n")
        
        f.write(f"\nFailed to delete ({len(failed)}):\n")
        for session, error in failed:
            f.write(f"  - {session['session_id']}: {error}\n")
    
    print(f"\nDeletion log saved to: {log_file}")


if __name__ == "__main__":
    main()