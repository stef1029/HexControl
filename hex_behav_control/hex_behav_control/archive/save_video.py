
from pathlib import Path
import os
import matplotlib.pyplot as plt
import json
import time
import cv2 as cv
from datetime import datetime
import multiprocessing as mp
import subprocess
import struct
import sys

# Append the path to the directory containing the modules
sys.path.append(r'W:/Behaviour code/2407_July_WT_cohort/Analysis/NAP/Scripts')
from Cohort_folder import Cohort_folder

def bmp_to_avi_MP(prefix, data_folder_path, framerate = 30, num_processes = 8):
    # Get all the bmp files in the folder
    bmp_files = [f for f in os.listdir(data_folder_path) if f.endswith('.bmp') and f.startswith(prefix)]

    # Sort the files by name
    bmp_files.sort()

    # Get the first file to use as a template for the video writer
    first_file = cv.imread(os.path.join(data_folder_path, bmp_files[0]))
    height, width, channels = first_file.shape
    dims = (width, height)
    FPS = framerate

    temp_video_dir = data_folder_path / 'temp_videos'
    os.makedirs(temp_video_dir, exist_ok=True)

    # Divide your list of bmp frame files into chunks according to the number of available CPUs
    chunk_size = len(bmp_files) // num_processes
    chunks = [bmp_files[i:i + chunk_size] for i in range(0, len(bmp_files), chunk_size)]

    # Use multiprocessing to process each chunk
    with mp.Pool(num_processes) as p:
        p.starmap(process_video_chunk_MP, [(chunks[i], i, temp_video_dir, FPS, dims, data_folder_path) for i in range(num_processes)])

    # Concatenate all chunks into a single video
    output_path = data_folder_path / f"{data_folder_path.stem}_{prefix}_MP.avi"
    concatenate_videos(temp_video_dir, output_path)

    # Clean up the temporary directory
    os.rmdir(temp_video_dir)

def get_dims(frame_path):
    with open(frame_path, 'rb') as bmp:
        bmp.read(18)  # Skip over the size and reserved fields.

        # Read width and height.
        width = struct.unpack('I', bmp.read(4))[0]
        height = struct.unpack('I', bmp.read(4))[0]

    return (width, height)

def concatenate_videos(temp_video_dir, output_path):
    # Determine the list of all chunk video files
    chunk_files = sorted([os.path.join(temp_video_dir, f) for f in os.listdir(temp_video_dir) if f.endswith('.avi')])
    # Create a temporary text file containing the list of video files for ffmpeg
    list_path = os.path.join(temp_video_dir, 'video_list.txt')
    with open(list_path, 'w') as f:
        for chunk_file in chunk_files:
            f.write(f"file '{chunk_file}'\n")

    # Run ffmpeg command to concatenate all the videos
    ffmpeg_cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_path, '-c', 'copy', output_path]
    subprocess.run(ffmpeg_cmd)

    # Clean up the temporary chunk video files and text file
    for file_path in chunk_files:
        os.remove(file_path)
    os.remove(list_path)

def clear_BMP_files(data_folder_path):
    # Get all the bmp files in the folder
    bmp_files = [f for f in os.listdir(data_folder_path) if f.endswith('.bmp')]

    # Sort the files by name
    bmp_files.sort()

    for bmp_file in bmp_files:
        bmp_path = os.path.join(data_folder_path, bmp_file)
        os.remove(bmp_path)

def process_video_chunk_MP(chunk, chunk_index, temp_video_dir, FPS, DIMS, path):
    fourcc = cv.VideoWriter_fourcc(*'MJPG')
    # Each process will create its own output file
    temp_video_path = os.path.join(temp_video_dir, f"chunk_{chunk_index}.avi")
    video_writer = cv.VideoWriter(temp_video_path, fourcc, FPS, DIMS)

    for bmp_file in chunk:
        bmp_path = os.path.join(path, bmp_file)
        frame = cv.imread(bmp_path)
        video_writer.write(frame)

    video_writer.release()

def get_sessions_to_process(directory_info):
    sessions_to_video_process = []
    for mouse in directory_info["mice"]:
        for session in directory_info["mice"][mouse]["sessions"]:
            session_directory = Path(directory_info["mice"][mouse]["sessions"][session]["directory"])
            if directory_info["mice"][mouse]["sessions"][session]["raw_data"]["raw_video"] == "None":
                # test if there are .bmp files in the session directory:
                if len(list(session_directory.glob("*.bmp"))) > 0:
                    sessions_to_video_process.append(session_directory)
    return sessions_to_video_process

def process_video_session(video_session, processes):
    print(f"Processing {video_session}...")
    bmp_to_avi_MP("raw", video_session, framerate=30, num_processes=processes)
    print(f"Clearing {video_session}...")
    clear_BMP_files(video_session)

def process_cohort_directory(cohort_directory, processes):
    directory_info = Cohort_folder(cohort_directory, multi=True, plot=False).cohort
    sessions_to_video_process = get_sessions_to_process(directory_info)

    for video_session in sessions_to_video_process:
        process_video_session(video_session, processes)

def main_MP():
    total_start_time = time.perf_counter()

    cohort_directory = Path(r"C:\Users\Tripodi Group\Videos\2407_July_WT_output")

    processes = mp.cpu_count()

    process_cohort_directory(cohort_directory, processes)

    # Example for processing another cohort directory:
    # cohort_directory = Path(r"C:\Users\Tripodi Group\Videos\Another_Directory")
    # process_cohort_directory(cohort_directory, processes)

    total_time_taken = time.perf_counter() - total_start_time
    hours, remainder = divmod(total_time_taken, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"Total time taken: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds")

if __name__ == "__main__":
    main_MP()






