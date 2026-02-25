"""
Full Task with Wait Period Protocol (Phase 9c)

A complete behavioural task where:
1. Mouse stands on the pressure plate platform
2. Mouse must wait for a specified duration while on the platform
3. After wait period, a cue (visual LED or audio) indicates the correct port
4. Mouse goes to the correct port for reward
5. Incorrect port touches are penalised with punishment (spotlight)

Supports:
- Visual trials (LED at target port)
- Audio trials (speaker cue, reward at port 0)
- Mixed audio/visual sessions with configurable proportions
- Configurable port selection (any subset of 6 ports)
- Limited or unlimited trial counts

The run() function receives:
    - link: BehaviourRigLink for hardware control
    - params: Dict of parameter values from GUI
    - log: Function to print messages to GUI
    - check_abort: Function returning True if user clicked Stop
    - scales: ScalesClient instance for reading weight
    - perf_tracker: PerformanceTracker for recording trial outcomes
"""

import time
import random

# Try to import speaker enums from BehavLink
try:
    from BehavLink import SpeakerFrequency, SpeakerDuration
    SPEAKER_AVAILABLE = True
except ImportError:
    SPEAKER_AVAILABLE = False
    # Fallback - will use integer codes directly if needed
    class SpeakerFrequency:
        FREQ_3300_HZ = 4
    class SpeakerDuration:
        DURATION_500_MS = 4
        CONTINUOUS = 7


NAME = "Full Task with Wait"
DESCRIPTION = "Complete task: mouse waits on platform, then responds to visual/audio cue for reward."

# Protocol-specific parameters
PARAMETERS = {

    # Cue settings
    "cue_duration": {"default": 0.1, "label": "Cue Duration (s, 0=until response)", "min": 0.0, "max": 30.0},

    # Port selection (checkboxes for each port)
    "port_0_enabled": {"default": True, "label": "Port 0 Enabled"},
    "port_1_enabled": {"default": True, "label": "Port 1 Enabled"},
    "port_2_enabled": {"default": True, "label": "Port 2 Enabled"},
    "port_3_enabled": {"default": True, "label": "Port 3 Enabled"},
    "port_4_enabled": {"default": True, "label": "Port 4 Enabled"},
    "port_5_enabled": {"default": True, "label": "Port 5 Enabled"},

    # Audio settings
    "audio_enabled": {"default": False, "label": "Enable Audio Trials"},
    "audio_proportion": {"default": 6, "label": "Audio Proportion (0=all audio, 6=50:50)", "min": 0, "max": 12},
    
    # Platform settings
    "weight_offset": {"default": 3.0, "label": "Weight Threshold Offset (g)", "min": 0.0, "max": 10.0},
    "platform_settle_time": {"default": 1, "label": "Platform Settle Time (s)", "min": 0.0, "max": 5.0},

    # Trial settings
    "response_timeout": {"default": 10.0, "label": "Response Timeout (s)", "min": 1.0, "max": 60.0},
    "wait_duration": {"default": 0.0, "label": "Wait Duration (s)", "min": 0.0, "max": 10.0},
    "iti": {"default": 1.0, "label": "Inter-Trial Interval (s)", "min": 0.0, "max": 10.0},
    "led_brightness": {"default": 255, "label": "LED Brightness (0-255)", "min": 0, "max": 255},

    # Reward/punishment
    "reward_duration": {"default": 500, "label": "Reward Duration (ms)", "min": 50, "max": 5000},
    "punishment_duration": {"default": 5.0, "label": "Punishment Duration (s)", "min": 0.0, "max": 30.0},
}


