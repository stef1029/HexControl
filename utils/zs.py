import serial
import time

class ScaleZeroing:
    def __init__(self, rig, baudrate=9600):
        # Initialize rig-specific settings
        if rig == 3:
            self.port = "COM10"
        elif rig == 4:
            self.port = "COM8"
        else:
            raise ValueError("Rig number not recognized")
        
        self.baudrate = baudrate

    def zero_scale(self):
        try:
            # Open serial connection
            with serial.Serial(self.port, self.baudrate, timeout=2) as ser:
                # Send 'e' to end acquisition
                ser.write(b'e')
                time.sleep(2)  # Wait for 2 seconds
                
                # Send 't' to tare
                ser.write(b't')
                time.sleep(3)  # Wait for 3 seconds
                return True
        except Exception as e:
            # Return the error message in case of failure
            return str(e)

if __name__ == "__main__":
    rigs_to_zero = [3, 4]
    failed_rigs = []

    print("Starting scale zeroing process...")
    for rig in rigs_to_zero:
        print(f"Processing rig {rig}...")
        try:
            scale = ScaleZeroing(rig)
            result = scale.zero_scale()
            if result is True:
                print(f"Rig {rig}: Zeroing successful.")
            else:
                print(f"Rig {rig}: Zeroing failed. Error: {result}")
                failed_rigs.append(rig)
        except Exception as e:
            print(f"Rig {rig}: Failed to initialize. Error: {e}")
            failed_rigs.append(rig)

    # Summary of results
    if failed_rigs:
        print("\nSummary of failures:")
        for rig in failed_rigs:
            print(f"Rig {rig} failed.")
    else:
        print("\nAll rigs zeroed successfully.")
