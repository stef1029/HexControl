"""
Post-processing module for behaviour rig system.

Contains functions for batch processing of cohort data.
"""

from .post_process_arduinoDAQ import (
    process_ephys_data,
    process_cohort_directory,
    run_analysis_on_local,
)

__all__ = [
    "process_ephys_data",
    "process_cohort_directory",
    "run_analysis_on_local",
]
