from deeplabcut import analyze_videos
from deeplabcut import video_inference_superanimal
import time
import sys
import gc
import threading
import ctypes

# config = r'/cephfs2/srogers/New_analysis_pipeline/training_videos/DLC_Project_231212_193535_wtjx285-2a_raw_MP-SRC-2024-01-09/config.yaml'
# config = r'/cephfs2/dwelch/6-choice_behaviour_DLC_model/config.yaml'
# config = r'/cephfs2/srogers/DEEPLABCUT_models/LMDC_model_videos/models/LMDC-StefanRC-2025-03-11/config.yaml' # model used for chemo mice 2025
config = r'/cephfs2/srogers/DEEPLABCUT_models/2500601_Pitx2_ephys_model/project_folders/tetrodes-StefanRC-2025-06-01/config.yaml' # first attempt at tetrode model

# Global flag for malloc_trim thread
stop_trim_thread = False


def malloc_trim_thread(interval=15):
    """
    Periodically call malloc_trim to return freed memory to the OS.
    This prevents memory fragmentation issues during long video analysis.
    """
    global stop_trim_thread
    
    try:
        libc = ctypes.CDLL("libc.so.6")
    except OSError:
        print("Warning: malloc_trim not available (Linux only). Memory usage may be higher.")
        return
    
    while not stop_trim_thread:
        time.sleep(interval)
        if not stop_trim_thread:
            # Trim memory and run garbage collection
            libc.malloc_trim(0)
            gc.collect()


def analyse(video_path, gpu_id):
    """
    Analyse video with malloc_trim fix for memory issues.
    """
    global stop_trim_thread
    stop_trim_thread = False
    
    # Start malloc_trim thread
    trim_thread = threading.Thread(target=malloc_trim_thread, args=(15,), daemon=True)
    trim_thread.start()
    
    start_time = time.perf_counter()
    print(f"Analyzing {str(video_path)}")
    print(f"Using GPU {gpu_id}")
    
    try:
        analyze_videos(config=config,
                      videos=[video_path], 
                      videotype='.avi', 
                      save_as_csv=True, 
                      gputouse=gpu_id)
        
        # Calculate time taken
        elapsed_time = time.perf_counter() - start_time
        minutes = round(elapsed_time / 60, 2)
        seconds = round(elapsed_time % 60, 2)
        
        print(f"Analysis of {str(video_path)} complete.")
        print(f"Took: {minutes} minutes and {seconds} seconds")
        
    finally:
        # Stop malloc_trim thread
        stop_trim_thread = True

    

if __name__ == "__main__":
    video_path = sys.argv[1]
    gpu_id = int(sys.argv[2])

    analyse(video_path, gpu_id)