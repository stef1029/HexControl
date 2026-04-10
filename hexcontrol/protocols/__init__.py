"""
Behaviour Protocols

Each protocol file should define a class-based protocol (inherits from BaseProtocol):
    class MyProtocol(BaseProtocol):
        @classmethod
        def get_name(cls) -> str: ...
        @classmethod
        def get_parameters(cls) -> list: ...
        def _run_protocol(self) -> None: ...

Protocols are auto-loaded from .py files in this folder.
"""

import importlib.util
import inspect
import logging
import sys
from pathlib import Path

from hexcontrol.core.protocol_base import BaseProtocol

logger = logging.getLogger(__name__)


def get_available_protocols() -> list[type]:
    """Load all protocols from this folder."""
    protocols = []
    protocols_dir = Path(__file__).parent
    
    # No sys.path manipulation needed — hexcontrol is installed as a package.
    
    for py_file in protocols_dir.glob("*.py"):
        # Skip __init__.py and private files
        if py_file.name.startswith("_"):
            continue
        
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find class-based protocols (BaseProtocol subclasses)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (obj is not BaseProtocol and 
                    issubclass(obj, BaseProtocol) and 
                    obj.__module__ == module.__name__):
                    protocols.append(obj)
        
        except Exception as e:
            logger.warning(f"Failed to load {py_file.name}: {e}")
    
    return protocols
