"""
Trial context manager — the documented happy path for the trial lifecycle.

Wraps ``begin_trial`` / outcome / auto-abandon-on-exit so that protocol
authors can write::

    with Trial(tracker, correct_port=3) as t:
        t.stimulus(port=3, modality="visual")
        # ... run trial logic ...
        t.success()

The context manager guarantees that the tracker's lifecycle state is
always cleaned up:

- If an outcome is recorded, the trial closes normally.
- If the body exits without recording an outcome, the trial is
  abandoned and a warning is emitted.
- If the body raises an exception, the trial is abandoned with the
  exception in the reason and the exception is re-raised.

The Trial object exposes ``success`` / ``failure`` / ``timeout`` /
``stimulus`` methods that delegate to the wrapped tracker. Each
delegate is sub-aware via the ``sub`` argument passed at construction.
"""

from typing import Any, Optional


class Trial:
    """Context manager enforcing the trial lifecycle on a Tracker."""

    def __init__(
        self,
        tracker: Any,
        correct_port: Optional[int] = None,
        sub: Optional[str] = None,
    ):
        """
        Args:
            tracker:      The Tracker instance to record on.
            correct_port: The correct port for this trial. Stored on the
                          tracker so outcome calls don't need to repeat it.
            sub:          The default sub-tracker to record outcomes on.
                          Outcome methods accept their own ``sub`` to override.
        """
        self._tracker = tracker
        self._correct_port = correct_port
        self._sub = sub
        self._outcome_recorded = False

    def __enter__(self) -> "Trial":
        self._tracker.begin_trial(correct_port=self._correct_port)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            # An exception occurred — abandon and propagate
            self._tracker.abandon_trial(
                reason=f"exception: {exc_type.__name__}: {exc_val}"
            )
            return  # don't suppress

        if not self._outcome_recorded:
            # Body exited cleanly but never recorded an outcome
            self._tracker._emit(
                "warning",
                message=(
                    f"Trial on tracker '{self._tracker.name}' exited without "
                    f"recording an outcome — auto-abandoning."
                ),
            )
            self._tracker.abandon_trial(reason="no outcome recorded")

    # ------------------------------------------------------------------
    # Stimulus
    # ------------------------------------------------------------------

    def stimulus(
        self,
        port: int,
        modality: Optional[str] = None,
        **details,
    ) -> None:
        """Record a stimulus presentation during this trial."""
        self._tracker.stimulus(port=port, modality=modality, **details)

    # ------------------------------------------------------------------
    # Outcomes
    # ------------------------------------------------------------------

    def success(
        self,
        correct_port: Optional[int] = None,
        sub: Optional[str] = None,
        **details,
    ) -> None:
        """Record a successful trial. Sub defaults to the Trial's sub."""
        self._tracker.success(
            correct_port=correct_port,
            sub=sub if sub is not None else self._sub,
            **details,
        )
        self._outcome_recorded = True

    def failure(
        self,
        chosen_port: int,
        correct_port: Optional[int] = None,
        sub: Optional[str] = None,
        **details,
    ) -> None:
        """Record a failed trial. Sub defaults to the Trial's sub."""
        self._tracker.failure(
            chosen_port=chosen_port,
            correct_port=correct_port,
            sub=sub if sub is not None else self._sub,
            **details,
        )
        self._outcome_recorded = True

    def timeout(
        self,
        correct_port: Optional[int] = None,
        sub: Optional[str] = None,
        **details,
    ) -> None:
        """Record a timeout trial. Sub defaults to the Trial's sub."""
        self._tracker.timeout(
            correct_port=correct_port,
            sub=sub if sub is not None else self._sub,
            **details,
        )
        self._outcome_recorded = True
