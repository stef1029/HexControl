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

# Append the path to the directory containing the modules
sys.path.append(r'C:\Dev\projects\July_cohort_scripts')

from Cohort_folder import Cohort_folder
from analysis_manager import Process_Raw_Behaviour_Data  # Import your analysis manager function

# Convert BMP images to AVI video using multiprocessing
def bmp_to_avi_MP(prefix, data_folder_path, framerate=30, num_processes=8):
    """
    Converts BMP images to an AVI video using multiprocessing to speed up the process.
    
    Args:
        prefix (str): The prefix to match BMP files.
        data_folder_path (str/Path): The directory where BMP files are stored.
        framerate (int): Frames per second for the video. Default is 30.
        num_processes (int): Number of processes to use for multiprocessing. Default is 8.
    
    Returns:
        None
    """
    # Get all BMP files in the directory that match the given prefix
    bmp_files = [f for f in os.listdir(data_folder_path) if f.endswith('.bmp') and f.startswith(prefix)]
    bmp_files.sort()  # Sort files by name

    # Define the path for the debug directory
    debug_dir = Path(data_folder_path) / 'debug'

    # Create the directory if it doesn't exist
    debug_dir.mkdir(parents=True, exist_ok=True)

    # Save a copy of the file names to a text file
    with open(debug_dir / 'bmp_files.txt', 'w') as f:
        for item in bmp_files:
            f.write(f"{item}\n")

    # Read the first BMP file to get video dimensions (height, width, channels)
    first_file = cv.imread(os.path.join(data_folder_path, bmp_files[0]))
    height, width, channels = first_file.shape
    dims = (width, height)  # Dimensions tuple for video
    FPS = framerate  # Frames per second

    # Create a temporary directory for intermediate video chunks
    temp_video_dir = data_folder_path / 'temp_videos'
    os.makedirs(temp_video_dir, exist_ok=True)

    # Split the BMP files into chunks for multiprocessing
    chunk_size = len(bmp_files) // num_processes
    chunks = [bmp_files[i:i + chunk_size] for i in range(0, len(bmp_files), chunk_size)]

    # Use multiprocessing to convert BMP chunks into AVI video files
    with mp.Pool(num_processes) as p:
        p.starmap(process_video_chunk_MP, [
            (chunks[i], i, temp_video_dir, FPS, dims, data_folder_path) for i in range(num_processes)
        ])

    # Set the output path for the final concatenated AVI video
    output_path = data_folder_path / f"{data_folder_path.stem}_{prefix}_MP.avi"
    
    # Concatenate all chunked AVI files into one final video
    concatenate_videos(temp_video_dir, output_path)

    # Remove the temporary directory after processing
    os.rmdir(temp_video_dir)

# Helper function to get dimensions of a BMP image
def get_dims(frame_path):
    """
    Retrieves the width and height of a BMP image from its file header.
    
    Args:
        frame_path (str): The file path of the BMP image.
    
    Returns:
        tuple: A tuple containing the width and height of the image.
    """
    # Open the BMP file in binary mode
    with open(frame_path, 'rb') as bmp:
        bmp.read(18)  # Skip header bytes to reach width and height data
        width = struct.unpack('I', bmp.read(4))[0]  # Read width (4 bytes)
        height = struct.unpack('I', bmp.read(4))[0]  # Read height (4 bytes)
    return (width, height)

# Concatenate chunked AVI videos into a single output video using ffmpeg
def concatenate_videos(temp_video_dir, output_path):
    """
    Concatenates chunked AVI files into a single output video using ffmpeg.

    Args:
        temp_video_dir (str/Path): Directory where the temporary AVI chunk files are stored.
        output_path (str/Path): The path to save the final concatenated video.

    Returns:
        None
    """
    # Get the list of all chunked AVI files sorted by name
    chunk_files = sorted([os.path.join(temp_video_dir, f) for f in os.listdir(temp_video_dir) if f.endswith('.avi')])

    # Create a text file listing all the chunk files to concatenate
    list_path = os.path.join(temp_video_dir, 'video_list.txt')
    with open(list_path, 'w') as f:
        for chunk_file in chunk_files:
            f.write(f"file '{chunk_file}'\n")

    # Call ffmpeg to concatenate the listed chunk files into one final video
    ffmpeg_cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_path, '-c', 'copy', output_path]
    subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    # Clean up: remove individual chunk files and the list file
    for file_path in chunk_files:
        os.remove(file_path)
    os.remove(list_path)

