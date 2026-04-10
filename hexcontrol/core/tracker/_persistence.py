"""
Trial persistence — write trial data from one or more trackers to CSV.

The merged CSV format includes one row per trial across every supplied
tracker, sorted chronologically. Stimulus events captured during each
trial are serialized as JSON in the ``stimulus_log`` column so that
post-session analysis can reconstruct the full sequence of cues.
"""

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING

from ._outcomes import TrialRecord

if TYPE_CHECKING:
    from ._tracker import Tracker


_FIELDNAMES = [
    "tracker",
    "trial_type",
    "trial_number",
    "outcome",
    "time_since_start_s",
    "trial_duration_s",
    "correct_port",
    "chosen_port",
    "stage",
    "stimulus_log",
]


def save_merged_trials(
    trackers: "dict[str, Tracker]",
    save_path: str | Path,
    session_id: str = "",
) -> Path | None:
    """
    Merge trials from multiple trackers into a single CSV.

    All trials from all sub-trackers across all trackers are collected,
    sorted by timestamp for chronological order, and written with a
    global ``trial_number`` index.

    Args:
        trackers:    Dict mapping tracker name to Tracker instance.
        save_path:   Directory where the file should be saved (will be
                     created if missing).
        session_id:  Optional prefix for the filename. The result is
                     ``{session_id}-trials.csv``, or ``trials.csv`` if
                     no session_id is given.

    Returns:
        Path to the saved file, or ``None`` if there were no trials
        across all trackers.
    """
    # Collect (tracker_name, sub_name, trial) tuples from every tracker.
    all_trials: list[tuple[str, str, TrialRecord]] = []
    for tracker_name, tracker in trackers.items():
        for sub_name in tracker.sub_tracker_names:
            sub = tracker.get_sub_tracker(sub_name)
            if sub is None:
                continue
            for trial in sub.get_trials():
                all_trials.append((tracker_name, sub_name, trial))

    if not all_trials:
        return None

    # Chronological order across all trackers
    all_trials.sort(key=lambda t: t[2].timestamp)

    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{session_id}-trials.csv" if session_id else "trials.csv"
    file_path = save_dir / filename

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()

        for global_num, (tracker_name, sub_name, trial) in enumerate(all_trials, start=1):
            row = {
                "tracker": tracker_name,
                "trial_type": sub_name or trial.trial_type,
                "trial_number": global_num,
                "outcome": trial.outcome.value,
                "time_since_start_s": f"{trial.time_since_start:.3f}",
                "trial_duration_s": f"{trial.trial_duration:.3f}",
                "correct_port": (
                    trial.correct_port if trial.correct_port is not None else ""
                ),
                "chosen_port": (
                    trial.chosen_port if trial.chosen_port is not None else ""
                ),
                "stage": trial.details.get("stage", ""),
                "stimulus_log": json.dumps(trial.stimuli) if trial.stimuli else "",
            }
            writer.writerow(row)

    return file_path
