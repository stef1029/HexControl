"""
This program reads the raw data from the serial port which represents the reading from a set of scales. the data is converted to a weight based on colibartion values.
This weight is then printed. 
"""


import serial
import time
import struct
import keyboard

class Scales():
    def __init__(self, rig = None):
        self.UP = "\033[1A"; self.CLEAR = '\x1b[2K'
        self.rig = rig
        if rig == None:
            self.port = "COM1"
            self.scale = float(0.22375971500351627)       # these values are found by running Calibrate() and copying the output
            self.intercept = 6497.609999999999
        else:
            if rig == 1:
                self.port = "COM12"
                self.scale = float(0.22375971500351627)       # these values are found by running Calibrate() and copying the output
                self.intercept = -5617.39 
                baudrate = 115200
            elif rig == 2:
                self.port = "COM5"     ## These port numbers need checking
                self.scale = float(0.21654951518353163)       # these values are found by running Calibrate() and copying the output            ## Calibrated 29th September '25 (DW)
                self.intercept = -983.6799999999988
                baudrate = 115200
            elif rig == 3:
                self.port = "COM10"
                self.scale = float(0.1725046376146776)
                self.intercept = -1327.66
                baudrate = 9600
            elif rig == 4:
                self.port = "COM12"
                self.scale = float(0.16461420192565693)
                self.intercept = -616.28
                baudrate = 9600
            else:
                raise ValueError("Rig number not recognised")

        # def convert(data):
        try:
            self.ser = serial.Serial(self.port, baudrate, timeout=0)
            time.sleep(2)
        except serial.SerialException:
            print("Serial connection not found, trying again...")
            self.ser = serial.Serial(self.port, baudrate, timeout=0)
            time.sleep(2)

        if rig == 3 or rig == 4:
            self.ser.write(b'e') 
            self.ser.write(b's')
        
        self.mouse_weight = 20

        if self.rig == 3 or self.rig == 4:
            self.most_recent_scales_value = {'ID': None, 'value': 0}
        elif self.rig == 1 or self.rig == 2:
            self.most_recent_scales_value = {'value': 0}
        else:
            raise ValueError("Rig number not recognised")

        self.previous_time = None  # To track the previous valid reading time

    def __del__(self):
        if hasattr(self, 'ser'):
            try:
                self.ser.write(b'e')
                self.ser.close()
            except Exception as e:
                print(f"Error closing serial port: {e}")

    def raw_read(self):
        """
        Drop-in replacement for raw_read that processes only the most recent message.
        This fixes the buffer backlog lag issue.
        """
        # Wired scales read
        if self.rig == 3 or self.rig == 4:
            # Reads raw input from serial, if available. If not, returns (None, None)
            end_delimiter = b'\x02\x03'  # The 2-byte end delimiter

            # Initialize data_bytes if it doesn't exist
            if not hasattr(self, 'data_bytes'):
                self.data_bytes = bytearray()
            
            # Buffer management: prevent excessive memory usage
            if len(self.data_bytes) > 20000:
                self.data_bytes = self.data_bytes[-10000:]
            
            if self.ser.inWaiting() > 0:
                # Read all available bytes from the serial port
                data = self.ser.read(self.ser.inWaiting())
                self.data_bytes.extend(data)
                
                # CRITICAL FIX: Process all complete messages but only return the LATEST one
                latest_message = None
                
                # Look for the end delimiter in the buffer
                delimiter_index = self.data_bytes.find(end_delimiter)
                while delimiter_index != -1:
                    # End delimiter found
                    # Extract the message up to the delimiter
                    message_data = self.data_bytes[:delimiter_index]
                    
                    # Remove the processed message and delimiter from the buffer
                    self.data_bytes = self.data_bytes[delimiter_index + len(end_delimiter):]
                    
                    if len(message_data) != 8:
                        # Unexpected data length - skip this message
                        delimiter_index = self.data_bytes.find(end_delimiter)
                        continue
                    else:
                        # Deinterleave the data bytes
                        message_id_bytes = message_data[::2]  # Even indices
                        value_bytes = message_data[1::2]     # Odd indices
                        
                        # Convert message_id_bytes to integer (big-endian)
                        message_id = int.from_bytes(message_id_bytes, byteorder='big', signed=False)
                        
                        # Convert value_bytes to float (big-endian)
                        load_cell_value = struct.unpack('>f', value_bytes)[0]
                        
                        # Store as latest message (overwrites older ones - this is the key fix)
                        latest_message = {'value': load_cell_value, 'ID': message_id}
                    
                    # Update delimiter_index for the next iteration
                    delimiter_index = self.data_bytes.find(end_delimiter)
                
                # Return the latest message if found, otherwise None values
                if latest_message is not None:
                    return latest_message
                else:
                    return {'value': None, 'ID': None}
            else:
                # No data available
                return {'value': None, 'ID': None}
            
        # Wireless scales read
        elif self.rig == 1 or self.rig == 2:
            # Also optimised for wireless scales - process all available and return latest
            latest_value = None
            
            # Process all available lines and keep only the latest valid reading
            while self.ser.inWaiting() > 0:
                try:
                    data = self.ser.readline().decode("utf-8")
                    data = float(data.strip())
                    if data != "None":
                        latest_value = data  # Keep updating to get the latest value
                except ValueError:
                    # Skip invalid data
                    continue
            
            # Return the latest value found, or None if no valid data
            if latest_value is not None:
                return {'value': latest_value}
            else:
                return {'value': None}
            
    def clear_buffer(self):
        # clears the serial buffer
        self.ser.read_all()  # clear the serial buffer
        

    def calibrate(self):
        if self.rig == 3 or self.rig == 4:
            self.ser.write(b't')
            time.sleep(3)
            self.ser.write(b's')

        # calibrates the scales by taking an empty reading and a 100g reading.
        print("Empty the scale, press any key to continue..."); input()
        print("Reading...")
        self.ser.read_all()  # clear the serial buffer       

        sum = 0
        iterations = 50
        no_of_reads = 0
        while True:
            raw = self.raw_read()
            data = raw['value']
            if data != None:
                sum += data
                no_of_reads += 1
            if no_of_reads == iterations:
                break
        empty = sum / iterations
        print(empty)

        print("Place 100g on the scale, press any key to continue when ready..."); input()
        print("Reading...")

        self.ser.read_all()

        sum = 0
        iterations = 50
        no_of_reads = 0
        while True:
            raw = self.raw_read()
            data = raw['value']
            if data != None:
                sum += data
                no_of_reads += 1
            if no_of_reads == iterations:
                break
        hundred_grams = sum / iterations
        print(hundred_grams)

        gradient = 100000/(hundred_grams-empty)   # 100,000 = 100g
        print(f"scale = {gradient},\nintercept = {empty}")

        self.ser.write(b'e')

    def get_mass(self):
        # returns a calibrated mass value if available. If not, like most of the time, then returns None
        while(True):
            raw = self.raw_read()
            if 'ID' in raw:
                data = raw['value']
                id = raw['ID']
                if data != None:
                    return {'ID': id, 'value': ((data-self.intercept)*self.scale)/1000}
                else:
                    return {'value': None, 'ID': None}
            elif 'value' in raw:
                data = raw['value']
                if data != None:
                    return {'value': ((data-self.intercept)*self.scale)/1000}
                else:
                    return {'value': None}
            else:
                raise ValueError("Unexpected data format")


    def get_average_weight(self, number_of_samples):
        # returns the average weight of the mouse over a number of samples
        # beware that multiple samples can take a long time.
        self.ser.read_all()
        sum = 0
        no_of_reads = 0
        while True:
            if self.get_mass() != None:
                sum += self.get_mass()
                no_of_reads += 1
            if no_of_reads == number_of_samples:
                return sum/number_of_samples
            
    
    def weight_with_frequency(self):
        # Returns weight and calculates frequency of incoming messages
        data = self.get_mass()
        if data is not None:
            self.most_recent_scales_value = data

            # Measure time and calculate frequency
            current_time = time.time()
            if self.previous_time is not None:
                time_difference = current_time - self.previous_time
                frequency = round(1 / time_difference, 2) if time_difference > 0 else float('inf')
            else:
                frequency = None  # Not enough data to calculate frequency

            self.previous_time = current_time  # Update the previous time
            print(frequency)
        else:
            return None

    def weight(self):
        
        # Returns weight from scales. If no new data, returns most recent value.
        # Also adds scales data to scales_data list.

        raw = self.get_mass()
        if 'ID' in raw:
            id = raw['ID']
            data = raw['value']
            if data != None:
                self.most_recent_scales_value = {'ID': id,'value': data}
                return {'ID': id,'value': data}
            else:
                return self.most_recent_scales_value
        elif 'value' in raw:
            data = raw['value']
            if data != None:
                self.most_recent_scales_value = {'value': data}
                return {'value': data}
            else:
                return self.most_recent_scales_value
    

def test_scales(scales):
    # Send 'e' to reset acquisition
    scales.ser.write(b'e')  # Explicitly send 's' as a byte

    # Send 't' to tare acquisition
    scales.ser.write(b't')
    time.sleep(3)
    # clear input:
    scales.clear_buffer()

    # Send 's' to start acquisition
    scales.ser.write(b's')

    # start = time.perf_counter()
    # while True:
    #     # print(scales.weight())
    #     # print(scales.weight_with_frequency())
    #     print(scales.weight())
    #     # time.sleep(0.1)
    #     if time.perf_counter() - start > 10:
    #         break

    # Send 'e' to stop acquisition
    scales.ser.write(b'e')

    scales.ser.close()

    
if __name__ == '__main__':


<<<<<<< HEAD
    scales = Scales(rig=1)
=======
    scales = Scales(rig=4)
>>>>>>> hex-behav-code-v2.0

    scales.calibrate()
        
    while True:
        # id, data = scales.weight()
        raw = scales.weight()
        if 'ID' in raw:
            id = raw['ID']
            data = raw['value']
            print(f"{id}: {data}")
        elif 'value' in raw:
            data = raw['value']
            print(data)
        else:
            print("No data")

        if keyboard.is_pressed("esc"):
            break
    


