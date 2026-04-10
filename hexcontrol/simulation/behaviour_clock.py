"""
Behaviour Clock — Injectable time source for accelerated simulated sessions.

When speed=1.0 the clock is a transparent pass-through to the standard
library.  With speed=10.0, all sleeps and timeouts complete 10× faster
while virtual timestamps advance 10× more quickly so recorded trial
data looks identical to real-time data.

Usage:
    clock = BehaviourClock(speed=10.0)
    clock.sleep(5.0)          # actually sleeps 0.5 real seconds
    t = clock.time()          # virtual elapsed time (real_elapsed * speed)
    cond.wait(timeout=clock.real_timeout(5.0))  # wait 0.5 real seconds
"""

import time


class BehaviourClock:
    """
    Time source that can accelerate sleeps and timeouts.

    All public methods are safe to call from any thread.
    """

    def __init__(self, speed: float = 1.0) -> None:
        if speed <= 0:
            raise ValueError(f"speed must be positive, got {speed}")
        self._speed = speed
        self._origin = time.monotonic()

    @property
    def speed(self) -> float:
        return self._speed

    # Minimum real sleep to avoid Windows timer resolution (~15ms) inflating
    # virtual time.  Below this threshold we skip the sleep entirely — the
    # caller's loop will re-check its exit condition using time() anyway.
    _MIN_REAL_SLEEP = 0.001  # 1 ms

    def sleep(self, seconds: float) -> None:
        """Sleep for *seconds* of virtual time (real sleep = seconds / speed)."""
        if seconds > 0:
            real = seconds / self._speed
            if real >= self._MIN_REAL_SLEEP:
                time.sleep(real)

    def time(self) -> float:
        """Virtual elapsed time since clock creation (real_elapsed × speed)."""
        return (time.monotonic() - self._origin) * self._speed

    def real_timeout(self, virtual_timeout: float) -> float:
        """Convert a virtual-time timeout to real seconds for Condition.wait() / Timer."""
        return virtual_timeout / self._speed


REAL_TIME = BehaviourClock(speed=1.0)
