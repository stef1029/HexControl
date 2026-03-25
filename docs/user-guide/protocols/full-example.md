# Full Example Protocol

This page walks through `protocols/full_task_with_wait.py`, a production protocol that demonstrates all major features.

## What it does

The Full Task with Wait protocol runs a complete behavioural session:

1. Mouse mounts the platform (detected by weight on scales)
2. Mouse waits on the platform for a configurable duration
3. A visual cue (LED) and/or audio cue (speaker) indicates the target port
4. Mouse has a limited time to nose-poke the correct port
5. Correct response delivers reward; incorrect response triggers punishment; no response is a timeout
6. Inter-trial interval, then repeat

## Tracker declaration

```python
@classmethod
def get_tracker_definitions(cls) -> list:
    return [TrackerDefinition(name="trials", display_name="Trials")]
```

A single tracker named `"trials"`. The GUI shows one performance tab.

## Parameters

The protocol declares 15 parameters covering:

- **Cue settings**: `cue_duration` (0 = LED stays on until response), `led_brightness`
- **Port selection**: Six `port_N_enabled` booleans
- **Audio**: `audio_enabled` flag, `audio_proportion` (ratio of audio-only to visual trials)
- **Platform detection**: `weight_offset` (subtracted from mouse weight for threshold), `platform_settle_time`
- **Timing**: `response_timeout`, `wait_duration`, `iti`
- **Punishment**: `punishment_duration` (0 = disabled)

!!! note
    The protocol also uses `mouse_weight` and `num_trials` which are injected by the session controller (common parameters not declared in `get_parameters()`).

## Protocol logic walkthrough

### Setup

```python
def _run_protocol(self) -> None:
    params = self.parameters
    scales = self.scales
    perf_tracker = self.perf_trackers.get("trials")

    if scales is None:
        self.log("ERROR: Scales not available!")
        return

    if perf_tracker is not None:
        perf_tracker.reset()
```

Get references to resources, check scales are available, reset the tracker.

### Build port pool

```python
enabled_ports = []
for i in range(6):
    if params[f"port_{i}_enabled"]:
        enabled_ports.append(i)
```

Collects which ports are active for this session.

### Audio/visual mode selection

```python
if audio_enabled:
    if audio_proportion == 0:
        weighted_pool = [6]  # All audio trials
    else:
        weighted_pool = enabled_ports.copy()
        for _ in range(audio_proportion):
            weighted_pool.append(6)  # Port 6 = audio trial
else:
    weighted_pool = enabled_ports.copy()
```

Port index `6` is a sentinel meaning "audio trial" (reward at port 0, but cue is audio instead of LED). The `audio_proportion` controls the ratio: setting it to 6 gives a 50:50 mix with 6 visual ports.

### Trial order

```python
trial_order = []
for i in range(num_trials):
    trial_order.append(weighted_pool[i % len(weighted_pool)])
random.shuffle(trial_order)
```

Pre-generates a shuffled trial sequence ensuring balanced port/modality distribution across the session.

### Platform detection

```python
platform_ready = False
while not self.check_stop() and not platform_ready:
    weight = scales.get_weight()
    if weight is not None and weight > weight_threshold:
        # Settle check: weight must stay above threshold
        settle_start = self.now()
        settled = True
        while self.now() - settle_start < platform_settle_time:
            if self.check_stop():
                break
            weight = scales.get_weight()
            if weight is None or weight < weight_threshold:
                settled = False
                break
            self.sleep(0.02)

        if settled and not self.check_stop():
            weight = scales.get_weight()
            if weight is not None and weight > weight_threshold:
                platform_ready = True
    else:
        self.sleep(0.05)
```

Waits for the mouse to mount and settle on the platform. The settle check requires weight to stay above threshold for `platform_settle_time` seconds, preventing false triggers from brief contacts.

### Wait period

```python
wait_complete = False
while not self.check_stop():
    elapsed = self.now() - activation_time
    weight = scales.get_weight()
    if weight is None or weight < weight_threshold:
        self.log("  Mouse left platform during wait period")
        break
    if elapsed >= wait_duration:
        wait_complete = True
        break
    self.sleep(0.02)
```

The mouse must remain on the platform for `wait_duration` seconds. If it leaves early, the trial is aborted (trial counter decremented) and the protocol returns to waiting for platform detection.

### Stimulus presentation

```python
if is_audio:
    self.link.speaker_set(SpeakerFrequency.FREQ_3300_HZ, SpeakerDuration.DURATION_500_MS)
else:
    self.link.led_set(target_port, led_brightness)
```

Either plays a tone or turns on the LED at the target port, depending on trial type.

### Response window

```python
cue_on = True
event = None
while True:
    if self.check_stop():
        break
    elapsed = self.now() - trial_start_time

    # Turn off cue after cue_duration (if limited)
    if cue_on and cue_duration > 0 and elapsed >= cue_duration:
        if not is_audio:
            self.link.led_set(target_port, 0)
        cue_on = False

    # Check for timeout
    if elapsed >= response_timeout:
        break

    # Poll for sensor event (short timeout for responsiveness)
    remaining = response_timeout - elapsed
    event = self.link.wait_for_event(timeout=min(0.1, remaining))
    if event is not None:
        break
```

Key design decisions:

- **Cue duration**: If `cue_duration > 0`, the LED turns off after that many seconds. If `cue_duration == 0`, it stays on until a response
- **Short poll timeout**: `min(0.1, remaining)` ensures the loop checks `check_stop()` every 100ms even during long timeouts
- **Any sensor event**: The first beam break on any port ends the response window

### Outcome evaluation

```python
if event is None:
    perf_tracker.timeout(correct_port=target_port, trial_duration=trial_duration)
elif event.port == target_port:
    perf_tracker.success(correct_port=target_port, trial_duration=trial_duration)
    self.link.valve_pulse(target_port, self.reward_durations[target_port])
else:
    perf_tracker.failure(correct_port=target_port, chosen_port=event.port,
                         trial_duration=trial_duration)
    if punishment_s > 0:
        self.link.spotlight_set(255, 255)  # All spotlights on
        self.sleep(punishment_s)
        self.link.spotlight_set(255, 0)    # All spotlights off
```

Three outcomes:

- **Timeout**: No response within the window -- record timeout
- **Success**: Correct port -- deliver reward via calibrated valve pulse
- **Failure**: Wrong port -- record failure, optionally deliver punishment (spotlights on for `punishment_duration` seconds)

### Inter-trial interval

```python
if not self.check_stop() and iti > 0:
    self.sleep(iti)
```

Brief pause between trials. Respects stop requests and virtual clock.
