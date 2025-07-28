#!/usr/bin/env python3
import json
import sys

def analyze_message_ids(file_path):
    """
    Analyze message IDs from a JSON file.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        tuple: (max_id, list_length)
    """
    try:
        # Open and read the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Extract the message_ids array
        message_ids = data.get('message_ids', [])
        
        # Check if message_ids exists and is a list
        if not isinstance(message_ids, list):
            print("Error: message_ids is missing or not a list")
            return None, None
        
        # Find the maximum value and length
        max_id = max(message_ids) if message_ids else None
        list_length = len(message_ids)
        
        return max_id, list_length
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        return None, None
    except json.JSONDecodeError:
        print(f"Error: File '{file_path}' contains invalid JSON")
        return None, None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None, None

def main():
    # Set the file path here
    file_path = r"D:\2504_pitx2_ephys_cohort\250409_180636\250409_180643_mtaq14-1j\250409_180643_mtaq14-1j-ArduinoDAQ.json"
    
    # Check if file path was provided as command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    # Analyze the message IDs
    max_id, list_length = analyze_message_ids(file_path)
    
    # Print the results
    if max_id is not None and list_length is not None:
        print(f"Maximum message ID: {max_id}")
        print(f"Number of messages in the list: {list_length}")

if __name__ == "__main__":
    main()