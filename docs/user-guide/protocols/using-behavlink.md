# Using BehavLink in Protocols

Inside `_run_protocol()`, the hardware is controlled through `self.link`, which is a `BehaviourRigLink` instance. This page covers the most common hardware operations you'll use when writing protocols.

For the full library reference including wire-level details, see [BehavLink Reference](../../reference/behavlink/index.md).

## LEDs

Each of the 6 ports has an LED for visual cues.

```python
# Turn on LED at port 0 with full brightness
self.link.led_set(0, 255)

# Dim LED at port 2 to half brightness
self.link.led_set(2, 128)

# Turn off LED at port 0
self.link.led_set(0, 0)
```

- **port**: 0-5 (which of the 6 reward ports)
- **brightness**: 0-255 (0 = off, 255 = full brightness)

## Spotlights

Each port has a spotlight (hardware PWM, flicker-free) used for illumination or punishment.

```python
# Turn on all spotlights at full brightness (punishment)
self.link.spotlight_set(255, 255)

# Turn off all spotlights
self.link.spotlight_set(255, 0)

# Set specific port spotlight
self.link.spotlight_set(port, brightness)
```

- **port**: 0-5 for individual ports, or 255 for all ports
- **brightness**: 0-255

## Solenoid valves (reward delivery)

Each port has a solenoid valve that delivers liquid reward when pulsed.

```python
# Deliver reward at port 0 using the calibrated duration
self.link.valve_pulse(0, self.reward_durations[0])

# Deliver reward with a custom duration (ms)
self.link.valve_pulse(0, 300)
```

- **port**: 0-5
- **duration_ms**: Pulse duration in milliseconds (1-65535)

!!! important
    Always use `self.reward_durations[port]` for reward delivery. These values are calibrated per solenoid in `rigs.yaml` to deliver consistent reward volumes across ports.

## Speaker (audio cues)

The overhead I2C speaker plays preset tones.

```python
from BehavLink import SpeakerFrequency, SpeakerDuration

# Play a 3300 Hz tone for 500ms
self.link.speaker_set(SpeakerFrequency.FREQ_3300_HZ, SpeakerDuration.DURATION_500_MS)

# Play continuous tone (must be stopped manually)
self.link.speaker_set(SpeakerFrequency.FREQ_1000_HZ, SpeakerDuration.CONTINUOUS)

# Stop the speaker
self.link.speaker_set(SpeakerFrequency.OFF, SpeakerDuration.OFF)
```

Available frequencies: `OFF`, `FREQ_1000_HZ` through `FREQ_7000_HZ`.

Available durations: `OFF`, `DURATION_50_MS`, `DURATION_100_MS`, `DURATION_200_MS`, `DURATION_500_MS`, `DURATION_1000_MS`, `DURATION_2000_MS`, `CONTINUOUS`.

## Buzzers

Each port has a piezo buzzer.

```python
# Turn on buzzer at port 0
self.link.buzzer_set(0, True)

# Turn off buzzer at port 0
self.link.buzzer_set(0, False)
```

## IR illuminator

Controls the infrared illuminator for camera recording.

```python
# Set IR brightness (0-255)
self.link.ir_set(200)

# Turn off IR
self.link.ir_set(0)
```

## Sensor events (IR beam breaks)

Each port has an IR sensor that detects nose-pokes. Use `wait_for_event()` to wait for the next beam break.

```python
# Wait up to 10 seconds for any sensor event
event = self.link.wait_for_event(timeout=10.0)

if event is None:
    # Timeout -- no sensor triggered
    pass
else:
    # event.port = which port was activated (0-5)
    # event.is_activation = True (beam broken) or False (beam restored)
    # event.timestamp_ms = Arduino timestamp in ms
    print(f"Port {event.port} triggered at {event.timestamp_ms}ms")
```

### Typical response-window pattern

```python
trial_start = self.now()
event = None

while True:
    if self.check_stop():
        break

    elapsed = self.now() - trial_start

    # Check for timeout
    if elapsed >= response_timeout:
        break

    # Wait for event with short timeout for responsive stopping
    remaining = response_timeout - elapsed
    event = self.link.wait_for_event(timeout=min(0.1, remaining))
    if event is not None:
        break
```

!!! note
    Use short timeouts (0.1s) in the `wait_for_event()` call inside a loop, and check `self.check_stop()` each iteration. This ensures the protocol responds promptly to stop requests.

### Other event methods

```python
# Get the most recent event without waiting (non-blocking)
event = self.link.get_latest_event(port=0)

# Drain all pending events (clear the buffer)
events = self.link.drain_events()
```

## GPIO

Six configurable GPIO pins for custom hardware.

```python
from BehavLink import GPIOMode

# Configure pin 0 as output
self.link.gpio_configure(0, GPIOMode.OUTPUT)

# Set pin 0 high
self.link.gpio_set(0, True)

# Configure pin 1 as input (generates events on change)
self.link.gpio_configure(1, GPIOMode.INPUT)

# Wait for GPIO event
gpio_event = self.link.wait_for_gpio_event(timeout=5.0)
```

## Scales (weight readings)

The platform scales are accessed through `self.scales`:

```python
weight = self.scales.get_weight()
if weight is not None:
    self.log(f"Current weight: {weight:.2f} g")
```

### Platform detection pattern

A common pattern for detecting when the mouse mounts the platform:

```python
weight_threshold = mouse_weight - weight_offset

while not self.check_stop():
    weight = self.scales.get_weight()
    if weight is not None and weight > weight_threshold:
        # Mouse is on the platform
        break
    self.sleep(0.05)
```

## Typical trial structure

Putting it together, here's a typical trial:

```python
# 1. Wait for mouse on platform
while not self.check_stop():
    weight = self.scales.get_weight()
    if weight is not None and weight > weight_threshold:
        break
    self.sleep(0.05)

# 2. Present stimulus
target_port = random.choice(enabled_ports)
tracker.stimulus(target_port)
self.link.led_set(target_port, led_brightness)

# 3. Wait for response
trial_start = self.now()
event = None
while not self.check_stop():
    elapsed = self.now() - trial_start
    if elapsed >= response_timeout:
        break
    event = self.link.wait_for_event(timeout=min(0.1, response_timeout - elapsed))
    if event is not None:
        break

# 4. Turn off stimulus
self.link.led_set(target_port, 0)
trial_duration = self.now() - trial_start

# 5. Evaluate and deliver outcome
if event is None:
    tracker.timeout(correct_port=target_port, trial_duration=trial_duration)
elif event.port == target_port:
    tracker.success(correct_port=target_port, trial_duration=trial_duration)
    self.link.valve_pulse(target_port, self.reward_durations[target_port])
else:
    tracker.failure(correct_port=target_port, chosen_port=event.port,
                    trial_duration=trial_duration)

# 6. Inter-trial interval
self.sleep(iti)
```
