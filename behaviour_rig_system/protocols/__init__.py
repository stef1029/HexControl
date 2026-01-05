"""
Behaviour Protocols

Each protocol file defines:
    NAME = "Protocol Name"
    DESCRIPTION = "What it does"
    PARAMETERS = {...}
    def run(hw, params, log, check_abort): ...

Protocols are auto-loaded from .py files in this folder.
"""

import importlib.util
import sys
from pathlib import Path

from core.protocol_loader import create_protocol_class


def get_available_protocols() -> list[type]:
    """Load all protocols from this folder."""
    protocols = []
    protocols_dir = Path(__file__).parent
    
    # Ensure parent is in path for imports
    parent = protocols_dir.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    
    for py_file in protocols_dir.glob("*.py"):
        # Skip __init__.py and private files
        if py_file.name.startswith("_"):
            continue
        
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Check for protocol format: NAME, PARAMETERS, run()
            if all(hasattr(module, attr) for attr in ["NAME", "PARAMETERS", "run"]):
                protocol_class = create_protocol_class(
                    name=module.NAME,
                    description=getattr(module, "DESCRIPTION", ""),
                    parameters=module.PARAMETERS,
                    run_func=module.run,
                )
                protocols.append(protocol_class)
        
        except Exception as e:
            print(f"Warning: Failed to load {py_file.name}: {e}")
    
    return protocols
