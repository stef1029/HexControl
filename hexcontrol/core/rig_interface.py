"""
RigInterface — structural typing Protocol for ``BehaviourRigLink`` and ``SimulatedRig``.

Both classes satisfy this Protocol implicitly (structural typing, no
inheritance required). Annotating ``BaseProtocol.link: RigInterface``
lets type checkers verify that every method protocols call on the link
actually exists on both the real and simulated implementations.

If you add a method to ``BehaviourRigLink`` and forget to add it to
``SimulatedRig``, a type checker (mypy/pyright) catches the drift.
"""

from __future__ import annotations

from typing import Optional, Protocol

from BehavLink.link import SensorEvent, GPIOEvent, GPIOMode


class RigInterface(Protocol):
    """Structural contract for the hardware control link.

    Satisfied by both ``BehaviourRigLink`` (real hardware) and
    ``SimulatedRig`` (virtual rig). Protocols type-annotate their
    ``self.link`` as ``RigInterface`` and call only these methods.

    Constants:
        NUM_PORTS, NUM_GPIO_PINS, NUM_DAQ_LINK_PINS
    """

    NUM_PORTS: int
    NUM_GPIO_PINS: int
    NUM_DAQ_LINK_PINS: int

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def shutdown(self) -> None: ...
    def send_hello(self) -> None: ...
    def wait_hello(self, timeout: float = 3.0) -> None: ...

    # -- Event reception -----------------------------------------------------

    def wait_for_event(
        self,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True,
        auto_acknowledge: bool = True,
        drain_first: bool = True,
    ) -> Optional[SensorEvent]: ...

    def get_latest_event(self, *, clear_buffer: bool = False) -> Optional[SensorEvent]: ...
    def drain_events(self) -> list[SensorEvent]: ...

    def wait_for_gpio_event(
        self,
        pin: Optional[int] = None,
        timeout: Optional[float] = None,
        consume: bool = True,
    ) -> Optional[GPIOEvent]: ...

    # -- LED / Spotlight / IR ------------------------------------------------

    def led_set(self, port: int, brightness: int) -> None: ...
    def spotlight_set(self, port: int, brightness: int) -> None: ...
    def ir_set(self, brightness: int) -> None: ...

    # -- Audio ---------------------------------------------------------------

    def buzzer_set(self, port: int, state: bool) -> None: ...
    def noise_set(self, port: int, state: bool) -> None: ...
    def speaker_set(self, frequency: int, duration: int) -> None: ...

    # -- GPIO / DAQ ----------------------------------------------------------

    def gpio_configure(self, pin: int, mode: GPIOMode) -> None: ...
    def gpio_set(self, pin: int, state: bool) -> None: ...
    def daq_link_set(self, index: int, state: bool) -> None: ...

    # -- Valves --------------------------------------------------------------

    def valve_pulse(self, port: int, duration_ms: int) -> None: ...
