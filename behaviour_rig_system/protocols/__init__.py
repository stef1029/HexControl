"""
Behaviour Protocols

Each protocol file can define either:

1. Class-based protocol (inherits from BaseProtocol):
    class MyProtocol(BaseProtocol):
        @classmethod
        def get_name(cls) -> str: ...
        @classmethod
        def get_parameters(cls) -> list: ...
        def _run_protocol(self) -> None: ...

2. Function-based protocol (simple format):
    NAME = "Protocol Name"
    DESCRIPTION = "What it does"
    PARAMETERS = {...}
    def run(hw, params, log, check_abort): ...

Protocols are auto-loaded from .py files in this folder.
"""

import importlib.util
import inspect
import sys
from pathlib import Path

from core.protocol_base import BaseProtocol
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
            
            # First, look for class-based protocols (BaseProtocol subclasses)
            found_class = False
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (obj is not BaseProtocol and 
                    issubclass(obj, BaseProtocol) and 
                    obj.__module__ == module.__name__):
                    protocols.append(obj)
                    found_class = True
            
            # If no class found, check for function-based format
            if not found_class and all(hasattr(module, attr) for attr in ["NAME", "PARAMETERS", "run"]):
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
