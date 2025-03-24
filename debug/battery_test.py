from Scripts.read import Scales
import time
import json
import keyboard

rd = Scales()

most_recent_scales_value = 0
def weight(test = False):
    global most_recent_scales_value
    global scales_data
    # Returns weight from scales. If no new data, returns most recent value.
    # Also adds scales data to scales_data list.
    data = rd.get_mass()
    if data != None:
        most_recent_scales_value = data
        if test == False:
            scales_data.append([timer(), data])
        return data
    else:
        return most_recent_scales_value
    

global tic
tic = 0
def timer():
    global tic
    toc = time.perf_counter()       
    return toc - tic

filename = f"battery_test_{time.strftime('%Y%m%d_%H%M%S')}.json"

readings = {}
scales_data = []
tic = time.perf_counter()
time_of_last_reading = 0
while True:
    reading = rd.get_mass()
    if reading != None:
        entry = (timer(), reading)  
        scales_data.append(entry)
        time_of_last_reading = entry[0]
    else:
        if timer() - time_of_last_reading > 1:
            break
    if keyboard.is_pressed("q"):
        break

readings["scales"] = scales_data

battery_life = timer() / 60

readings["battery_life"] = battery_life

print(f"Battery life: {battery_life} minutes")

with open(filename, "w") as f:
    json.dump(readings, f, indent=4)