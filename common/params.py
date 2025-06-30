"""
Parameter handling utilities.
"""

import json
import argparse

def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--rig", type=int, help="Rig number")
    parser.add_argument("--path", type=str, help="Folder ID")
    parser.add_argument("--mouse", type=str, help="Mouse ID")
    parser.add_argument("--weight", type=float, help="Mouse weight")
    parser.add_argument("--fps", type=int, help="Frames per second for video recording")
    parser.add_argument("--window_width", type=int, help="Width of the video window")
    parser.add_argument("--window_height", type=int, help="Height of the video window")
    parser.add_argument("--config_json", type=str, help="Path to the configuration JSON file")
    return parser.parse_args()

def load_config(config_path):
    """
    Load configuration from file.
    
    Args:
        config_path (str): Path to configuration file
        
    Returns:
        dict: Configuration data
    """
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config file: {e}")
        return {}
