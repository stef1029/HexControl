"""
Session State - Data containers for session lifecycle.

SessionPhase tracks where we are in the session lifecycle.
SessionConfig captures the user's choices at session start.
SessionResult holds the final outcomes for the post-session screen.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class SessionPhase(Enum):
    """Where we are in the session lifecycle."""
    IDLE = auto()          # Setup mode, nothing running
    STARTING = auto()      # Hardware init in progress
    RUNNING = auto()       # Protocol executing
    STOPPING = auto()      # Stop requested, waiting for protocol to finish
    CLEANING_UP = auto()   # Hardware shutdown in progress
    COMPLETED = auto()     # Post-session results displayed


@dataclass
class SessionConfig:
    """Immutable config captured when user clicks Start."""
    mouse_id: str
    save_directory: str
    protocol_name: str
    protocol_class: type
    parameters: dict[str, Any]


@dataclass
class SessionResult:
    """Final session outcomes for the post-session screen."""
    status: str                        # "Completed" / "Stopped" / "Error"
    protocol_name: str
    mouse_id: str
    elapsed_time: float
    save_path: str
    performance_report: dict | None
