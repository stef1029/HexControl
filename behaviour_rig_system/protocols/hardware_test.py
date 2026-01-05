"""
Hardware Test

A minimal protocol showing how to write behaviour protocols.
Just define NAME, DESCRIPTION, PARAMETERS, and a run() function.

The run() function receives:
    - link: BehaviourRigLink (use link.led_set(), link.valve_pulse(), etc.)
    - params: Dict of parameter values from GUI
    - log: Function to print messages to GUI
    - check_abort: Function returning True if user clicked Stop

Available BehavLink functions:
    link.led_set(port, brightness)      # port 0-5, brightness 0-255
    link.spotlight_set(port, brightness) # port 0-5 or 255 for all
    link.ir_set(brightness)             # brightness 0-255
    link.buzzer_set(port, state)        # port 0-5 or 255, state True/False
    link.valve_pulse(port, duration_ms) # port 0-5, duration 1-65535
    link.speaker_set(frequency, duration) # use SpeakerFrequency/SpeakerDuration enums
    link.wait_for_event(timeout=...)    # wait for sensor event
    link.drain_events()                 # clear event buffer
"""

import random
import time

NAME = "Hardware Test"
DESCRIPTION = "Runs trials activating LED, buzzer, solenoid on random ports."

PARAMETERS = {
    "num_trials": {"default": 10, "label": "Number of Trials"},
    "trial_duration": {"default": 0.5, "label": "Trial Duration (s)"},
    "iti": {"default": 1.0, "label": "Inter-Trial Interval (s)"},
    "led_brightness": {"default": 200, "label": "LED Brightness (0-255)"},
    "valve_duration": {"default": 50, "label": "Valve Pulse (ms)"},
    "use_buzzer": {"default": True, "label": "Use Buzzer"},
}


def run(link, params, log, check_abort):
    """
    Main behaviour loop.
    
    link: BehaviourRigLink - call link.led_set(), link.buzzer_set(), etc.
    params: Dict of parameter values
    log: Function to print to GUI log
    check_abort: Returns True if user clicked Stop
    """
    log(f"Starting {params['num_trials']} trials")
    
    for trial in range(1, params["num_trials"] + 1):
        # Check if user wants to stop
        if check_abort():
            log("Aborted by user")
            return
        
        # Pick random port (0-5)
        port = random.randint(0, 5)
        log(f"Trial {trial}/{params['num_trials']}: Port {port}")
        
        # === STIMULUS ON ===
        link.led_set(port, params["led_brightness"])
        
        if params["use_buzzer"]:
            link.buzzer_set(port, True)
        
        link.valve_pulse(port, params["valve_duration"])
        
        # Wait for trial duration
        time.sleep(params["trial_duration"])
        
        # === STIMULUS OFF ===
        link.led_set(port, 0)
        link.buzzer_set(port, False)
        
        # Inter-trial interval
        if trial < params["num_trials"]:
            time.sleep(params["iti"])
    
    log("Done!")
