"""
Simulated BehaviourRigLink — Interactive mock backed by VirtualRigState.

Drop-in replacement for MockBehaviourRigLink that:
    - Updates VirtualRigState on every hardware command  (LEDs, valves, …)
    - Blocks on threading.Condition in wait_for_event()  until the GUI
      injects a sensor event via VirtualRigState.inject_sensor_event().
    - Provides the exact same public API as BehaviourRigLink / MockBehaviourRigLink.

Usage:
    from core.virtual_rig_state import VirtualRigState
    from BehavLink.simulated import SimulatedBehaviourRigLink, MockSerial

    state = VirtualRigState()
    link  = SimulatedBehaviourRigLink(state)
    link.start()
    link.send_hello()
    link.wait_hello()
    ...
    link.shutdown()
    link.stop()
"""

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

from BehavLink.link import (
    EventType,
    GPIOEvent,
    GPIOMode,
    SensorEvent,
    SpeakerDuration,
    SpeakerFrequency,
)

if TYPE_CHECKING:
    from core.virtual_rig_state import VirtualRigState


class SimulatedBehaviourRigLink:
    """
    Interactive simulated rig link backed by a shared VirtualRigState.

    Hardware commands update the state (so the GUI can visualise them).
    Event-wait methods block on the state's threading.Condition and return
    real SensorEvent / GPIOEvent objects when the user clicks in the
    VirtualRigWindow.
    """

    # Constants (match real class)
    DEFAULT_RETRIES = 10
    DEFAULT_TIMEOUT = 0.2
    EVENT_BUFFER_SIZE = 1024
    NUM_PORTS = 6
    NUM_GPIO_PINS = 6
    ALL_PORTS = 255

    def __init__(self, state: "VirtualRigState", serial_port=None, *, receive_timeout: float = 0.1):
        self._state = state
        self._running = False

    # ── Lifecycle ───────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def shutdown(self) -> None:
        """Reset all outputs (mirrors real link's shutdown)."""
        self._state.reset()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        self.stop()

    # ── Handshake ───────────────────────────────────────────────────────

    def send_hello(self) -> None:
        pass

    def wait_hello(self, timeout: float = 3.0) -> None:
        pass

    # ── Hardware control ────────────────────────────────────────────────

    def led_set(self, port: int, brightness: int) -> None:
        self._state.set_led(port, brightness)

    def spotlight_set(self, port: int, brightness: int) -> None:
        self._state.set_spotlight(port, brightness)

    def ir_set(self, brightness: int) -> None:
        self._state.set_ir(brightness)

    def buzzer_set(self, port: int, state: bool) -> None:
        self._state.set_buzzer(port, state)

    def speaker_set(self, frequency: SpeakerFrequency, duration: SpeakerDuration) -> None:
        self._state.set_speaker(int(frequency), int(duration))

    def valve_pulse(self, port: int, duration_ms: int) -> None:
        self._state.set_valve_pulse(port, duration_ms)

    # ── GPIO ────────────────────────────────────────────────────────────

    def gpio_configure(self, pin: int, mode: GPIOMode) -> None:
        self._state.set_gpio_mode(pin, mode)

    def gpio_set(self, pin: int, state: bool) -> None:
        self._state.set_gpio_output(pin, state)

    def gpio_get_mode(self, pin: int) -> Optional[GPIOMode]:
        return self._state.get_gpio_mode(pin)

    # ── Sensor events ───────────────────────────────────────────────────

    def get_latest_event(self, *, clear_buffer: bool = False) -> Optional[SensorEvent]:
        cond = self._state._sensor_event_condition
        buf = self._state._sensor_event_buffer
        with cond:
            if not buf:
                return None
            event = buf[-1]
            if clear_buffer:
                buf.clear()
            return event

    def drain_events(self) -> list[SensorEvent]:
        cond = self._state._sensor_event_condition
        buf = self._state._sensor_event_buffer
        with cond:
            events = list(buf)
            buf.clear()
            return events

    def wait_for_event(
        self,
        *,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True,
        auto_acknowledge: bool = True,
        drain_first: bool = True,
    ) -> Optional[SensorEvent]:
        """
        Block until a sensor event arrives in the buffer (injected by GUI).

        Mirrors the real BehaviourRigLink.wait_for_event() contract:
        - If *drain_first*, clears stale events before waiting.
        - If *port* is set, only returns events matching that port.
        - Returns ``None`` on timeout.
        """
        cond = self._state._sensor_event_condition
        buf = self._state._sensor_event_buffer

        if drain_first:
            with cond:
                buf.clear()

        deadline = None if timeout is None else (time.monotonic() + timeout)

        with cond:
            while True:
                # Scan buffer for matching event
                for i, event in enumerate(buf):
                    if port is not None and event.port != port:
                        continue
                    # Match found
                    if consume:
                        del buf[i]
                    return event

                # Check timeout
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                else:
                    remaining = None

                # Block until notified or timeout
                cond.wait(timeout=remaining)

                # Re-check after wake (could be spurious or shutdown)
                if not self._running:
                    return None

    # ── GPIO events ─────────────────────────────────────────────────────

    def get_latest_gpio_event(self, *, clear_buffer: bool = False) -> Optional[GPIOEvent]:
        cond = self._state._gpio_event_condition
        buf = self._state._gpio_event_buffer
        with cond:
            if not buf:
                return None
            event = buf[-1]
            if clear_buffer:
                buf.clear()
            return event

    def drain_gpio_events(self) -> list[GPIOEvent]:
        cond = self._state._gpio_event_condition
        buf = self._state._gpio_event_buffer
        with cond:
            events = list(buf)
            buf.clear()
            return events

    def wait_for_gpio_event(
        self,
        *,
        pin: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True,
    ) -> GPIOEvent:
        """
        Block until a GPIO event arrives. Raises ``TimeoutError`` on timeout.
        """
        cond = self._state._gpio_event_condition
        buf = self._state._gpio_event_buffer

        deadline = None if timeout is None else (time.monotonic() + timeout)

        with cond:
            while True:
                for i, event in enumerate(buf):
                    if pin is not None and event.pin != pin:
                        continue
                    if consume:
                        del buf[i]
                    return event

                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(
                            "SimulatedBehaviourRigLink: GPIO event wait timed out"
                        )
                else:
                    remaining = None

                cond.wait(timeout=remaining)

                if not self._running:
                    raise TimeoutError(
                        "SimulatedBehaviourRigLink: link stopped during GPIO event wait"
                    )

    # ── Event acknowledgement ───────────────────────────────────────────

    def acknowledge_event(self, event_id: int, event_type: EventType) -> None:
        pass  # No ACK needed in simulation
