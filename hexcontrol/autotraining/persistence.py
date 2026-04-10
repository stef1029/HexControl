"""
Training State Persistence

Saves and loads per-mouse training progress to/from an autotraining_progress
folder. Each mouse gets its own subfolder with:

    autotraining_progress/
        M001/
            training_state.json     <- current stage, history
            training_log.csv        <- append-only record of all transitions

The autotraining_progress folder is separate from the normal session data
folder, so training progression state is kept in one place while raw
session files go to the usual cohort save location.
"""

import csv
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# =============================================================================
# Training state data
# =============================================================================

@dataclass
class TrainingState:
    """
    Persisted training state for a single mouse.

    Loaded at session start, saved at session end.
    """
    mouse_id: str
    current_stage: str
    trials_in_stage: int = 0
    sessions_in_stage: int = 0
    last_session_date: str = ""
    stage_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "mouse_id": self.mouse_id,
            "current_stage": self.current_stage,
            "trials_in_stage": self.trials_in_stage,
            "sessions_in_stage": self.sessions_in_stage,
            "last_session_date": self.last_session_date,
            "stage_history": self.stage_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainingState":
        """Deserialise from a dict (loaded from JSON)."""
        return cls(
            mouse_id=data.get("mouse_id", ""),
            current_stage=data.get("current_stage", ""),
            trials_in_stage=data.get("trials_in_stage", 0),
            sessions_in_stage=data.get("sessions_in_stage", 0),
            last_session_date=data.get("last_session_date", ""),
            stage_history=data.get("stage_history", []),
        )


# =============================================================================
# Load / Save functions
# =============================================================================

def get_mouse_progress_dir(progress_root: str | Path, mouse_id: str) -> Path:
    """
    Get the directory for a specific mouse's training progress.

    Creates the directory if it doesn't exist.
    """
    mouse_dir = Path(progress_root) / mouse_id
    mouse_dir.mkdir(parents=True, exist_ok=True)
    return mouse_dir


def load_training_state(
    progress_root: str | Path,
    mouse_id: str,
    default_stage: str = "",
) -> TrainingState:
    """
    Load a mouse's training state from disk.

    If no state file exists (first session), returns a fresh TrainingState
    starting at the default_stage.

    Args:
        progress_root: Path to the autotraining_progress folder
        mouse_id:      Mouse identifier (e.g. "M001")
        default_stage: Stage name to use if no saved state exists

    Returns:
        TrainingState loaded from JSON, or a fresh default.
    """
    mouse_dir = get_mouse_progress_dir(progress_root, mouse_id)
    state_file = mouse_dir / "training_state.json"

    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TrainingState.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Corrupted file -- log warning and start fresh
            print(f"Warning: Could not load training state for {mouse_id}: {e}")

    # No saved state -- return fresh
    return TrainingState(
        mouse_id=mouse_id,
        current_stage=default_stage,
        trials_in_stage=0,
        sessions_in_stage=0,
        last_session_date="",
        stage_history=[],
    )


def save_training_state(
    progress_root: str | Path,
    mouse_id: str,
    current_stage: str,
    trials_in_stage: int,
    previous_state: TrainingState,
    transition_log: list[dict[str, Any]] | None = None,
) -> None:
    """
    Save a mouse's training state to disk.

    Replays the full transition log (if provided) so that every stage
    visited during the session appears in the history, not just the
    start and end stages.

    Args:
        progress_root:   Path to the autotraining_progress folder
        mouse_id:        Mouse identifier
        current_stage:   Stage name at end of session
        trials_in_stage: Cumulative trial count in the current stage
        previous_state:  The TrainingState that was loaded at session start
        transition_log:  List of transition dicts from engine.get_transition_log()
    """
    mouse_dir = get_mouse_progress_dir(progress_root, mouse_id)
    state_file = mouse_dir / "training_state.json"

    today = datetime.now().strftime("%Y-%m-%d")

    # Build updated history by replaying every transition that occurred
    history = list(previous_state.stage_history)
    transitions = transition_log or []

    if transitions:
        # Replay each transition into the history
        for t in transitions:
            from_stage = t.get("from_stage", "")
            to_stage = t.get("to_stage", "")

            # Close out the from_stage entry if it's the latest in history
            if history and history[-1].get("stage") == from_stage:
                history[-1]["exited"] = today

            # Open a new entry for the to_stage
            history.append({
                "stage": to_stage,
                "entered": today,
                "exited": None,
                "sessions": 1,
            })

        sessions_in_stage = 1
    elif previous_state.current_stage and previous_state.current_stage != current_stage:
        # Stage changed but no transition log provided (shouldn't happen, but handle it)
        if history and history[-1].get("stage") == previous_state.current_stage:
            history[-1]["exited"] = today
        history.append({
            "stage": current_stage,
            "entered": today,
            "exited": None,
            "sessions": 1,
        })
        sessions_in_stage = 1
    else:
        # Same stage as session start -- increment session count
        sessions_in_stage = previous_state.sessions_in_stage + 1
        if history and history[-1].get("stage") == current_stage:
            history[-1]["sessions"] = sessions_in_stage
        else:
            # First ever entry
            history.append({
                "stage": current_stage,
                "entered": today,
                "exited": None,
                "sessions": 1,
            })

    state = TrainingState(
        mouse_id=mouse_id,
        current_stage=current_stage,
        trials_in_stage=trials_in_stage,
        sessions_in_stage=sessions_in_stage,
        last_session_date=today,
        stage_history=history,
    )

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)


def append_transition_log(
    progress_root: str | Path,
    mouse_id: str,
    session_id: str,
    transitions: list[dict[str, Any]],
) -> None:
    """
    Append stage transitions from this session to the mouse's transition log.

    Creates the CSV file with headers if it doesn't exist.

    Args:
        progress_root: Path to the autotraining_progress folder
        mouse_id:      Mouse identifier
        session_id:    Identifier for the current session
        transitions:   List of transition dicts from engine.get_transition_log()
    """
    if not transitions:
        return

    mouse_dir = get_mouse_progress_dir(progress_root, mouse_id)
    log_file = mouse_dir / "training_log.csv"

    file_exists = log_file.exists()
    fieldnames = ["timestamp", "session_id", "from_stage", "to_stage", "trigger", "trial_number"]

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for t in transitions:
            writer.writerow({
                "timestamp": datetime.fromtimestamp(t["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                "session_id": session_id,
                "from_stage": t.get("from_stage", ""),
                "to_stage": t.get("to_stage", ""),
                "trigger": t.get("trigger", ""),
                "trial_number": t.get("trial_number", ""),
            })
