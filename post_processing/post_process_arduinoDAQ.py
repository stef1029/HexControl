import subprocess
import time
from pathlib import Path
import multiprocessing as mp
import os
import cv2 as cv
import struct
import logging
import sys
import paramiko
import json
from datetime import datetime
from typing import Dict, Union, List, Optional

from hex_behav_analysis.utils.Cohort_folder import Cohort_folder 
from hex_behav_analysis.utils.analysis_manager_arduinoDAQ import Process_Raw_Behaviour_Data  # Import your analysis manager function
from hex_behav_analysis.utils.recover_crashed_sessions_test import recover_crashed_sessions
from hex_behav_analysis.ephys import get_axona_events

# Import the video processing functions
from hex_behav_control.archive.bmp_to_video import bmp_to_avi_MP, clear_BMP_files
from hex_behav_control.post_processing.bin_to_vid_MP import convert_binary_to_video, cleanup_binary_files, delete_binary_files


def process_ephys_data(cohort_directory, target_pin=0):
    """
    Process electrophysiology data by finding .inp files in the parent directories
    of all session directories within a cohort.
    
    Args:
        cohort_directory (Path): The root directory containing cohort data.
        target_pin (int): The pin number to extract events for (default: 0).
        
    Returns:
        int: Number of .inp files processed
    """
    from pathlib import Path
    from hex_behav_analysis.ephys import get_axona_events
    from hex_behav_analysis.utils.Cohort_folder import Cohort_folder
    
    print(f"Processing ephys data in cohort: {cohort_directory}")
    
    # Load cohort directory information
    directory_info = Cohort_folder(cohort_directory, 
                                  multi=True, 
                                  plot=False, 
                                  OEAB_legacy=False,
                                  ignore_tests=False).cohort
                                  
    processed_count = 0
    
    # Iterate over each mouse in the directory information
    for mouse in directory_info["mice"]:
        # Iterate over each session for the mouse
        for session in directory_info["mice"][mouse]["sessions"]:
            session_data = directory_info["mice"][mouse]["sessions"][session]
            session_directory = Path(session_data["directory"])
            
            # Check for ephys data in parent folder
            parent_directory = session_directory.parent
            inp_files = list(parent_directory.glob('*.inp'))
            
            if inp_files:
                print(f"Found ephys data files for {session} in parent directory: {parent_directory}")
                print(f"Ephys data files: {[f.name for f in inp_files]}")
                
                if len(inp_files) > 0:
                    inp_file = inp_files[0]
                    try:
                        # Process the ephys data
                        get_axona_events.process_file(inp_file, session_directory, target_pin=target_pin)
                        print(f"Successfully processed ephys sync file from {inp_file} for session {session_directory.name}")
                        processed_count += 1
                    except Exception as e:
                        print(f"Error processing ephys data for {session_directory}: {e}")
    
    print(f"Completed ephys processing. Processed {processed_count} .inp files.")
    return processed_count

# Function to get a list of sessions that have unprocessed data
def get_sessions_to_process(directory_info):
    """
    Returns a list of sessions that need processing, along with the processing method.

    Args:
        directory_info (dict): A dictionary containing metadata about the mice and their sessions.

    Returns:
        list: A list of tuples, each containing the session directory, frame rate, and processing method.
    """
    sessions_to_process = []

    # Iterate over each mouse in the directory information
    for mouse in directory_info["mice"]:
        # Iterate over each session for the mouse
        for session in directory_info["mice"][mouse]["sessions"]:
            session_data = directory_info["mice"][mouse]["sessions"][session]
            session_directory = Path(session_data["directory"])

            # Determine the processing method based on the files present
            binary_files = list(session_directory.glob('*binary_video*'))
            bmp_files = list(session_directory.glob("*.bmp"))
            raw_video = session_data["raw_data"].get("raw_video", "None")

            # Load behavior data to get the FPS (frames per second)
            behaviour_data_path = session_data["raw_data"].get("behaviour_data")
            fps = 30  # Default FPS 

            if behaviour_data_path and behaviour_data_path != "None" and Path(behaviour_data_path).exists():
                try:
                    with open(behaviour_data_path, 'r') as file:
                        behaviour_data = json.load(file)
                        fps = behaviour_data.get("fps", 30)  # Default to 30 FPS if not specified
                except Exception as e:
                    # Handle any error by keeping fps as 30
                    print(f"Error loading behaviour data from {behaviour_data_path}: {e}")

            if raw_video == "None":
                if binary_files:
                    # Use new processing method
                    sessions_to_process.append((session_directory, fps, 'binary'))
                elif bmp_files:
                    # Use old processing method
                    sessions_to_process.append((session_directory, fps, 'bmp'))

    return sessions_to_process

