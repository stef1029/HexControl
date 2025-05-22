import os
import subprocess
from pathlib import Path
import multiprocessing as mp
import cv2 as cv
import struct
import json

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

    if not bmp_files:
        print(f"No BMP files found in {data_folder_path}. Skipping BMP to AVI conversion.")
        return

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
    temp_video_dir = Path(data_folder_path) / 'temp_videos'
    os.makedirs(temp_video_dir, exist_ok=True)

    # Split the BMP files into chunks for multiprocessing
    chunk_size = max(len(bmp_files) // num_processes, 1)
    chunks = [bmp_files[i:i + chunk_size] for i in range(0, len(bmp_files), chunk_size)]

    # Use multiprocessing to convert BMP chunks into AVI video files
    with mp.Pool(processes=min(num_processes, len(chunks))) as p:
        p.starmap(process_video_chunk_MP, [
            (chunks[i], i, temp_video_dir, FPS, dims, data_folder_path) for i in range(len(chunks))
        ])

    # Set the output path for the final concatenated AVI video
    output_path = Path(data_folder_path) / f"{Path(data_folder_path).name}_{prefix}_MP.avi"
    
    # Concatenate all chunked AVI files into one final video
    concatenate_videos(temp_video_dir, output_path)

    # Remove the temporary directory after processing
    os.rmdir(temp_video_dir)

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

    if not chunk_files:
        print(f"No chunk files found in {temp_video_dir}. Skipping concatenation.")
        return

    # Create a text file listing all the chunk files to concatenate
    list_path = os.path.join(temp_video_dir, 'video_list.txt')
    with open(list_path, 'w') as f:
        for chunk_file in chunk_files:
            f.write(f"file '{chunk_file}'\n")

    # Call ffmpeg to concatenate the listed chunk files into one final video
    ffmpeg_cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path, '-c', 'copy', str(output_path)]
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