# Remove all BMP files from the data folder after processing
def clear_BMP_files(data_folder_path):
    """
    Deletes all BMP files from the given folder after processing.
    
    Args:
        data_folder_path (str/Path): The directory containing BMP files to be deleted.
    
    Returns:
        None
    """
    # Get a sorted list of all BMP files in the folder
    bmp_files = [f for f in os.listdir(data_folder_path) if f.endswith('.bmp')]
    bmp_files.sort()
    
    # Remove each BMP file from the folder
    for bmp_file in bmp_files:
        bmp_path = os.path.join(data_folder_path, bmp_file)
        os.remove(bmp_path)

# Process a chunk of BMP files into an AVI video file (used in multiprocessing)
def process_video_chunk_MP(chunk, chunk_index, temp_video_dir, FPS, DIMS, path):
    """
    Converts a chunk of BMP files into an AVI video and saves it as a temporary file.
    
    Args:
        chunk (list): List of BMP files to process in this chunk.
        chunk_index (int): The index of this chunk (used for naming the output file).
        temp_video_dir (str/Path): The directory where the temporary AVI files will be stored.
        FPS (int): Frames per second for the video.
        DIMS (tuple): Dimensions of the video (width, height).
        path (str/Path): The root path where BMP files are stored.
    
    Returns:
        None
    """
    # Define the codec for AVI video (MJPG codec)
    fourcc = cv.VideoWriter_fourcc(*'MJPG')

    # Create the path for the output video chunk
    temp_video_path = os.path.join(temp_video_dir, f"chunk_{chunk_index:03}.avi")  
    
    # Initialize the video writer with specified dimensions and frame rate
    video_writer = cv.VideoWriter(temp_video_path, fourcc, FPS, DIMS)

    # Write each BMP image in the chunk to the video
    for bmp_file in chunk:
        bmp_path = os.path.join(path, bmp_file)
        frame = cv.imread(bmp_path)  # Read BMP file as an image
        video_writer.write(frame)  # Write the image frame to the video

    # Release the video writer to finalize the chunk video
    video_writer.release()

# Get a list of sessions that have BMP files but no associated video
def get_sessions_to_process(directory_info):
    """
    Returns a list of sessions that contain BMP files but have no associated raw video.
    
    Args:
        directory_info (dict): A dictionary containing metadata about the mice and their sessions.
    
    Returns:
        list: A list of tuples, each containing the session directory and frame rate.
    """
    sessions_to_video_process = []

    # Iterate over each mouse in the directory information
    for mouse in directory_info["mice"]:
        # Iterate over each session for the mouse
        for session in directory_info["mice"][mouse]["sessions"]:
            session_directory = Path(directory_info["mice"][mouse]["sessions"][session]["directory"])

            # Check if the session has no raw video, but contains BMP files
            if directory_info["mice"][mouse]["sessions"][session]["raw_data"]["raw_video"] == "None":
                if len(list(session_directory.glob("*.bmp"))) > 0:
                    # Load behavior data to get the FPS (frames per second)
                    behaviour_data_path = directory_info["mice"][mouse]["sessions"][session]["raw_data"].get("behaviour_data")
                    
                    fps = 30  # Default FPS
                    if behaviour_data_path and Path(behaviour_data_path).exists():
                        try:
                            with open(behaviour_data_path, 'r') as file:
                                behaviour_data = json.load(file)
                                fps = behaviour_data.get("fps", 30)  # Default to 30 FPS if not specified
                        except Exception as e:
                            # Handle any error by keeping fps as 30
                            print(f"Error loading behaviour data from {behaviour_data_path}: {e}")
                    
                    # Add the session directory and FPS to the list of sessions to process
                    sessions_to_video_process.append((session_directory, fps))
    
    return sessions_to_video_process

# Process a single video session, converting BMP images to AVI and then clearing the BMP files
def process_video_session(video_session, processes, fps):
    """
    Converts BMP files from a video session into an AVI video and clears the BMP files after processing.
    
    Args:
        video_session (str/Path): The directory containing BMP files for this session.
        processes (int): The number of processes to use for multiprocessing.
        fps (int): The frames per second to use for the video.
    
    Returns:
        None
    """
    bmp_to_avi_MP("raw", video_session, framerate=fps, num_processes=processes)  # Convert BMP to AVI
    print(f"Clearing {video_session}...")  # Inform the user that clearing BMP files will begin
    clear_BMP_files(video_session)  # Clear BMP files after video is created

