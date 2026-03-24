"""
Simulated Rig — Unified mock/simulated BehaviourRigLink.

Drop-in replacement for BehaviourRigLink that operates in two modes:

    Interactive (virtual_state provided):
        - Hardware commands update VirtualRigState (so the GUI can visualise)
        - Event-wait methods block on threading.Condition until the GUI
          injects events via VirtualRigState.inject_sensor_event()

    Passive (virtual_state is None):
        - All hardware commands are no-ops
        - Event-wait methods sleep for the timeout, then return None
        - Suitable for headless unit-testing of protocols

Usage:
    from BehavLink.simulation import SimulatedRig, VirtualRigState

    # Interactive mode (with VirtualRigWindow)
    state = VirtualRigState()
    link  = SimulatedRig(serial_port=None, virtual_state=state)

    # Passive / no-op mode (unit tests)
    link  = SimulatedRig()
"""

from __future__ import annotations

import time
from typing import Optional

from BehavLink.link import (
    EventType,
    GPIOEvent,
    GPIOMode,
    SensorEvent,
    SpeakerDuration,
    SpeakerFrequency,
)

from .rig_state import VirtualRigState


class SimulatedRig:
    """
    Unified simulated rig link.

    When *virtual_state* is provided, hardware commands update the shared
    state model so the VirtualRigWindow can render them, and event-wait
    methods block until the user injects events via the GUI.

    When *virtual_state* is ``None`` (default), all commands are silent
    no-ops and event waits return ``None`` after the timeout — suitable
    for automated testing.
    """

    # Constants (match real BehaviourRigLink)
    DEFAULT_RETRIES = 10
    DEFAULT_TIMEOUT = 0.2
    EVENT_BUFFER_SIZE = 1024
    NUM_PORTS = 6
    NUM_GPIO_PINS = 6
    ALL_PORTS = 255

    def __init__(
        self,
        serial_port=None,
        virtual_state: VirtualRigState | None = None,
        *,
        receive_timeout: float = 0.1,
        clock=None,
    ) -> None:
        self._state = virtual_state
        self._interactive = virtual_state is not None
        self._running = False
        self._gpio_modes: dict[int, GPIOMode] = {}
        self._clock = clock  # Optional BehaviourClock for accelerated simulation

    # ── Lifecycle ───────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def shutdown(self) -> None:
        """Reset all outputs (mirrors real link's shutdown)."""
        if self._interactive:
            self._state.reset()
        self._gpio_modes.clear()

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
        if self._interactive:
            self._state.set_led(port, brightness)

    def spotlight_set(self, port: int, brightness: int) -> None:
        if self._interactive:
            self._state.set_spotlight(port, brightness)

    def ir_set(self, brightness: int) -> None:
        if self._interactive:
            self._state.set_ir(brightness)

    def buzzer_set(self, port: int, state: bool) -> None:
        if self._interactive:
            self._state.set_buzzer(port, state)

    def speaker_set(self, frequency: SpeakerFrequency, duration: SpeakerDuration) -> None:
        if self._interactive:
            self._state.set_speaker(int(frequency), int(duration))

    def valve_pulse(self, port: int, duration_ms: int) -> None:
        if self._interactive:
            self._state.set_valve_pulse(port, duration_ms)

    # ── GPIO ────────────────────────────────────────────────────────────

    def gpio_configure(self, pin: int, mode: GPIOMode) -> None:
        self._gpio_modes[pin] = mode
        if self._interactive:
            self._state.set_gpio_mode(pin, mode)

    def gpio_set(self, pin: int, state: bool) -> None:
        if self._interactive:
            self._state.set_gpio_output(pin, state)

    def gpio_get_mode(self, pin: int) -> Optional[GPIOMode]:
        if self._interactive:
            return self._state.get_gpio_mode(pin)
        return self._gpio_modes.get(pin)

    # ── Sensor events ───────────────────────────────────────────────────

    def get_latest_event(self, *, clear_buffer: bool = False) -> Optional[SensorEvent]:
        if not self._interactive:
            return None
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
        if not self._interactive:
            return []
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
        Block until a sensor event arrives.

        In interactive mode, blocks on VirtualRigState's condition until
        the GUI injects an event. In passive mode, sleeps for the timeout
        and returns None.
        """
        if not self._interactive:
            if timeout is not None:
                real_t = self._clock.real_timeout(timeout) if self._clock else timeout
                time.sleep(real_t)
            return None

        cond = self._state._sensor_event_condition
        buf = self._state._sensor_event_buffer

        if drain_first:
            with cond:
                buf.clear()

        real_timeout = self._clock.real_timeout(timeout) if (self._clock and timeout is not None) else timeout
        deadline = None if real_timeout is None else (time.monotonic() + real_timeout)

        with cond:
            while True:
                for i, event in enumerate(buf):
                    if port is not None and event.port != port:
                        continue
                    if consume:
                        del buf[i]
                    return event

                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                else:
                    remaining = None

                cond.wait(timeout=remaining)

                if not self._running:
                    return None

    # ── GPIO events ─────────────────────────────────────────────────────

    def get_latest_gpio_event(self, *, clear_buffer: bool = False) -> Optional[GPIOEvent]:
        if not self._interactive:
            return None
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
        if not self._interactive:
            return []
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
        Block until a GPIO event arrives. Raises TimeoutError on timeout.

        In passive mode, always raises TimeoutError after the timeout.
        """
        if not self._interactive:
            if timeout is not None:
                real_t = self._clock.real_timeout(timeout) if self._clock else timeout
                time.sleep(real_t)
            raise TimeoutError("SimulatedRig: no GPIO events in passive mode")

        cond = self._state._gpio_event_condition
        buf = self._state._gpio_event_buffer

        real_timeout = self._clock.real_timeout(timeout) if (self._clock and timeout is not None) else timeout
        deadline = None if real_timeout is None else (time.monotonic() + real_timeout)

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
                            "SimulatedRig: GPIO event wait timed out"
                        )
                else:
                    remaining = None

                cond.wait(timeout=remaining)

                if not self._running:
                    raise TimeoutError(
                        "SimulatedRig: link stopped during GPIO event wait"
                    )

    # ── Event acknowledgement ───────────────────────────────────────────

    def acknowledge_event(self, event_id: int, event_type: EventType) -> None:
        pass  # No ACK needed in simulation
