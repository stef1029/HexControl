from easypyspin import VideoCapture
import cv2 as cv
import numpy as np
from datetime import datetime
import csv
import json
import time
import os
import argparse
import keyboard
import multiprocessing
import subprocess

global global_FPS
global global_DIMS
global_FPS = 0
global_DIMS = (0, 0)

class Tracker:
    def __init__(self, new_mouse_ID=None, new_date_time=None, new_path=None, cam=None, FPS=30):

        if new_mouse_ID is None:
            self.mouse_ID = input(r"Enter mouse ID (no '.'s): ")
        else:
            self.mouse_ID = new_mouse_ID

        if new_date_time is None:
            self.start_time = f"{datetime.now():%y%m%d_%H%M%S}"
        else:
            self.start_time = new_date_time
        
        self.foldername = f"{self.start_time}_{self.mouse_ID}"
        if new_path is None:
            self.path = os.path.join(os.getcwd(), self.foldername)
            os.mkdir(self.path)
        else:
            self.path = new_path

        if cam is None:
            self.cam = 0
            self.cam_no = 0
        else:
            if cam == 1:
                self.cam = '22181614'
                self.cam_no = 1
            elif cam == 2:
                self.cam = '20530175'
                self.cam_no = 2
            else:
                self.cam = 0
                self.cam_no = 0

        self.angles_list = []
        self.data_list = []

        self.cap = VideoCapture(self.cam) 

        if not self.cap.isOpened():
            print("Camera can't open\nexit")
            return -1
        self.cap.set(cv.CAP_PROP_EXPOSURE, -1)
        self.cap.set(cv.CAP_PROP_GAIN, -1)
        self.FPS = FPS
        global global_FPS
        global_FPS = self.FPS
        self.cap.set(cv.CAP_PROP_FPS, self.FPS)

        self.dims = (
                int(self.cap.get(cv.CAP_PROP_FRAME_WIDTH)),
                int(self.cap.get(cv.CAP_PROP_FRAME_HEIGHT))
            )
        global global_DIMS
        global_DIMS = self.dims

    def timer(self):
        start_time = self.timer_start_time
        return time.perf_counter() - start_time

    def tracker(self, show_frame=False, save_video=True, save_to_avi=True):
        self.previous_point_1 = self.previous_point_2 = None
        self.previous_angle = None
        self.frame_count = 0

        self.timer_start_time = time.perf_counter()

        self.frame_IDs = []

        while True:
            ret, self.frame, frame_ID = self.cap.read()

            if not ret:
                continue
            
            self.frame_IDs.append(frame_ID)

            if save_video:
                filename = os.path.join(self.path, fr"raw_temp{self.frame_count:08}.bmp")
                cv.imwrite(filename, self.frame)

            # Make sure your initial prev_point_1 and prev_point_2 values are not None
            self.frame, point_1, point_2, angle = self.get_leds(self.frame, self.previous_point_1, self.previous_point_2, self.previous_angle)

            # self.frame = cv.cvtColor(self.frame, cv.COLOR_GRAY2BGR)

            # calculate time since last frame and display as true fps value on frame:
            if self.frame_count == 0:
                self.fps_start_time = time.perf_counter()
            fps = 1 / (time.perf_counter() - self.fps_start_time)
            self.fps_start_time = time.perf_counter()
            cv.putText(self.frame, str(round(fps)), (10, 30), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            if show_frame:
                scale = 0.7
                self.img_show = cv.resize(self.frame, None, fx=scale, fy=scale)
                cv.imshow(f"Rig {self.cam_no}. Press M to quit", self.img_show)

            # if save_video:
            #     filename = os.path.join(self.path, fr"overlay_temp{self.frame_count:08}.bmp")
            #     cv.imwrite(filename, self.frame)

            self.frame_count += 1

            if cv.waitKey(5) == ord("m"):
                break

            if keyboard.is_pressed("m"):
                break

        self.cap.release()
        cv.destroyAllWindows()

        self.end_time = f"{datetime.now():%y%m%d_%H%M%S}"
        self.save_data()
        print("Tracker data saved")

        if save_to_avi:
            start_time = time.perf_counter()
            print("Saving video... ")
            self.bmp_to_avi_MP("raw")
            # self.bmp_to_avi_MP("overlay")

            # check if file ending in .avi exists, if so, delete all the bmp files:
            avi_files = [f for f in os.listdir(self.path) if f.endswith('.avi')]
            if len(avi_files) > 0:
                self.clear_BMP_files()
                
            print("Video saved!")
            # time taken in minutes and seconds:
            print(f"Time taken: {round((time.perf_counter() - start_time) / 60)} minutes {round((time.perf_counter() - start_time) % 60)} seconds")

    def get_leds(self, img, prev_point_1=None, prev_point_2=None, prev_angle=None):
        # Gaussian blur to avoid issues with noisy pixels
        analysis_image = cv.GaussianBlur(img, (5, 5), 0)

        # Find coords of first maximum value
        (minVal, maxVal, minLoc, maxLoc) = cv.minMaxLoc(analysis_image)
        point_1 = maxLoc
        # Draw a black mask over this region so it isn't detected again:
        mask = cv.circle(analysis_image, point_1, 50, (0, 0, 0), -1)
        # Find coords of second maximum value
        (minVal, maxVal, minLoc, maxLoc) = cv.minMaxLoc(mask)
        point_2 = maxLoc
        dist_1 = 0
        dist_2 = 0

#-------------------------
        #Start the calculation of whether the points should be flipped in order based on comparison to their last known location:

        # get distance between points and their previous equivalents:
        if prev_point_1 is not None and prev_point_2 is not None:
            dist_1 = np.hypot(prev_point_1[0] - point_1[0], prev_point_1[1] - point_1[1])
            dist_2 = np.hypot(prev_point_2[0] - point_2[0], prev_point_2[1] - point_2[1])

        # swapped equivalent:
        if prev_point_1 is not None and prev_point_2 is not None:
            dist_1_swapped = np.hypot(prev_point_2[0] - point_1[0], prev_point_2[1] - point_1[1])
            dist_2_swapped = np.hypot(prev_point_1[0] - point_2[0], prev_point_1[1] - point_2[1])

        max_jump = 50    # should be less than the distance to the next light but also decently bigger than the led size
        #if the distance between the two points suddenly increases massively, then it is likely there is an obstruction
        # and we should ignore the new point and keep the old one.
        max_distance = 100  # should be bigger than the distance to the next light.

        # if the distance between the two new points and their previous position is greater than max_distance,
        # then it is deemed that the detector has jumped to an incorrect signal, and so these new values should be ignored
        if np.hypot(point_1[0] - point_2[0], point_1[1] - point_2[1]) > max_distance:
            point_1, point_2 = prev_point_1, prev_point_2   # <- do not use new values, instead stick with previous ones.
        
        # if both the points have jumped outside the radius somewhere
        # and both those points happen to fall within the radius of the other points previous location, then a swap has occured.
        if dist_1 > max_jump and dist_2 > max_jump and dist_1_swapped < max_jump and dist_2_swapped < max_jump:
            point_1, point_2 = point_2, point_1  # swap points
#-------------------------

        # convert to colour image:
        img = cv.cvtColor(img, cv.COLOR_GRAY2BGR)
        # draw different colour dot on frame at brightest pixel:
        cv.circle(img, point_1, 5, (0, 0, 255), -1)
        cv.circle(img, point_2, 5, (0, 255, 0), -1)
        #draw line between two points and display angle between then in degrees:
        cv.line(img, point_1, point_2, (255, 255, 255), 2)

        # Compute current_angle using atan2
        current_angle = 0
        if point_1 != None and point_2 != None:
            current_angle = cv.fastAtan2(-(point_2[1] - point_1[1]), (point_2[0] - point_1[0]))    # -y because y axis is flipped in image coordinates

#-------------------------
        # Check that angle makes sense based on previous known angle. If the angle has flipped into the range 180 degrees away, then it has likely flipped
        angle_threshold = 5
        if prev_angle is not None:
            if 180 - angle_threshold < (current_angle - prev_angle) < 180 + angle_threshold:
                current_angle = current_angle + 180
            elif -180 - angle_threshold < (current_angle - prev_angle) < -180 + angle_threshold:
                current_angle = current_angle - 180
            if current_angle < 0:
                current_angle = current_angle + 360
            elif current_angle > 360:
                current_angle = current_angle - 360


        # if current_angle > 180:
        #     current_angle = current_angle - 180
        # draw white circles around both points at both max_jump radiusa dn max_distance radius;
        # cv.circle(img, point_1, max_jump, (255, 255, 255), 2)
        # cv.circle(img, point_2, max_jump, (255, 255, 255), 2)
        # cv.circle(img, point_1, max_distance, (255, 255, 255), 2)
        # cv.circle(img, point_2, max_distance, (255, 255, 255), 2)
        if point_1 != None and point_2 != None:
            cv.putText(img, str(round(current_angle)), (point_1[0] + 10, point_1[1] + 10), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        self.data_list.append([self.timer(), self.frame_count, point_1, point_2, current_angle])

        self.previous_point_1, self.previous_point_2 = point_1, point_2

        return img, point_1, point_2, current_angle
    
    def save_data(self):
        # make file name the date and time:
        file_name = f"{self.foldername}_Tracker_data.json"

        data = {}

        data["frame_rate"] = self.FPS
        data["start_time"] = self.start_time
        data["end_time"] = self.end_time
        data["height"] = self.dims[1]
        data["width"] = self.dims[0]
        data["headers"] = ["time", "frame", "point_1", "point_2", "angle"]
        data["data"] = self.data_list
        data["frame_IDs"] = self.frame_IDs

        # save data to json file:
        
        with open(f'{os.path.join(self.path, f"{file_name}")}', "w") as f:
            json.dump(data, f, indent=4)


    def bmp_to_avi_MP(self, prefix, framerate = 30):
        # Get all the bmp files in the folder
        bmp_files = [f for f in os.listdir(self.path) if f.endswith('.bmp') and f.startswith(prefix)]

        # Sort the files by name
        bmp_files.sort()

        # Get the first file to use as a template for the video writer
        first_file = cv.imread(os.path.join(self.path, bmp_files[0]))
        height, width, channels = first_file.shape

        temp_video_dir = os.path.join(self.path, 'temp_videos')
        os.makedirs(temp_video_dir, exist_ok=True)

        # Divide your list of bmp frame files into chunks according to the number of available CPUs
        num_processes = multiprocessing.cpu_count()
        chunk_size = len(bmp_files) // num_processes
        chunks = [bmp_files[i:i + chunk_size] for i in range(0, len(bmp_files), chunk_size)]

        global global_FPS
        global global_DIMS
        # Use multiprocessing to process each chunk
        with multiprocessing.Pool(num_processes) as p:
            p.starmap(process_video_chunk_MP, [(chunks[i], i, temp_video_dir, self.FPS, self.dims, self.path) for i in range(num_processes)])

        # Concatenate all chunks into a single video
        output_path = os.path.join(self.path, f"{self.foldername}_{prefix}_MP.avi")
        self.concatenate_videos(temp_video_dir, output_path)

        # Clean up the temporary directory
        os.rmdir(temp_video_dir)

    # def process_video_chunk(self, chunk, chunk_index, temp_video_dir):
    #     fourcc = cv.VideoWriter_fourcc(*'MJPG')
    #     # Each process will create its own output file
    #     temp_video_path = os.path.join(temp_video_dir, f"chunk_{chunk_index}.avi")
    #     video_writer = cv.VideoWriter(temp_video_path, fourcc, self.FPS, self.dims)

    #     for frame_path in chunk:
    #         frame = cv.imread(frame_path)
    #         video_writer.write(frame)

    #     video_writer.release()
    
    def concatenate_videos(self, temp_video_dir, output_path):
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

    def clear_BMP_files(self):
        # Get all the bmp files in the folder
        bmp_files = [f for f in os.listdir(self.path) if f.endswith('.bmp')]

        # Sort the files by name
        bmp_files.sort()

        for bmp_file in bmp_files:
            bmp_path = os.path.join(self.path, bmp_file)
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

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=str, help="Mouse ID")
    parser.add_argument("--date", type=str, help="Date and time")
    parser.add_argument("--path", type=str, help="Path to save data to")
    parser.add_argument("--rig", type=int, help="Rig number")
    args = parser.parse_args()
    
    if args.id is not None:
        mouse_ID = args.id
    else:
        mouse_ID = "NoID"
    
    if args.date is not None:
        date_time = args.date
    else:
        date_time = f"{datetime.now():%y%m%d_%H%M%S}"
    
    foldername = f"{date_time}_{mouse_ID}"
    if args.path is not None:
        path = args.path

    else:
        test_path = r"C:\Users\Tripodi Group\Videos\Test video"
        # path = os.path.join(os.getcwd(), foldername)
        path = os.path.join(test_path, foldername)
        os.mkdir(path)

    if args.rig is not None:
        cam = args.rig

    else:
        cam = None

    camera = Tracker(new_mouse_ID=mouse_ID, new_date_time=date_time, new_path=path, cam=cam)
    camera.tracker(show_frame=True, save_video=True, save_to_avi=False)

if __name__ == "__main__":
    main()