# Process all sessions in a cohort directory, converting BMP images to AVI videos
def process_cohort_directory(cohort_directory, processes):
    """
    Processes all sessions within a cohort directory by converting BMP files to AVI videos.

    Args:
        cohort_directory (str/Path): The root directory containing cohort data.
        processes (int): Number of processes to use for multiprocessing.

    Returns:
        None
    """
    # Load cohort directory information (this assumes Cohort_folder is defined elsewhere)
    directory_info = Cohort_folder(cohort_directory, multi=True, plot=False).cohort

    # Get all sessions that need video processing (BMP to AVI conversion)
    sessions_to_video_process = get_sessions_to_process(directory_info)

    total_sessions = len(sessions_to_video_process)  # Calculate the total number of sessions

    # Process each session by converting BMP to AVI and then clearing BMP files
    for i, (video_session, fps) in enumerate(sessions_to_video_process, start=1):
        print(f"Processing session {i}/{total_sessions}: {video_session}...")
        process_video_session(video_session, processes, fps)




def sync_with_cephfs(local_dir, remote_dir):
    rsync_command = [
        "rsync", "-avz",
        local_dir,
        remote_dir
    ]
    try:
        subprocess.run(rsync_command, check=True)
        print("\nSync completed successfully.\n")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred during rsync: {e}")

def run_analysis_on_local(cohort_directory):
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

    Cohort = Cohort_folder(cohort_directory, multi=True)
    directory_info = Cohort.cohort

    sessions_to_process = []
    refresh = False

    for mouse in directory_info["mice"]:
        for session in directory_info["mice"][mouse]["sessions"]:
            if directory_info["mice"][mouse]["sessions"][session]["raw_data"]["is_all_raw_data_present?"] == True:
                if not directory_info["mice"][mouse]["sessions"][session]["processed_data"]["preliminary_analysis_done?"] == True or refresh == True:
                    sessions_to_process.append(Cohort.get_session(session))

    print(f"Processing {len(sessions_to_process)} sessions...")

    for session in sessions_to_process:
        print(f"Processing {session.get('directory')}...")
        Process_Raw_Behaviour_Data(session, logger=logger)

    directory_info = Cohort_folder(cohort_directory, multi=True).cohort

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

def main_MP():
    total_start_time = time.perf_counter()

    cohort_directories = []
    # cohort_directory = {'local': Path(r"E:\September_cohort"),
    #                    'cephfs_mapped': Path(r"Y:\Behaviour code\2409_September_cohort\Data"),
    #                    'cephfs_hal': r"/cephfs2/srogers/Behaviour code/2409_September_cohort/Data",
    #                    'rsync_local': r"/cygdrive/e/September_cohort/",
    #                    'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour code/2409_September_cohort/Data"}
    # cohort_directories.append(cohort_directory)

    cohort_directory = {'local': Path(r"E:\Test_output"),
                       'cephfs_mapped': Path(r"Y:\Behaviour code\2409_September_cohort\Data"),
                       'cephfs_hal': r"/cephfs2/srogers/Behaviour code/2409_September_cohort/Data",
                       'rsync_local': r"/cygdrive/e/Test_output/",
                       'rsync_cephfs_mapped': r"/cygdrive/y/Behaviour code/2409_September_cohort/Data"}
    cohort_directories.append(cohort_directory)

    for cohort_directory in cohort_directories:
        # Process uncompressed videos:
        processes = mp.cpu_count()
        process_cohort_directory(cohort_directory['local'], processes)

    for cohort_directory in cohort_directories:
        # Run analysis on the local files:
        run_analysis_on_local(cohort_directory['local'])

        # Sync files to cephfs:
        print(f"\nSyncing {cohort_directory['rsync_local']} with CephFS server...\n")
        sync_with_cephfs(cohort_directory['rsync_local'], cohort_directory['rsync_cephfs_mapped'])
        
        # Run DeepLabCut analysis on the videos in CephFS:
        make_vid_list_script = r"/cephfs2/srogers/Behaviour code/2407_July_WT_cohort/Analysis/NAP/July_cohort_scripts/make_vid_list.py"
        slurm_script = r"/cephfs2/srogers/Behaviour code/2407_July_WT_cohort/Analysis/NAP/July_cohort_scripts/newSH.sh"
        remote_host = "hex"
        remote_user = "srogers"
        remote_key_path = r"C:\Users\Tripodi Group\.ssh\id_rsa" 
        run_deeplabcut_analysis(cohort_directory, make_vid_list_script, slurm_script, remote_host, remote_user, remote_key_path)
        
        # Report time taken:
        total_time_taken = time.perf_counter() - total_start_time
        hours, remainder = divmod(total_time_taken, 3600)
        minutes, seconds = divmod(remainder, 60)

    print(f"Total time taken: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds")

if __name__ == "__main__":
    main_MP()