def run(link, params, log, check_abort, scales, perf_tracker):
    """Main behaviour loop for the full task with wait period."""
    
    if scales is None:
        log("ERROR: Scales not available!")
        return
    
    # === EXTRACT PARAMETERS ===
    
    # Session parameters (auto-injected)
    mouse_weight = params["mouse_weight"]
    num_trials = params["num_trials"]  # 0 = unlimited
    
    # Calculate weight threshold
    weight_offset = params["weight_offset"]
    weight_threshold = mouse_weight - weight_offset
    
    # Trial timing
    response_timeout = params["response_timeout"]
    wait_duration = params["wait_duration"]
    iti = params["iti"]
    cue_duration = params["cue_duration"]  # 0 = unlimited (until response)
    platform_settle_time = params["platform_settle_time"]
    
    # Cue settings
    led_brightness = params["led_brightness"]
    
    # Reward/punishment
    reward_ms = params["reward_duration"]
    punishment_s = params["punishment_duration"]
    
    # Audio settings
    audio_enabled = params["audio_enabled"]
    audio_proportion = params["audio_proportion"]
    
    # Parse enabled ports from checkboxes
    enabled_ports = []
    for i in range(6):
        if params[f"port_{i}_enabled"]:
            enabled_ports.append(i)  # 0-indexed
    
    if not enabled_ports and not audio_enabled:
        log("ERROR: No ports enabled and audio disabled! Enable at least one port.")
        return
    
    # === BUILD TRIAL ORDER ===
    
    trial_order = None  # None means random selection each trial
    
    if audio_enabled:
        if audio_proportion == 0:
            # All audio trials
            weighted_pool = [6]  # 6 = audio marker
            log("Mode: All audio trials (reward at port 0)")
        else:
            # Mixed audio/visual
            # Build weighted pool: each visual port once, audio marker multiple times
            weighted_pool = enabled_ports.copy()
            for _ in range(audio_proportion):
                weighted_pool.append(6)  # 6 = audio marker
            log(f"Mode: Mixed audio/visual (audio proportion: {audio_proportion})")
            log(f"Visual ports: {enabled_ports}")
    else:
        # Visual only
        weighted_pool = enabled_ports.copy()
        log(f"Mode: Visual only, ports: {enabled_ports}")
    
    # If specific number of trials, create randomised order
    if num_trials > 0:
        trial_order = []
        for i in range(num_trials):
            trial_order.append(weighted_pool[i % len(weighted_pool)])
        random.shuffle(trial_order)
    
    # === LOG STARTUP INFO ===
    
    trials_str = "unlimited" if num_trials == 0 else str(num_trials)
    log(f"Starting Full Task with Wait Period")
    log(f"  Mouse weight: {mouse_weight}g, threshold: {weight_threshold:.1f}g")
    log(f"  Trials: {trials_str}")
    log(f"  Wait duration: {wait_duration}s, Response timeout: {response_timeout}s")
    if cue_duration > 0:
        log(f"  Cue duration: {cue_duration}s (limited)")
    else:
        log(f"  Cue duration: unlimited (until response)")
    log("---")
    
    # === MAIN TRIAL LOOP ===
    
    trial_num = 0
    
    while True:
        # Check trial limit
        if num_trials > 0 and trial_num >= num_trials:
            log(f"Completed {num_trials} trials")
            break
        
        if check_abort():
            log("Aborted by user")
            break
        
        # === WAIT FOR MOUSE ON PLATFORM ===
        
        platform_ready = False
        while not check_abort() and not platform_ready:
            weight = scales.get_weight()
            if weight is not None and weight > weight_threshold:
                # Mouse detected, start settle timer
                settle_start = time.time()
                settled = True
                
                # Actively monitor weight during settle period
                while time.time() - settle_start < platform_settle_time:
                    if check_abort():
                        break
                    weight = scales.get_weight()
                    if weight is None or weight < weight_threshold:
                        # Mouse left during settle - restart
                        settled = False
                        break
                    time.sleep(0.02)
                
                if settled and not check_abort():
                    # Final confirmation
                    weight = scales.get_weight()
                    if weight is not None and weight > weight_threshold:
                        platform_ready = True
            else:
                time.sleep(0.05)
        
        if check_abort():
            break
        
        activation_time = time.time()
        trial_num += 1
        
        # === SELECT PORT/CUE TYPE ===
        
        if trial_order is not None:
            port = trial_order[trial_num - 1]
        else:
            port = random.choice(weighted_pool)
        
        is_audio = (port == 6)
        
        if is_audio:
            cue_type = "audio"
            target_port = 0  # Audio trials reward at port 0
        else:
            cue_type = "visual"
            target_port = port
        
        # === WAIT PERIOD ===
        
        wait_complete = False
        wait_start = time.time()
        
        while not check_abort():
            elapsed = time.time() - activation_time
            
            # Check weight during wait
            weight = scales.get_weight()
            if weight is None or weight < weight_threshold:
                # Mouse left platform during wait
                log(f"  Mouse left platform during wait period")
                break
            
            # Check if wait duration completed
            if elapsed >= wait_duration:
                wait_complete = True
                break
            
            time.sleep(0.02)
        
        if check_abort():
            break
        
        if not wait_complete:
            # Mouse left early - don't count as trial, continue to next
            trial_num -= 1
            time.sleep(iti)
            continue
        
        # === PRESENT CUE ===
        
        perf_tracker.stimulus(target_port)
        trial_start_time = time.time()
        
        if is_audio:
            # Play audio cue
            try:
                link.speaker_set(SpeakerFrequency.FREQ_3300_HZ, SpeakerDuration.DURATION_500_MS)
            except Exception as e:
                log(f"  Warning: Could not play audio cue: {e}")
        else:
            # Turn on LED at target port
            link.led_set(target_port, led_brightness)
        
        # === WAIT FOR RESPONSE ===
        
        # If cue_duration > 0, turn off cue after that time but keep waiting for response
        # Response timeout is always the full window for the mouse to respond
        cue_on = True
        event = None
        
        while True:
            if check_abort():
                break
            
            elapsed = time.time() - trial_start_time
            
            # Turn off cue after cue_duration (if limited)
            if cue_on and cue_duration > 0 and elapsed >= cue_duration:
                if not is_audio:
                    link.led_set(target_port, 0)
                cue_on = False
            
            # Check for timeout
            if elapsed >= response_timeout:
                break
            
            # Check for event (non-blocking with short timeout)
            remaining = response_timeout - elapsed
            event = link.wait_for_event(timeout=min(0.1, remaining))
            if event is not None:
                break
        
        trial_duration = time.time() - trial_start_time
        
        # === TURN OFF CUE (if still on) ===
        
        if cue_on and not is_audio:
            link.led_set(target_port, 0)
        
        # === PROCESS RESPONSE ===
        
        if event is None:
            # Timeout - no response
            perf_tracker.timeout(correct_port=target_port, trial_duration=trial_duration)
            log(f"  TIMEOUT - no response in {effective_timeout:.1f}s")
        
        elif event.port == target_port:
            # Correct response!
            perf_tracker.success(correct_port=target_port, trial_duration=trial_duration)
            link.valve_pulse(target_port, reward_ms)
            log(f"  SUCCESS - correct port {event.port}, reward delivered")
        
        else:
            # Incorrect response
            perf_tracker.failure(
                correct_port=target_port,
                chosen_port=event.port,
                trial_duration=trial_duration
            )
            log(f"  FAILURE - chose port {event.port}, expected port {target_port}")
            
            # Punishment (spotlights on)
            if punishment_s > 0:
                link.spotlight_set(255, 255)  # All spotlights on
                time.sleep(punishment_s)
                link.spotlight_set(255, 0)    # All spotlights off
        
        # === INTER-TRIAL INTERVAL ===
        
        if not check_abort() and iti > 0:
            time.sleep(iti)
    
