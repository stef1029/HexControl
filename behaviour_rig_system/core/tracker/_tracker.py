"""
Tracker — the runtime tracker, one per :class:`TrackerDefinition`.

A Tracker always has a dict of named sub-trackers internally; simple
trackers have one called ``"default"``. The public API is identical for
the simple and multi-sub cases — simple protocols never need to think
about the ``sub`` parameter because it resolves to the default sub
when omitted.

Tracker holds the trial lifecycle state machine. Recording an outcome
without a trial in progress raises ``TrackerLifecycleError``; the
documented happy path is via the :class:`Trial` context manager.
"""

from datetime import datetime
from typing import Callable, Optional

from ._definition import TrackerDefinition
from ._outcomes import TrialOutcome, TrialRecord, TrialState
from ._sub_tracker import _SubTracker


class TrackerLifecycleError(RuntimeError):
    """Raised when an outcome or stimulus is recorded with no trial in progress."""


class Tracker:
    """
    Records trial outcomes and provides statistics.

    A Tracker is built from a :class:`TrackerDefinition` and owns one or
    more named sub-trackers internally. Protocols call ``begin_trial`` /
    outcome methods on the Tracker, optionally specifying a ``sub`` to
    target a particular sub-tracker. The Tracker emits events when trials
    are recorded so the GUI can update.

    The trial lifecycle is **mandatory**: calling ``success()``,
    ``failure()``, ``timeout()``, or ``stimulus()`` outside of an active
    trial raises ``TrackerLifecycleError``. Use the :class:`Trial` context
    manager (or call ``begin_trial`` explicitly) before recording outcomes.

    Events emitted:
        ``"trial_started"``  — payload: ``correct_port``, ``timestamp``
        ``"stimulus"``       — payload: ``port``, ``modality``, ``details``
        ``"trial_ended"``    — payload: ``record`` (TrialRecord), ``sub``
        ``"trial_abandoned"`` — payload: ``reason``
        ``"update"``         — payload: ``tracker``, ``sub`` (sub name)
        ``"warning"``        — payload: ``message``
    """

    def __init__(self, definition: TrackerDefinition, clock=None):
        self._definition = definition
        self._clock = clock

        # Build sub-trackers from the definition
        self._sub_trackers: dict[str, _SubTracker] = {
            sub_name: _SubTracker(sub_name)
            for sub_name in definition.effective_sub_trackers
        }

        # Session start time (set on reset)
        self._start_time: Optional[float] = None

        # Trial lifecycle state (one trial in progress at a time, across all subs)
        self._trial_state: TrialState = TrialState.IDLE
        self._trial_start_time: Optional[float] = None
        self._pending_correct_port: Optional[int] = None
        self._pending_stimuli: list[dict] = []

        # Event listeners
        self._listeners: dict[str, list[Callable]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def display_name(self) -> str:
        return self._definition.display_name

    @property
    def stages(self) -> set[str]:
        return self._definition.effective_stages

    @property
    def sub_tracker_names(self) -> list[str]:
        return list(self._sub_trackers.keys())

    @property
    def is_simple(self) -> bool:
        """True if this tracker has only the implicit ``default`` sub-tracker."""
        return list(self._sub_trackers.keys()) == ["default"]

    @property
    def trial_in_progress(self) -> bool:
        """True if a trial has been started and not yet ended or abandoned."""
        return self._trial_state == TrialState.IN_PROGRESS

    # ------------------------------------------------------------------
    # Aggregate statistics (across all sub-trackers)
    # ------------------------------------------------------------------

    @property
    def total_trials(self) -> int:
        return sum(st.total_trials for st in self._sub_trackers.values())

    @property
    def successes(self) -> int:
        return sum(st.successes for st in self._sub_trackers.values())

    @property
    def failures(self) -> int:
        return sum(st.failures for st in self._sub_trackers.values())

    @property
    def timeouts(self) -> int:
        return sum(st.timeouts for st in self._sub_trackers.values())

    @property
    def responses(self) -> int:
        return self.successes + self.failures

    @property
    def accuracy(self) -> float:
        responses = self.responses
        if responses == 0:
            return 0.0
        return (self.successes / responses) * 100

    # ------------------------------------------------------------------
    # Sub-tracker access
    # ------------------------------------------------------------------

    def get_sub_tracker(self, name: str) -> Optional[_SubTracker]:
        """
        Return the named sub-tracker.

        The returned object exposes per-sub stats (``total_trials``,
        ``successes``, ``accuracy``, ``rolling_accuracy``, ``get_trials``,
        ``get_trials_since``). Its identity is implementation detail —
        rely only on the documented methods.
        """
        return self._sub_trackers.get(name)

    def _get_sub(self, sub: Optional[str]) -> _SubTracker:
        """Internal: resolve a sub name to a _SubTracker.

        - ``sub=None`` resolves to ``"default"`` if it exists, otherwise the
          first sub-tracker. This is the right default for simple
          (single-sub) trackers and lets multi-sub trackers explicitly
          specify the sub on each outcome call.
        - A name that doesn't exist falls back to the first sub-tracker.
        """
        if sub is None:
            if "default" in self._sub_trackers:
                return self._sub_trackers["default"]
            return next(iter(self._sub_trackers.values()))
        st = self._sub_trackers.get(sub)
        if st is None:
            return next(iter(self._sub_trackers.values()))
        return st

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """
        Clear all trial records and reset the session start time.

        Also clears any in-progress trial (without recording it as
        abandoned, since reset is a hard reset).
        """
        for st in self._sub_trackers.values():
            st.reset()
        self._trial_state = TrialState.IDLE
        self._trial_start_time = None
        self._pending_correct_port = None
        self._pending_stimuli = []
        self._start_time = self._now()
        self._notify_update(sub=None)

    def begin_trial(self, correct_port: Optional[int] = None) -> None:
        """
        Mark the start of a new trial.

        Captures the start time and stores ``correct_port`` as the
        default for the eventual outcome call. Stimulus events between
        ``begin_trial`` and the outcome are accumulated and stored on
        the resulting TrialRecord.

        If a trial is already in progress, emits a warning and
        auto-abandons it before starting the new one. This prevents a
        stuck IN_PROGRESS state from blocking all subsequent trials.
        """
        if self._trial_state == TrialState.IN_PROGRESS:
            self._emit(
                "warning",
                message=(
                    f"Tracker '{self.name}': begin_trial called while another "
                    f"trial is in progress. Auto-abandoning the previous trial."
                ),
            )
            self.abandon_trial(reason="implicit abandon (new begin_trial)")

        self._trial_state = TrialState.IN_PROGRESS
        self._trial_start_time = self._now()
        self._pending_correct_port = correct_port
        self._pending_stimuli = []

        self._emit(
            "trial_started",
            tracker=self,
            correct_port=correct_port,
            timestamp=self._trial_start_time,
        )

    def abandon_trial(self, reason: str = "") -> None:
        """
        Discard the in-progress trial without recording an outcome.

        No-op if no trial is in progress. Used by the Trial context
        manager when an exception occurs or no outcome is recorded.
        """
        if self._trial_state != TrialState.IN_PROGRESS:
            return
        self._trial_state = TrialState.IDLE
        self._trial_start_time = None
        self._pending_correct_port = None
        self._pending_stimuli = []
        self._emit("trial_abandoned", tracker=self, reason=reason)

    # ------------------------------------------------------------------
    # Stimulus events (accumulated during in-progress trial)
    # ------------------------------------------------------------------

    def stimulus(
        self,
        port: int,
        modality: Optional[str] = None,
        **details,
    ) -> None:
        """
        Record a stimulus presentation during the current trial.

        Multiple calls per trial are allowed and encouraged (e.g. visual
        cue at t=0, audio cue at t=2, go signal at t=3). Each stimulus
        is captured as ``{t, port, modality, **details}`` and attached
        to the resulting TrialRecord when the trial closes.

        Raises:
            TrackerLifecycleError: if no trial is in progress.
        """
        if self._trial_state != TrialState.IN_PROGRESS:
            raise TrackerLifecycleError(
                f"Tracker '{self.name}': stimulus() called with no trial in "
                f"progress. Use the Trial context manager or call "
                f"begin_trial() first."
            )

        t_offset = self._now() - (self._trial_start_time or 0.0)
        stim_record = {"t": t_offset, "port": port, "modality": modality}
        stim_record.update(details)
        self._pending_stimuli.append(stim_record)

        # Live event for GUI / future subscribers
        self._emit(
            "stimulus",
            tracker=self,
            port=port,
            modality=modality,
            t_offset=t_offset,
            details=details,
        )

    # ------------------------------------------------------------------
    # Recording outcomes
    # ------------------------------------------------------------------

    def success(
        self,
        correct_port: Optional[int] = None,
        sub: Optional[str] = None,
        **details,
    ) -> None:
        """
        Record a successful trial.

        ``correct_port`` defaults to the value passed to ``begin_trial``.
        On success, the chosen port equals the correct port.

        Raises:
            TrackerLifecycleError: if no trial is in progress.
        """
        port = correct_port if correct_port is not None else self._pending_correct_port
        self._record(
            outcome=TrialOutcome.SUCCESS,
            sub=sub,
            correct_port=port,
            chosen_port=port,
            details=details,
        )

    def failure(
        self,
        chosen_port: int,
        correct_port: Optional[int] = None,
        sub: Optional[str] = None,
        **details,
    ) -> None:
        """
        Record a failed trial.

        ``correct_port`` defaults to the value passed to ``begin_trial``.

        Raises:
            TrackerLifecycleError: if no trial is in progress.
        """
        port = correct_port if correct_port is not None else self._pending_correct_port
        self._record(
            outcome=TrialOutcome.FAILURE,
            sub=sub,
            correct_port=port,
            chosen_port=chosen_port,
            details=details,
        )

    def timeout(
        self,
        correct_port: Optional[int] = None,
        sub: Optional[str] = None,
        **details,
    ) -> None:
        """
        Record a timeout trial (no response within the response window).

        ``correct_port`` defaults to the value passed to ``begin_trial``.

        Raises:
            TrackerLifecycleError: if no trial is in progress.
        """
        port = correct_port if correct_port is not None else self._pending_correct_port
        self._record(
            outcome=TrialOutcome.TIMEOUT,
            sub=sub,
            correct_port=port,
            chosen_port=None,
            details=details,
        )

    def _record(
        self,
        outcome: TrialOutcome,
        sub: str,
        correct_port: Optional[int],
        chosen_port: Optional[int],
        details: dict,
    ) -> None:
        """Internal: build a TrialRecord and append it to the right sub-tracker."""
        if self._trial_state != TrialState.IN_PROGRESS:
            raise TrackerLifecycleError(
                f"Tracker '{self.name}': cannot record {outcome.value} — no "
                f"trial in progress. Use the Trial context manager or call "
                f"begin_trial() first."
            )

        st = self._get_sub(sub)
        end_time = self._now()
        trial_duration = end_time - (self._trial_start_time or end_time)
        time_since_start = (
            end_time - self._start_time if self._start_time is not None else 0.0
        )

        record = TrialRecord(
            trial_number=st.total_trials + 1,
            outcome=outcome,
            timestamp=end_time,
            time_since_start=time_since_start,
            correct_port=correct_port,
            chosen_port=chosen_port,
            trial_duration=trial_duration,
            trial_type=st.name,
            stimuli=list(self._pending_stimuli),
            details=dict(details),
        )
        st.append(record)

        # Clear lifecycle state before emitting events so listeners see IDLE
        self._trial_state = TrialState.IDLE
        self._trial_start_time = None
        self._pending_correct_port = None
        self._pending_stimuli = []

        self._emit("trial_ended", tracker=self, record=record, sub=st.name)
        self._notify_update(sub=st.name)

    # ------------------------------------------------------------------
    # Aggregate trial queries
    # ------------------------------------------------------------------

    def get_all_trials(self) -> list[TrialRecord]:
        """All trials from all sub-trackers, sorted by timestamp."""
        trials: list[TrialRecord] = []
        for st in self._sub_trackers.values():
            trials.extend(st.get_trials())
        trials.sort(key=lambda t: t.timestamp)
        return trials

    def get_all_trials_since(self, start_indices: dict[str, int]) -> list[TrialRecord]:
        """
        Trials from all sub-trackers since the given per-sub indices, sorted.

        Args:
            start_indices: Dict mapping sub-tracker name to trial index.
                           Trials at or after the index are included.
        """
        trials: list[TrialRecord] = []
        for sub_name, st in self._sub_trackers.items():
            idx = start_indices.get(sub_name, 0)
            trials.extend(st.get_trials_since(idx))
        trials.sort(key=lambda t: t.timestamp)
        return trials

    def get_time_span(self) -> tuple[Optional[float], Optional[float]]:
        """
        Return ``(earliest_start, latest_outcome_timestamp)`` for this tracker.

        ``earliest_start`` is the tracker's session start time (set on
        ``reset``). ``latest_outcome_timestamp`` is the timestamp of the
        most recent recorded trial across all sub-trackers, or ``None``
        if no trials have been recorded.
        """
        last_ts: Optional[float] = None
        for st in self._sub_trackers.values():
            ts = st.last_timestamp()
            if ts is not None and (last_ts is None or ts > last_ts):
                last_ts = ts
        return self._start_time, last_ts

    def rolling_accuracy(self, n: int = 20) -> float:
        """
        Tracker-level rolling accuracy across all sub-trackers.

        Merges all trials, sorts by timestamp, takes the last ``n``
        non-timeout trials.
        """
        all_trials = self.get_all_trials()
        recent = [t for t in all_trials if t.outcome != TrialOutcome.TIMEOUT][-n:]
        if not recent:
            return 0.0
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def rolling_accuracy_since(
        self, n: int, start_indices: dict[str, int]
    ) -> Optional[float]:
        """
        Tracker-level rolling accuracy, stage-isolated by start indices.

        Returns ``None`` if fewer than ``n`` non-timeout trials have been
        recorded since the given indices.
        """
        trials = self.get_all_trials_since(start_indices)
        recent = [t for t in trials if t.outcome != TrialOutcome.TIMEOUT][-n:]
        if len(recent) < n:
            return None
        successes = sum(1 for t in recent if t.outcome == TrialOutcome.SUCCESS)
        return (successes / len(recent)) * 100

    def get_summary(self) -> str:
        """One-line summary string for logging."""
        if self.total_trials == 0:
            return "No trials yet"
        return (
            f"{self.successes}/{self.responses} correct ({self.accuracy:.0f}%) | "
            f"{self.timeouts} timeouts | "
            f"Last 20: {self.rolling_accuracy(20):.0f}%"
        )

    # ------------------------------------------------------------------
    # Event system
    # ------------------------------------------------------------------

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a callback for a named event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def _emit(self, event_name: str, **kwargs) -> None:
        """Fire an event to registered listeners."""
        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception as e:
                print(f"Warning: Tracker listener error in '{event_name}': {e}")

    def _notify_update(self, sub: Optional[str]) -> None:
        """Emit the ``update`` event after a trial is recorded or the tracker is reset."""
        self._emit("update", tracker=self, sub=sub)

    # ------------------------------------------------------------------
    # Time helper
    # ------------------------------------------------------------------

    def _now(self) -> float:
        """Current time, using the optional BehaviourClock if set."""
        if self._clock is not None:
            return self._clock.time()
        return datetime.now().timestamp()
