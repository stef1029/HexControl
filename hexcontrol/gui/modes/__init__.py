"""
GUI Modes for Behaviour Rig System.

Each mode represents a distinct phase of the session lifecycle:
    - SetupMode: Configure and start a session
    - RunningMode: Monitor an active session
    - PostSessionMode: Review completed session
"""

from .setup_mode import SetupMode
from .running_mode import RunningMode
from .post_session_mode import PostSessionMode

__all__ = ["SetupMode", "RunningMode", "PostSessionMode"]