# Function to process a single video session using the appropriate method
# def process_video_session(session_directory, fps, processing_method, num_processes=8):
#     """
#     Processes a video session by either processing BMP files or processing the binary file.

#     Args:
#         session_directory (Path): The directory containing the data for this session.
#         fps (int): The frames per second to use for the video (used for BMP method).
#         processing_method (str): The method to use for processing ('bmp' or 'binary').
#         num_processes (int): Number of processes to use for multiprocessing (for 'bmp' method).

#     Returns:
#         None
#     """

def process_video_session(session_directory, fps, processing_method, num_processes=8):
    """
    Processes a video session by either processing BMP files or processing the binary file.
    First checks if ephys data exists in the parent folder.

    Args:
        session_directory (Path): The directory containing the data for this session.
        fps (int): The frames per second to use for the video (used for BMP method).
        processing_method (str): The method to use for processing ('bmp' or 'binary').
        num_processes (int): Number of processes to use for multiprocessing (for 'bmp' method).

    Returns:
        None
    """
    # Continue with normal processing
    if processing_method == 'binary':
        # Search for the binary video file
        binary_files = list(session_directory.glob('*binary_video*'))

        if not binary_files:
            print(f"No binary video file found in {session_directory}. Skipping...")
            return

        if len(binary_files) > 1:
            print(f"Multiple binary video files found in {session_directory}. Using the first one.")

        binary_file_path = binary_files[0]

        metadata_file_path = session_directory / f"{session_directory.name}_Tracker_data.json"

        if not binary_file_path.exists():
            print(f"No binary file found in {session_directory}. Skipping...")
            return

        if not metadata_file_path.exists():
            print(f"No metadata file found in {session_directory}. Skipping...")
            return

        # Output directory (could be the session directory or another directory)
        output_directory = session_directory

        print(f"Processing session in {session_directory} using binary method...")
        try:
            # Call the convert_binary_to_video function from the new script
            success = convert_binary_to_video(str(binary_file_path), str(metadata_file_path), output_directory)
            if success:
                print(f"Successfully compressed: {binary_file_path} to AVI in {output_directory}.")
            else:
                print(f"Failed to compress {binary_file_path}.")
            
            # After successful conversion, delete the binary file if the AVI exists
            delete_binary_files(session_directory, binary_file_path)
            
        except Exception as e:
            print(f"Error processing {session_directory}: {e}")

    elif processing_method == 'bmp':
        print(f"Processing session in {session_directory} using BMP method...")
        bmp_to_avi_MP("raw", session_directory, framerate=fps, num_processes=num_processes)
        print(f"Clearing BMP files in {session_directory}...")
        clear_BMP_files(session_directory)
        print(f"Processing of {session_directory} completed successfully.")
    else:
        print(f"Unknown processing method '{processing_method}' for {session_directory}. Skipping...")


