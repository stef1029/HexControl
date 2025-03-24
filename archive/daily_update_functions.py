import pandas as pd
import sys
from tabulate import tabulate
import json

def generate_text_summary(cohort_instance, sessions):
    """
    Generate a summary table from a list of Session objects and the cohort instance.
    """
    # Collect table data
    table_data = []

    # To keep track of the dates that have already been added
    displayed_dates = set()

    for session in sessions:
        session_dict = session.session_dict
        session_id = session.session_ID
        session_date_str = session_id[:6]
        session_date = pd.to_datetime(session_date_str, format='%y%m%d').date()
        mouse = session_dict['mouse_id']
        
        # Retrieve additional data from cohort_instance
        cohort_data = cohort_instance.get_session(session_id, concise=True)
        behavior_phase = cohort_data.get('Behaviour_phase')
        total_trials = cohort_data.get('total_trials')
        video_length = cohort_data.get('video_length')

        num_trials = len(session.trials)
        successes = sum(1 for trial in session.trials if trial.get("success"))
        failures = num_trials - successes
        timeouts = sum(1 for trial in session.trials if not trial.get("next_sensor"))

        # Check if the date has already been displayed
        if session_date in displayed_dates:
            table_data.append([
                "", mouse, total_trials, behavior_phase, 1, video_length, 
                session_id, num_trials, successes, failures, timeouts
            ])
        else:
            table_data.append([
                session_date, mouse, total_trials, behavior_phase, 1, video_length, 
                session_id, num_trials, successes, failures, timeouts
            ])
            displayed_dates.add(session_date)

    # Define table headers
    headers = [
        "Session Date", "Mouse", "Total Trials", "Behavior Phases", "Session Count", 
        "Video Lengths", "Session ID", "Number of Trials", "Successes", "Failures", "Timeouts"
    ]

    # Print the table
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def generate_text_summary_by_mouse(cohort_instance, sessions):
    """
    Generate a summary table sorted by mouse from a list of Session objects and the cohort instance.
    """
    # Collect table data
    table_data = []

    # To keep track of the mice that have already been added
    displayed_mice = set()

    for session in sessions:
        session_dict = session.session_dict
        session_id = session.session_ID
        session_date_str = session_id[:6]
        session_date = pd.to_datetime(session_date_str, format='%y%m%d').date()
        mouse = session_dict['mouse_id']
        
        # Retrieve additional data from cohort_instance
        cohort_data = cohort_instance.get_session(session_id, concise=True)
        behavior_phase = cohort_data.get('Behaviour_phase')
        video_length = cohort_data.get('video_length')

        num_trials = len(session.trials)
        successes = sum(1 for trial in session.trials if trial.get("success"))
        failures = num_trials - successes
        timeouts = sum(1 for trial in session.trials if not trial.get("next_sensor"))
        percentage_success = (successes / (successes + failures + timeouts)) * 100 if (successes + failures + timeouts) > 0 else 0

        # Check if the mouse has already been displayed
        if mouse in displayed_mice:
            table_data.append([
                "", session_date, video_length, behavior_phase, num_trials, 
                successes, failures, timeouts, f"{percentage_success:.2f}%"
            ])
        else:
            table_data.append([
                mouse, session_date, video_length, behavior_phase, num_trials, 
                successes, failures, timeouts, f"{percentage_success:.2f}%"
            ])
            displayed_mice.add(mouse)

    # Define table headers
    headers = [
        "Mouse", "Session Date", "Video Lengths", "Behavior Phases", "Number of Trials", 
        "Successes", "Failures", "Timeouts", "Percentage Success"
    ]

    # Print the table
    print(tabulate(table_data, headers=headers, tablefmt="grid"))