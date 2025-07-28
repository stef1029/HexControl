"""
Phase module initialization.
This allows dynamic loading of phase modules based on phase name.
"""

import importlib.util
import sys

def get_phase_module(phase_name):
    """
    Dynamically load and return the module for the specified phase.
    
    Args:
        phase_name (str): The phase name/number (e.g., "2", "9c")
        
    Returns:
        module or None: The loaded module if found, None otherwise
    """
    # Standardize phase name for import
    module_name = f"phase_{phase_name}"
    
    try:
        # Try to import the module
        return importlib.import_module(f"phases.{module_name}")
    except ImportError:
        print(f"Warning: Could not import module for phase {phase_name}")
        return None