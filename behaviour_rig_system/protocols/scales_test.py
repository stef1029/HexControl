"""
Scales Test Protocol

A simple protocol using scales for trial initiation.
Mouse stands on platform → LED on → wait for sensor → reward/punish → repeat.

The run() function receives:
    - link: BehaviourRigLink for hardware control
    - params: Dict of parameter values from GUI
    - log: Function to print messages to GUI
    - check_abort: Function returning True if user clicked Stop
    - scales: ScalesClient instance for reading weight (always available)
    - perf_tracker: PerformanceTracker for recording trial outcomes

Scales functions:
    scales.get_weight()  # Returns current weight in grams, or None

Tracker functions:
    perf_tracker.success()   # Record a successful trial
    perf_tracker.failure()   # Record a failed trial  
    perf_tracker.timeout()   # Record a timeout trial
"""

import time

NAME = "Scales Test"
DESCRIPTION = "Mouse stands on platform to start trial, then goes to correct port for reward."

PARAMETERS = {
    "weight_threshold": {"default": 15.0, "label": "Weight Threshold (g)"},
    "num_trials": {"default": 50, "label": "Number of Trials"},
    "target_port": {"default": 0, "label": "Target Port (0-5)"},
    "response_timeout": {"default": 5.0, "label": "Response Timeout (s)"},
    "iti": {"default": 1.0, "label": "Inter-Trial Interval (s)"},
    "reward_duration": {"default": 500, "label": "Reward Duration (ms)"},
    "punishment_duration": {"default": 5.0, "label": "Punishment Duration (s)"},
    "led_brightness": {"default": 255, "label": "LED Brightness (0-255)"},
}


def run(link, params, log, check_abort, scales, perf_tracker):
    """Main behaviour loop."""
    
    if scales is None:
        log("ERROR: Scales not available!")
        return
    
    threshold = params["weight_threshold"]
    num_trials = params["num_trials"]
    target_port = params["target_port"]  # Already 0-indexed
    response_timeout = params["response_timeout"]
    iti = params["iti"]
    reward_ms = params["reward_duration"]
    punishment_s = params["punishment_duration"]
    led_brightness = params["led_brightness"]
    
    
    for trial in range(1, num_trials + 1):
        if check_abort():
            log("Aborted by user")
            break
        
        # === WAIT FOR MOUSE ON SCALES ===
        
        while not check_abort():
            weight = scales.get_weight()
            if weight is not None and weight > threshold:
                break
            time.sleep(0.05)
        
        if check_abort():
            break
        
        weight = scales.get_weight()
        
        # === STIMULUS ON ===
        link.led_set(target_port, led_brightness)
        trial_start_time = time.time()  # Start timing from LED on
        
        # === WAIT FOR RESPONSE ===
        # (wait_for_event auto-drains stale events by default)
        event = link.wait_for_event(timeout=response_timeout)
        
        # Calculate trial duration from LED on to response/timeout
        trial_duration = time.time() - trial_start_time
        
        # === STIMULUS OFF ===
        link.led_set(target_port, 0)
        
        # === PROCESS RESPONSE ===
        if event is None:
            perf_tracker.timeout(correct_port=target_port, trial_duration=trial_duration)
        
        elif event.port == target_port:
            perf_tracker.success(correct_port=target_port, trial_duration=trial_duration)
            link.valve_pulse(target_port, reward_ms)
        
        else:
            perf_tracker.failure(correct_port=target_port, chosen_port=event.port, trial_duration=trial_duration)
            link.spotlight_set(255, 255)  # All spotlights on
            time.sleep(punishment_s)
            link.spotlight_set(255, 0)    # All spotlights off
        
        # === ITI ===
        if trial < num_trials and not check_abort():
            time.sleep(iti)
    