# Function to process all sessions in a cohort directory
def process_cohort_directory(cohort_directory, num_processes=8, cleanup=True):
    """
    Processes all sessions within a cohort directory by determining the appropriate method.

    Args:
        cohort_directory (str or Path): The root directory containing cohort data.
        num_processes (int): Number of processes to use for multiprocessing (for BMP processing).
        cleanup (bool): Whether to clean up binary files in sessions that already have AVI files.

    Returns:
        None
    """
    cohort_directory = Path(cohort_directory)
    # Load cohort directory information
    directory_info = Cohort_folder(cohort_directory, 
                                   multi=True, 
                                   plot=False, 
                                   OEAB_legacy=False,
                                   ignore_tests=ignore_test_sessions).cohort

    # Optionally clean up binary files in sessions that already have AVI files
    if cleanup:
        deleted_count = cleanup_binary_files(directory_info)
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} binary files from sessions with existing AVI files.")

    # Get all sessions that need processing
    sessions_to_process = get_sessions_to_process(directory_info)

    total_sessions = len(sessions_to_process)  # Calculate the total number of sessions

    # Process each session using the appropriate method
    for i, (session_directory, fps, processing_method) in enumerate(sessions_to_process, start=1):
        print(f"Processing session {i}/{total_sessions}: {session_directory}...")
        process_video_session(session_directory, fps, processing_method, num_processes=num_processes)





def sync_with_cephfs(local_dir, remote_dir):
    rsync_command = [
        "rsync", "-avz", "--progress", "--info=progress2",  # Added progress options
        local_dir,
        remote_dir
    ]
    try:
        process = subprocess.Popen(rsync_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in iter(process.stdout.readline, b''):
            print(line.decode(), end='')  # Print each line of output in real-time
        process.stdout.close()
        process.wait()
        if process.returncode == 0:
            print("\nSync completed successfully.\n")
        else:
            print(f"Error occurred during rsync: Return code {process.returncode}")
    except Exception as e:
        print(f"Error occurred during rsync: {e}")

def run_analysis_on_local(cohort_directory, refresh=False):
    total_start_time = time.perf_counter()

    # ---- Logging setup -----
    logger = logging.getLogger(__name__)        
    logger.setLevel(logging.DEBUG)
    log_dir = cohort_directory / 'logs'        
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = log_dir / 'error.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.ERROR)     
    console_handler = logging.StreamHandler()       
    console_handler.setLevel(logging.DEBUG)  
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')        
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)     
    logger.addHandler(console_handler)
    # --------------------------

    Cohort = Cohort_folder(cohort_directory, multi=True, OEAB_legacy = False, ignore_tests=ignore_test_sessions)
    directory_info = Cohort.cohort

    sessions_to_process = []

    for mouse in directory_info["mice"]:
        for session in directory_info["mice"][mouse]["sessions"]:
            if directory_info["mice"][mouse]["sessions"][session]["raw_data"]["is_all_raw_data_present?"] == True:
                if not directory_info["mice"][mouse]["sessions"][session]["processed_data"]["preliminary_analysis_done?"] == True or refresh == True:
                    sessions_to_process.append(Cohort.get_session(session))

    print(f"Processing {len(sessions_to_process)} sessions...")

    for session in sessions_to_process:
        print(f"\n\nProcessing {session.get('directory')}...")
        Process_Raw_Behaviour_Data(session, logger=logger, sync_with_ephys=False)
   
    directory_info = Cohort_folder(cohort_directory, multi=True, OEAB_legacy = False, ignore_tests=ignore_test_sessions).cohort

    total_time_taken = time.perf_counter() - total_start_time
    hours, remainder = divmod(total_time_taken, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"Total time taken for analysis: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds")

