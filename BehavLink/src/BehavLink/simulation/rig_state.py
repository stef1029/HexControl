"""
Virtual Rig State — Thread-safe shared state model for the simulated rig.

Holds the complete hardware state (LEDs, spotlights, valves, speaker, IR,
GPIOs, platform weight) and provides methods for:
    - Hardware commands to update state       (called from protocol thread)
    - GUI to inject sensor / GPIO events      (called from tkinter thread)
    - Dirty-flag based change notification    (polled by GUI at fixed rate)

The same VirtualRigState instance is shared between:
    - SimulatedRig               (reads/writes hardware state, waits for events)
    - ScalesManager (simulated)  (reads platform_weight)
    - VirtualRigWindow           (reads state for drawing, writes events on click)

Performance notes:
    - State mutations set a ``_dirty`` flag instead of calling observers
      synchronously. The GUI polls ``take_snapshot_if_dirty()`` at a fixed
      frame rate (~30 Hz) to avoid flooding the tkinter event queue.
    - Observer list + snapshot are copied under lock, then called outside
      the lock to avoid blocking the protocol thread on tkinter.
    - Fired timers are pruned on each valve/speaker reset.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from BehavLink.link import (
    EventType,
    GPIOEvent,
    GPIOMode,
    SensorEvent,
)


# ── Snapshot for observer callbacks ─────────────────────────────────────────

@dataclass(frozen=True)
class RigStateSnapshot:
    """Immutable snapshot of the virtual rig state for GUI rendering."""
    led_brightness: tuple[int, ...]          # length 6
    spotlight_brightness: tuple[int, ...]    # length 6
    ir_brightness: int
    buzzer_state: tuple[bool, ...]           # length 6
    noise_state: tuple[bool, ...]            # length 6
    speaker_active: bool
    speaker_frequency: int
    speaker_duration: int
    valve_pulsing: tuple[bool, ...]          # length 6
    platform_weight: float
    gpio_modes: tuple[Optional[GPIOMode], ...]   # length 4
    gpio_output_states: tuple[bool, ...]         # length 4
    daq_link_states: tuple[bool, ...]            # length 2


# ── Main state class ───────────────────────────────────────────────────────

class VirtualRigState:
    """
    Thread-safe model of the virtual rig hardware.

    All public setters acquire ``_lock``, mutate state, and set ``_dirty = True``.
    The GUI calls ``take_snapshot_if_dirty()`` on a timer (~30 Hz) to get the
    latest state only when something has actually changed.
    """

    NUM_PORTS = 6
    NUM_GPIO_PINS = 4
    NUM_DAQ_LINK_PINS = 2
    EVENT_BUFFER_SIZE = 1024

    def __init__(self, clock=None) -> None:
        self._clock = clock  # Optional BehaviourClock for accelerated simulation
        self._lock = threading.Lock()

        # Hardware state
        self._led_brightness: list[int] = [0] * self.NUM_PORTS
        self._spotlight_brightness: list[int] = [0] * self.NUM_PORTS
        self._ir_brightness: int = 0
        self._buzzer_state: list[bool] = [False] * self.NUM_PORTS
        self._noise_state: list[bool] = [False] * self.NUM_PORTS
        self._speaker_active: bool = False
        self._speaker_frequency: int = 0
        self._speaker_duration: int = 0
        self._valve_pulsing: list[bool] = [False] * self.NUM_PORTS
        self._platform_weight: float = 0.0

        # GPIO
        self._gpio_modes: list[Optional[GPIOMode]] = [None] * self.NUM_GPIO_PINS
        self._gpio_output_states: list[bool] = [False] * self.NUM_GPIO_PINS

        # DAQ link pins
        self._daq_link_states: list[bool] = [False] * self.NUM_DAQ_LINK_PINS

        # Dirty flag — set by every mutation, cleared by take_snapshot_if_dirty()
        # Starts True so the GUI renders the initial state on its first poll tick.
        self._dirty: bool = True

        # Sensor event injection
        self._sensor_event_buffer: deque[SensorEvent] = deque(maxlen=self.EVENT_BUFFER_SIZE)
        self._sensor_event_condition = threading.Condition(threading.Lock())
        self._next_sensor_event_id: int = 1

        # GPIO event injection
        self._gpio_event_buffer: deque[GPIOEvent] = deque(maxlen=self.EVENT_BUFFER_SIZE)
        self._gpio_event_condition = threading.Condition(threading.Lock())
        self._next_gpio_event_id: int = 1

        # Timers for auto-reset (valve pulses, speaker)
        self._active_timers: list[threading.Timer] = []

        # Cue notification — set when any cue (LED, buzzer, speaker) activates.
        # SimulatedMouse waits on this instead of polling, so it never misses
        # brief cues at high simulation speeds.
        self._cue_event = threading.Event()

    # ── Snapshot / dirty-flag API ───────────────────────────────────────

    def take_snapshot_if_dirty(self) -> Optional[RigStateSnapshot]:
        """
        If state has changed since the last call, return a snapshot and clear
        the dirty flag.  Otherwise return ``None``.

        Designed to be called at a fixed rate by the GUI polling loop so that
        multiple rapid mutations are coalesced into a single redraw.
        """
        with self._lock:
            if not self._dirty:
                return None
            self._dirty = False
            return self._snapshot_unlocked()

    def snapshot(self) -> RigStateSnapshot:
        """Return an immutable snapshot (always, regardless of dirty flag)."""
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> RigStateSnapshot:
        """Build a snapshot.  Caller must hold ``_lock``."""
        return RigStateSnapshot(
            led_brightness=tuple(self._led_brightness),
            spotlight_brightness=tuple(self._spotlight_brightness),
            ir_brightness=self._ir_brightness,
            buzzer_state=tuple(self._buzzer_state),
            noise_state=tuple(self._noise_state),
            speaker_active=self._speaker_active,
            speaker_frequency=self._speaker_frequency,
            speaker_duration=self._speaker_duration,
            valve_pulsing=tuple(self._valve_pulsing),
            platform_weight=self._platform_weight,
            gpio_modes=tuple(self._gpio_modes),
            gpio_output_states=tuple(self._gpio_output_states),
            daq_link_states=tuple(self._daq_link_states),
        )

    # ── Hardware setters (called by SimulatedRig) ───────────────────────

    def set_led(self, port: int, brightness: int) -> None:
        with self._lock:
            if port == 255:
                self._led_brightness = [brightness] * self.NUM_PORTS
            else:
                self._led_brightness[port] = brightness
            self._dirty = True
        if brightness > 0:
            self._cue_event.set()

    def set_spotlight(self, port: int, brightness: int) -> None:
        with self._lock:
            if port == 255:
                self._spotlight_brightness = [brightness] * self.NUM_PORTS
            else:
                self._spotlight_brightness[port] = brightness
            self._dirty = True

    def set_ir(self, brightness: int) -> None:
        with self._lock:
            self._ir_brightness = brightness
            self._dirty = True

    def set_buzzer(self, port: int, state: bool) -> None:
        with self._lock:
            if port == 255:
                self._buzzer_state = [state] * self.NUM_PORTS
            else:
                self._buzzer_state[port] = state
            self._dirty = True
        if state:
            self._cue_event.set()

    def set_noise(self, port: int, state: bool) -> None:
        with self._lock:
            if port == 255:
                self._noise_state = [state] * self.NUM_PORTS
            else:
                self._noise_state[port] = state
            self._dirty = True
        if state:
            self._cue_event.set()

    def set_speaker(self, frequency: int, duration: int) -> None:
        """Activate the speaker. Auto-resets after the duration (if not CONTINUOUS)."""
        # Duration enum mapping (ms) — matches SpeakerDuration values
        duration_ms_map = {
            0: 0,     # OFF
            1: 50,
            2: 100,
            3: 200,
            4: 500,
            5: 1000,
            6: 2000,
            7: None,  # CONTINUOUS — no auto-reset
        }

        with self._lock:
            if frequency == 0 or duration == 0:
                self._speaker_active = False
                self._speaker_frequency = 0
                self._speaker_duration = 0
            else:
                self._speaker_active = True
                self._speaker_frequency = frequency
                self._speaker_duration = duration
            self._dirty = True
        if frequency != 0 and duration != 0:
            self._cue_event.set()

        # Auto-reset timer
        ms = duration_ms_map.get(duration)
        if ms is not None and ms > 0 and frequency != 0:
            real_s = ms / 1000.0
            if self._clock:
                real_s = self._clock.real_timeout(real_s)
            t = threading.Timer(real_s, self._reset_speaker)
            t.daemon = True
            t.start()
            with self._lock:
                self._active_timers.append(t)

    def _reset_speaker(self) -> None:
        with self._lock:
            self._speaker_active = False
            self._speaker_frequency = 0
            self._speaker_duration = 0
            self._dirty = True
            self._prune_timers()

    def set_valve_pulse(self, port: int, duration_ms: int) -> None:
        """Start a valve pulse with auto-reset after duration_ms."""
        with self._lock:
            self._valve_pulsing[port] = True
            self._dirty = True

        def _reset():
            with self._lock:
                self._valve_pulsing[port] = False
                self._dirty = True
                self._prune_timers()

        real_s = duration_ms / 1000.0
        if self._clock:
            real_s = self._clock.real_timeout(real_s)
        t = threading.Timer(real_s, _reset)
        t.daemon = True
        t.start()
        with self._lock:
            self._active_timers.append(t)

    def _prune_timers(self) -> None:
        """Remove finished timers from the list. Must be called with _lock held."""
        self._active_timers = [t for t in self._active_timers if t.is_alive()]

    # ── GPIO (called by SimulatedRig) ───────────────────────────────────

    def set_gpio_mode(self, pin: int, mode: GPIOMode) -> None:
        with self._lock:
            self._gpio_modes[pin] = mode
            self._dirty = True

    def get_gpio_mode(self, pin: int) -> Optional[GPIOMode]:
        with self._lock:
            return self._gpio_modes[pin]

    def set_gpio_output(self, pin: int, state: bool) -> None:
        with self._lock:
            self._gpio_output_states[pin] = state
            self._dirty = True

    # ── DAQ link pins (called by SimulatedRig) ──────────────────────────

    def set_daq_link(self, index: int, state: bool) -> None:
        with self._lock:
            self._daq_link_states[index] = state
            self._dirty = True

    # ── Platform weight (set by GUI slider) ─────────────────────────────

    def set_weight(self, weight: float) -> None:
        with self._lock:
            self._platform_weight = weight
            self._dirty = True

    def get_weight(self) -> float:
        with self._lock:
            return self._platform_weight

    # ── Sensor event injection (called by GUI on port click) ────────────

    def inject_sensor_event(self, port: int, is_activation: bool = True) -> None:
        """
        Inject a sensor event as if the mouse broke an IR beam at *port*.

        This wakes any protocol thread blocked in ``wait_for_event()``.
        """
        with self._sensor_event_condition:
            ts = int(self._clock.time() * 1000) & 0xFFFFFFFF if self._clock else int(time.monotonic() * 1000) & 0xFFFFFFFF
            event = SensorEvent(
                event_id=self._next_sensor_event_id,
                port=port,
                is_activation=is_activation,
                timestamp_ms=ts,
                received_time=time.monotonic(),
            )
            self._next_sensor_event_id += 1
            self._sensor_event_buffer.append(event)
            self._sensor_event_condition.notify_all()

    # ── GPIO event injection (called by GUI on GPIO toggle) ─────────────

    def inject_gpio_event(self, pin: int, is_activation: bool = True) -> None:
        """
        Inject a GPIO event as if pin *pin* changed state.

        This wakes any protocol thread blocked in ``wait_for_gpio_event()``.
        """
        with self._gpio_event_condition:
            ts = int(self._clock.time() * 1000) & 0xFFFFFFFF if self._clock else int(time.monotonic() * 1000) & 0xFFFFFFFF
            event = GPIOEvent(
                event_id=self._next_gpio_event_id,
                pin=pin,
                is_activation=is_activation,
                timestamp_ms=ts,
                received_time=time.monotonic(),
            )
            self._next_gpio_event_id += 1
            self._gpio_event_buffer.append(event)
            self._gpio_event_condition.notify_all()

    # ── Shutdown / reset ────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all hardware state to initial values (called on link shutdown)."""
        # Cancel pending timers
        with self._lock:
            for t in self._active_timers:
                t.cancel()
            self._active_timers.clear()

            self._led_brightness = [0] * self.NUM_PORTS
            self._spotlight_brightness = [0] * self.NUM_PORTS
            self._ir_brightness = 0
            self._buzzer_state = [False] * self.NUM_PORTS
            self._noise_state = [False] * self.NUM_PORTS
            self._speaker_active = False
            self._speaker_frequency = 0
            self._speaker_duration = 0
            self._valve_pulsing = [False] * self.NUM_PORTS
            self._gpio_modes = [None] * self.NUM_GPIO_PINS
            self._gpio_output_states = [False] * self.NUM_GPIO_PINS
            self._daq_link_states = [False] * self.NUM_DAQ_LINK_PINS
            self._dirty = True
        self._cue_event.set()  # Wake mouse thread so it can exit

        # Wake any threads blocked on event waits so they can exit
        with self._sensor_event_condition:
            self._sensor_event_condition.notify_all()
        with self._gpio_event_condition:
            self._gpio_event_condition.notify_all()
