import json
import numpy as np
import cv2
from datetime import datetime
from pathlib import Path
import multiprocessing as mp
import subprocess
import os

def convert_binary_to_video(binary_filename, json_filename, output_directory):
    # Load metadata from JSON file
    try:
        with open(json_filename, 'r') as json_file:
            metadata = json.load(json_file)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return False

    # Extract metadata
    try:
        image_width = metadata['image_width']
        image_height = metadata['image_height']
        frame_rate = metadata['frame_rate']
        frame_IDs = metadata.get('frame_IDs', [])

        if not frame_IDs:
            print("Error: 'frame_IDs' not found or empty in JSON file.")
            return

        number_of_images = len(frame_IDs)

        # Since images are always Mono8, set bytes_per_pixel accordingly
        bytes_per_pixel = 1

        # Extract session ID from the output directory name
        session_id = Path(output_directory).name
        
        # Generate output video filename using session ID
        video_filename = output_directory / f"{session_id}_video.avi"

    except KeyError as e:
        print(f"Missing key in JSON file: {e}")
        return False

    # Calculate image size
    image_size = image_width * image_height * bytes_per_pixel

    # Determine the number of CPU cores
    num_cores = mp.cpu_count()
    # num_cores = 4  # You can set this manually if desired
    print(f"Number of CPU cores available: {num_cores}")

    # Calculate chunk size
    chunk_size = max(number_of_images // num_cores, 1)

    # Split frame indices into chunks
    chunks = [frame_IDs[i:i + chunk_size] for i in range(0, number_of_images, chunk_size)]

    # Create a temporary directory for intermediate video chunks
    temp_video_dir = output_directory / 'temp_videos'
    temp_video_dir.mkdir(parents=True, exist_ok=True)

    # Prepare arguments for multiprocessing
    args = []
    for idx, chunk in enumerate(chunks):
        args.append((binary_filename, image_size, image_width, image_height,
                     chunk, idx, temp_video_dir, bytes_per_pixel, frame_rate))

    # Use multiprocessing to process chunks in parallel
    with mp.Pool(processes=min(num_cores, len(chunks))) as pool:
        pool.starmap(process_video_chunk, args)

    # Concatenate all chunked videos into one final video
    concatenate_videos(temp_video_dir, video_filename)

    # Clean up temporary directory
    for temp_file in temp_video_dir.glob('*'):
        temp_file.unlink()
    temp_video_dir.rmdir()

    print(f"Video saved as {video_filename}")
    return True

def process_video_chunk(binary_filename, image_size, image_width, image_height,
                        frame_IDs_chunk, chunk_index, temp_video_dir, bytes_per_pixel, frame_rate):
    """
    Processes a chunk of images and writes them to a temporary video file.
    """
    import numpy as np
    import cv2

    # Open binary file
    try:
        with open(binary_filename, 'rb') as binary_file:
            # Calculate the position to start reading from
            start_frame = frame_IDs_chunk[0]
            start_pos = start_frame * image_size
            binary_file.seek(start_pos)

            # Set up VideoWriter for grayscale images
            is_color = False  # Mono8 images are grayscale
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # Change codec if needed
            temp_video_filename = temp_video_dir / f"chunk_{chunk_index:03}.avi"
            video_writer = cv2.VideoWriter(
                str(temp_video_filename),
                fourcc,
                frame_rate,  # Use the correct frame rate
                (image_width, image_height),
                isColor=is_color
            )

            if not video_writer.isOpened():
                print(f"Error: Could not open temporary video file for writing: {temp_video_filename}")
                return

            # Process images in the chunk
            for _ in frame_IDs_chunk:
                buffer = binary_file.read(image_size)
                if not buffer:
                    print(f"Error: End of file reached unexpectedly in chunk {chunk_index}")
                    break
                elif len(buffer) < image_size:
                    print(f"Error: Incomplete image data in chunk {chunk_index}")
                    break

                # Convert buffer to NumPy array
                image = np.frombuffer(buffer, dtype=np.uint8)

                # Reshape the image to 2D array
                image = image.reshape((image_height, image_width))

                # Write frame to video
                video_writer.write(image)

            # Clean up
            video_writer.release()

    except Exception as e:
        print(f"Error processing chunk {chunk_index}: {e}")
        return

def concatenate_videos(temp_video_dir, output_filename):
    """
    Concatenates temporary video chunks into a single video using ffmpeg.
    """
    import subprocess

    # Get list of chunk video files
    chunk_files = sorted(temp_video_dir.glob('chunk_*.avi'))

    if not chunk_files:
        print(f"No chunk files found in {temp_video_dir}. Skipping concatenation.")
        return

    # Create a text file listing all the chunk files
    list_file = temp_video_dir / 'video_list.txt'
    with open(list_file, 'w') as f:
        for chunk_file in chunk_files:
            f.write(f"file '{chunk_file.as_posix()}'\n")

    # Build ffmpeg command
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file.as_posix()),
        '-c', 'copy', str(output_filename)
    ]

    # Run ffmpeg to concatenate videos
    result = subprocess.run(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        print(f"ffmpeg error (concatenate_videos):\n{result.stderr}")
        return

    # Remove the list file
    list_file.unlink()

def delete_binary_files(session_directory, binary_file_path):
    """
    Deletes binary video files after confirming that any AVI file exists in the directory.
    
    Args:
        session_directory (Path): Directory containing the session data
        binary_file_path (Path): Path to the binary file that was processed
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Check if any AVI files exist in the directory
        avi_files = list(session_directory.glob('*.avi'))
        
        # If any AVI file exists, delete the binary file
        if avi_files:
            binary_file_path.unlink()
            print(f"Binary file {binary_file_path} deleted successfully.")
            return True
        else:
            # If no AVI exists, don't delete the binary
            print(f"No AVI files found in {session_directory}. Binary file not deleted.")
            return False
    except Exception as e:
        print(f"Error deleting binary file {binary_file_path}: {e}")
        return False


def cleanup_binary_files(cohort_info):
    """
    Cleans up binary files for all sessions that have any AVI files.
    Will delete binary files as long as any .avi file exists in the directory.
    
    Args:
        cohort_info (dict): Dictionary containing cohort information
        
    Returns:
        int: Number of binary files deleted
    """
    deleted_count = 0
    
    # Iterate over each mouse in the directory information
    for mouse in cohort_info["mice"]:
        # Iterate over each session for the mouse
        for session in cohort_info["mice"][mouse]["sessions"]:
            session_data = cohort_info["mice"][mouse]["sessions"][session]
            session_directory = Path(session_data["directory"])
            
            # Look for binary files to clean up
            binary_files = list(session_directory.glob('*binary_video*'))
            
            # Only proceed if there are binary files to clean
            if binary_files:
                # Check if there are any AVI files in the directory
                avi_files = list(session_directory.glob('*.avi'))
                
                # If any AVI files exist, delete the binary files
                if avi_files:
                    for binary_file in binary_files:
                        try:
                            binary_file.unlink()
                            print(f"Cleaned up: Binary file {binary_file} deleted successfully.")
                            deleted_count += 1
                        except Exception as e:
                            print(f"Error deleting binary file {binary_file}: {e}")
                else:
                    print(f"Skipping cleanup in {session_directory}: No AVI files found.")
    
    return deleted_count

if __name__ == "__main__":
    # Define the paths
    binary_filename = r"E:\bin_test\241128_151903_test1_binary_video.bin"
    json_filename = r"E:\bin_test\241128_151903_test1_Tracker_data.json"
    output_directory = Path(r"E:\bin_test")

    # Convert binary to video with multiprocessing
    convert_binary_to_video(binary_filename, json_filename, output_directory)