def run_deeplabcut_analysis(cohort_directory, make_vid_list_script, slurm_script, remote_host, remote_user, remote_key_path, num_gpus=8, mode="analyse"):
    """
    Automates the DeepLabCut processing for videos in the session folders.

    Parameters:
    - cohort_directory: Dictionary with paths to the cohort directories.
    - make_vid_list_script: Path to the make_vid_list.py script on the remote host.
    - slurm_script: Path to the SLURM job script (newSH.sh).
    - remote_host: The remote host where SLURM jobs will be submitted.
    - remote_user: The username for the remote host.
    - remote_key_path: Path to the SSH private key for the remote host.
    - num_gpus: Number of GPUs to use for the SLURM job array.
    - mode: Mode for processing videos ("analyse" or "label").
    """
    signal_file = Path(cohort_directory['cephfs_mapped']) / "make_vid_list.signal"

    # Step 1: Run make_vid_list.py on the remote host
    remote_cohort_directory = cohort_directory['cephfs_hal']
    remote_command = f"conda activate BehaviourControl && python '{make_vid_list_script}' '{remote_cohort_directory}' {mode}"

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(remote_host, username=remote_user, key_filename=remote_key_path)

        stdin, stdout, stderr = ssh.exec_command(remote_command)
        stdout.channel.recv_exit_status()  # Wait for the command to complete

        output = stdout.read().decode()
        errors = stderr.read().decode()

        if errors:
            print(f"Error occurred while running make_vid_list.py: {errors}")
            return
        else:
            print("make_vid_list.py executed successfully.")
            print(output)

        ssh.close()
    except Exception as e:
        print(f"Error occurred during SSH connection: {e}")
        return

    # Wait for the .signal file to be created
    print("Waiting for make_vid_list.signal file...")
    while not signal_file.exists():
        time.sleep(1)

    # Read the generated videos_to_analyse.txt file to count the number of lines
    video_list_path = os.path.join(cohort_directory['cephfs_mapped'], f"videos_to_{mode}.txt")
    try:
        with open(video_list_path, 'r') as file:
            num_lines = sum(1 for line in file)
        print(f"Number of videos to {mode}: {num_lines}")
    except FileNotFoundError:
        print(f"videos_to_{mode}.txt not found. Ensure make_vid_list.py executed correctly.")
        return

    # Remove the .signal file
    try:
        signal_file.unlink()
    except OSError as e:
        print(f"Error occurred while deleting signal file: {e}")

    # Step 3: Run the SLURM job array on the remote host using paramiko
    if num_lines != 0:
        slurm_command = f"cd '{cohort_directory['cephfs_hal']}' && sbatch --array=1-{num_lines}%{num_gpus} '{slurm_script}'"
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(remote_host, username=remote_user, key_filename=remote_key_path)

            stdin, stdout, stderr = ssh.exec_command(slurm_command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print("SLURM job submitted successfully.")
            else:
                print(f"Error occurred while submitting SLURM job: {stderr.read().decode()}")

            ssh.close()
        except Exception as e:
            print(f"Error occurred during SSH connection: {e}")
    else:
        print("No videos to analyse with DLC.")

def wait_until_time(target_hour):
    """Wait until the system time is past the target hour (24-hour format)"""
    while True:
        current_time = datetime.now()
        if current_time.hour >= target_hour:
            print(f"Current time {current_time.strftime('%H:%M:%S')} - Proceeding with the script...")
            break
        else:
            remaining_time = target_hour - current_time.hour
            print(f"Waiting for {remaining_time} more hour(s) until {target_hour}:00. Current time: {current_time.strftime('%H:%M:%S')}")
            time.sleep(60)  # Sleep for 60 seconds before checking again

ignore_test_sessions = False

def main():
    total_start_time = time.perf_counter()

    cohort_directories = []
    # cohort_directory = {'local': Path(r"E:\Test_output"),
    #                    'cephfs_mapped': Path(r"Y:\Behaviour code\2409_September_cohort\Data"),
    #                    'cephfs_hal': r"/cephfs2/srogers/Behaviour code/2409_September_cohort/Data",
    #                    'rsync_local': r"/cygdrive/e/Test_output/",
    #                    'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour code/2409_September_cohort/Data"}
    # cohort_directories.append(cohort_directory)

    cohort_directory = {'local': Path(r"D:\test_output"),
                       'cephfs_mapped': Path(r"Y:\Behaviour code\2409_September_cohort\Data"),
                       'cephfs_hal': r"/cephfs2/srogers/Behaviour code/2409_September_cohort/Data",
                       'rsync_local': r"/cygdrive/d/test_output/",
                       'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour code/2409_September_cohort/Data"}
    cohort_directories.append(cohort_directory)

    # cohort_directory = {'local': Path(r"D:\250317_New_rigs_test"),
    #                    'cephfs_mapped': Path(r"Y:\Behaviour code\2409_September_cohort\Data"),
    #                    'cephfs_hal': r"/cephfs2/srogers/Behaviour code/2409_September_cohort/Data",
    #                    'rsync_local': r"/cygdrive/d/test_output/",
    #                    'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour code/2409_September_cohort/Data"}
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {'local': Path(r"E:\Pitx2_Ephys"),
    #                    'cephfs_mapped': Path(r"Y:\Behaviour\Pitx2_Ephys\03-03_Optetrodes"),
    #                    'cephfs_hal': r"/cephfs2/srogers/Behaviour/Pitx2_Ephys/03-03_Optetrodes",
    #                    'rsync_local': r"/cygdrive/e/Pitx2_Ephys/",
    #                    'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour/Pitx2_Ephys/03-03_Optetrodes"}
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {'local': Path(r"E:\Pitx2_Chemogenetics"),
    #                    'cephfs_mapped': Path(r"Y:\Behaviour\Pitx2_Chemogenetics"),
    #                    'cephfs_hal': r"/cephfs2/srogers/Behaviour/Pitx2_Chemogenetics",
    #                    'rsync_local': r"/cygdrive/e/Pitx2_Chemogenetics/",
    #                    'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour/Pitx2_Chemogenetics"}
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {'local': Path(r"D:\2504_pitx2_ephys_cohort"),
    #                    'cephfs_mapped': Path(r"Y:\Behaviour code\2409_September_cohort\Data"),
    #                    'cephfs_hal': r"/cephfs2/srogers/Behaviour code/2409_September_cohort/Data",
    #                    'rsync_local': r"/cygdrive/d/test_output/",
    #                    'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour code/2409_September_cohort/Data"}
    # cohort_directories.append(cohort_directory)


    # Step 2: Process ephys data
    print("\n===== STEP 2: PROCESSING EPHYS DATA =====")
    for cohort_directory in cohort_directories:
        process_ephys_data(cohort_directory['local'], target_pin=0)

    # Step 1: Recover crashed sessions
    print("\n===== STEP 1: RECOVERING CRASHED SESSIONS =====")
    for cohort_directory in cohort_directories:
        recover_crashed_sessions(cohort_directory['local'], verbose=True, force=False)

    # Step 3: Process uncompressed videos
    print("\n===== STEP 3: PROCESSING VIDEOS =====")
    for cohort_directory in cohort_directories:
        processes = mp.cpu_count()
        process_cohort_directory(cohort_directory['local'], processes)

    # Wait until after 10 PM before running the main part
    # wait_until_time(22)  # 22:00 is 10 PM

    # Step 4: Run analysis on the local files
    print("\n===== STEP 4: RUNNING ANALYSIS =====")
    for cohort_directory in cohort_directories:
        run_analysis_on_local(cohort_directory['local'], refresh=True)

    # # Step 5: Sync files to cephfs 
    # print("\n===== STEP 5: SYNCING WITH CEPHFS =====")
    # for cohort_directory in cohort_directories:
    #     print(f"\nSyncing {cohort_directory['rsync_local']} with CephFS server...\n")
    #     sync_with_cephfs(cohort_directory['rsync_local'], cohort_directory['rsync_cephfs_mapped'])
        
    # # Step 6: Run DeepLabCut analysis
    # print("\n===== STEP 6: RUNNING DEEPLABCUT ANALYSIS =====")
    # for cohort_directory in cohort_directories:
    #     make_vid_list_script = r"/cephfs2/srogers/Behaviour code/2407_July_WT_cohort/Analysis/NAP/July_cohort_scripts/make_vid_list.py"
    #     slurm_script = r"/cephfs2/srogers/Behaviour code/2407_July_WT_cohort/Analysis/NAP/July_cohort_scripts/newSH.sh"
    #     remote_host = "hex"
    #     remote_user = "srogers"
    #     remote_key_path = r"C:\Users\Tripodi Group\.ssh\id_rsa" 
    #     run_deeplabcut_analysis(cohort_directory, make_vid_list_script, slurm_script, remote_host, remote_user, remote_key_path)
        
    # Report time taken
    total_time_taken = time.perf_counter() - total_start_time
    hours, remainder = divmod(total_time_taken, 3600)
    minutes, seconds = divmod(remainder, 60)

    print(f"Total time taken: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds")

if __name__ == "__main__":
    main()