"""
Simulated Mouse — Automated agent that interacts with a VirtualRigState.

Observes rig state (LEDs, speaker, spotlights, valves) and injects events
(port pokes, weight changes) based on a mix of fixed parameters and
Rescorla-Wagner learning:

    Fixed parameters (set in the GUI, constant across trials):
        mount_delay             — time before mounting the platform
        timeout_probability     — probability of ignoring a cue
        response_time           — mean response latency
        inhibition_probability  — probability of withholding a wrong response

    Learning values (Rescorla-Wagner, updated trial-by-trial):
        V_patience  — "waiting → cue appears"   → controls platform patience
        V_accuracy  — "follow cue → reward"      → controls port choice accuracy

Events emitted:
    "log"              (message: str)       — status messages for the GUI log
    "learning_update"  (v_values: dict)     — current V values after each trial
"""

from __future__ import annotations

import random
import threading
import time
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from BehavLink.simulation import RigStateSnapshot, VirtualRigState


class SimulatedMouse:
    """
    Automated simulated mouse that learns to interact with the behaviour rig.

    Runs on its own daemon thread.  Reads VirtualRigState snapshots to observe
    rig outputs (LEDs, speaker, spotlights, valves) and injects responses via
    set_weight() and inject_sensor_event().

    Uses emitter/listener pattern for communication (same as other classes
    in this codebase).
    """

    # Polling interval for observing rig state changes (ms equivalent)
    _POLL_INTERVAL = 0.05  # 50 ms — 20 Hz observation rate

    def __init__(self, params: dict, state: "VirtualRigState", clock=None) -> None:
        """
        Args:
            params: Dict of mouse parameters (from ParameterFormBuilder).
            state: Shared VirtualRigState to observe and inject events into.
            clock: Optional BehaviourClock for accelerated simulation.
        """
        self._state = state
        self._params = params
        self._clock = clock

        self._listeners: dict[str, list[Callable]] = {}

        # Learning state — two Rescorla-Wagner values
        self._v_patience: float = params.get("v_patience_initial", 0.1)
        self._v_accuracy: float = params.get("v_accuracy_initial", 0.1)

        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── Emitter / listener ─────────────────────────────────────────────

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a callback for a named event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def _emit(self, event_name: str, **kwargs) -> None:
        """Fire an event to registered listeners."""
        for cb in self._listeners.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception as e:
                print(f"Warning: listener error in '{event_name}': {e}")

    # ── Lifecycle ──────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the mouse behaviour thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._emit("log", message="Simulated mouse started")

    def stop(self) -> None:
        """Signal the mouse thread to stop and wait for it to finish."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._emit("log", message="Simulated mouse stopped")

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _lerp(v: float, param_min: float, param_max: float) -> float:
        """Map V in [0, 1] to a parameter range via linear interpolation."""
        return param_min + (param_max - param_min) * v

    def _sleep(self, seconds: float) -> bool:
        """
        Sleep for *seconds* (virtual time) in short increments so stop() is responsive.

        Returns False if the mouse was stopped during the sleep (caller
        should exit its loop).
        """
        if self._clock:
            # Chunk in real time (0.1s) so OS timer resolution doesn't
            # inflate virtual time at high speeds.
            real_total = self._clock.real_timeout(seconds)
            remaining = real_total
            while remaining > 0 and self._running:
                chunk = min(remaining, 0.1)
                time.sleep(chunk)
                remaining -= chunk
        else:
            remaining = seconds
            while remaining > 0 and self._running:
                chunk = min(remaining, 0.1)
                time.sleep(chunk)
                remaining -= chunk
        return self._running

    def _poll_sleep(self) -> None:
        """Sleep for one poll interval, using the clock if available."""
        if self._clock:
            # Floor to 1ms real to avoid Windows timer resolution overhead.
            time.sleep(max(self._POLL_INTERVAL / self._clock.speed, 0.001))
        else:
            time.sleep(self._POLL_INTERVAL)

    def _get_snapshot(self) -> "RigStateSnapshot":
        """Get the current rig state snapshot."""
        return self._state.snapshot()

    def _find_cued_port(self, snap: "RigStateSnapshot") -> Optional[int]:
        """
        Determine which port (0-5) has an active cue, if any.

        Checks LED brightness first (visual cue), then buzzer state
        (some protocols use buzzers as port-specific cues).
        Returns None if no single port is cued.
        """
        # Check LEDs — find ports with brightness > 0
        lit_ports = [p for p in range(6) if snap.led_brightness[p] > 0]
        if len(lit_ports) == 1:
            return lit_ports[0]

        # Check buzzers — find active buzzers
        buzzing_ports = [p for p in range(6) if snap.buzzer_state[p]]
        if len(buzzing_ports) == 1:
            return buzzing_ports[0]

        # Multiple or no cues — can't determine target
        return None

    def _any_spotlight_on(self, snap: "RigStateSnapshot") -> bool:
        """Check if overhead spotlights are on (punishment signal)."""
        return any(b > 0 for b in snap.spotlight_brightness)

    def _any_valve_pulsing(self, snap: "RigStateSnapshot") -> bool:
        """Check if any valve is pulsing (reward signal)."""
        return any(snap.valve_pulsing)

    def _cue_active(self, snap: "RigStateSnapshot") -> bool:
        """Check if any cue is currently presented (LED, buzzer, or speaker)."""
        if any(b > 0 for b in snap.led_brightness):
            return True
        if any(snap.buzzer_state):
            return True
        if snap.speaker_active:
            return True
        return False

    def _update_v(self, attr: str, positive: bool) -> None:
        """
        Rescorla-Wagner update for one V dimension.

        Args:
            attr: Name of the V attribute (e.g., "_v_accuracy").
            positive: True for positive update, False for decay.
        """
        # Map V attribute to its alpha parameter name
        alpha_map = {
            "_v_patience": "v_patience_alpha",
            "_v_accuracy": "v_accuracy_alpha",
        }
        alpha = self._params.get(alpha_map[attr], 0.05)
        v = getattr(self, attr)

        if positive:
            v = v + alpha * (1.0 - v)
        else:
            v = v * (1.0 - alpha)

        setattr(self, attr, max(0.0, min(1.0, v)))

    def _emit_learning_update(self) -> None:
        """Emit current V values for monitoring."""
        self._emit(
            "learning_update",
            v_values={
                "patience": round(self._v_patience, 3),
                "accuracy": round(self._v_accuracy, 3),
            },
        )

    # ── Main behaviour loop ────────────────────────────────────────────

    def _run(self) -> None:
        """Main thread loop — state machine driving mouse behaviour."""
        self._emit("log", message=(
            f"V initial: patience={self._v_patience:.2f} accuracy={self._v_accuracy:.2f}"
        ))

        trial_number = 0

        while self._running:
            try:
                # ── IDLE: wait, then mount platform ────────────────
                mount_delay = self._params.get("mount_delay", 2.0)
                if not self._sleep(mount_delay):
                    break

                # Mount platform
                self._state.set_weight(25.0)

                # ── ON_PLATFORM: wait for cue ──────────────────────
                cued_port = self._wait_for_cue()
                if cued_port is None:
                    # Stopped or left platform due to impatience
                    self._state.set_weight(0.0)
                    continue

                trial_number += 1

                # ── CUE_VISIBLE: decide response ──────────────────
                outcome = self._respond_to_cue(cued_port, trial_number)

                # ── ITI: dismount briefly ─────────────────────────
                self._state.set_weight(0.0)
                if not self._sleep(0.5):
                    break

                # Log and emit learning state
                v_summary = (
                    f"V: pat={self._v_patience:.2f} acc={self._v_accuracy:.2f}"
                )
                self._emit("log", message=f"  Mouse trial {trial_number}: {outcome} | {v_summary}")
                self._emit_learning_update()

            except Exception as e:
                self._emit("log", message=f"SimulatedMouse error: {e}")
                if not self._sleep(1.0):
                    break

    # ── Phase: wait for cue on platform ────────────────────────────────

    def _wait_for_cue(self) -> Optional[int]:
        """
        Wait on the platform for a cue to appear.

        Uses VirtualRigState._cue_event to wake immediately when the
        protocol presents a cue — avoids missing brief LED flashes at
        high simulation speeds.

        Periodically checks patience — the mouse may leave early if
        V_patience is low.  Returns the cued port, or None if the mouse
        left or was stopped.
        """
        patience_check_interval = 1.0  # 1 virtual second between patience checks
        # Use virtual time for patience so it doesn't depend on poll rate
        if self._clock:
            last_patience_time = self._clock.time()
        else:
            last_patience_time = time.monotonic()

        # Clear any stale cue notification before waiting
        self._state._cue_event.clear()

        while self._running:
            snap = self._get_snapshot()

            # Check if a cue has appeared
            cued_port = self._find_cued_port(snap)
            if cued_port is not None:
                # Successfully waited → positive patience signal
                self._update_v("_v_patience", positive=True)
                return cued_port

            # Also check for speaker-only cue (audio trials)
            if snap.speaker_active and cued_port is None:
                # Speaker is on but no specific port lit — protocol may
                # be using audio-only.  Mouse can't determine port from
                # speaker alone, so just wait for LED or treat as no cue.
                pass

            # Patience check — uses virtual time so it fires every
            # 1 virtual second regardless of simulation speed
            if self._clock:
                now = self._clock.time()
            else:
                now = time.monotonic()

            if now - last_patience_time >= patience_check_interval:
                last_patience_time = now
                effective_patience = self._lerp(
                    self._v_patience,
                    self._params.get("patience_min", 0.3),
                    self._params.get("patience_max", 0.95),
                )
                if random.random() > effective_patience:
                    # Impatient — leave platform
                    self._update_v("_v_patience", positive=False)
                    self._emit("log", message="  Mouse left platform (impatient)")
                    return None

            # Wait for a cue notification or poll timeout.
            # At high speeds the real timeout is very short; at 1x it's
            # the normal poll interval.  The Event wakes us immediately
            # when set_led/set_buzzer/set_speaker fires, so we never
            # miss a brief cue.
            real_timeout = (
                self._clock.real_timeout(self._POLL_INTERVAL)
                if self._clock
                else self._POLL_INTERVAL
            )
            self._state._cue_event.wait(timeout=max(real_timeout, 0.001))
            self._state._cue_event.clear()

        return None

    # ── Phase: respond to cue ──────────────────────────────────────────

    def _respond_to_cue(self, cued_port: int, trial_number: int) -> str:
        """
        Decide how to respond to a cue and observe the outcome.

        Returns a string describing the outcome for logging.
        """
        # Step 1: Will the mouse respond at all? (fixed timeout probability)
        if random.random() < self._params.get("timeout_probability", 0.05):
            self._wait_for_cue_end()
            return "timeout (disengaged)"

        # Step 2: Choose port
        chosen_port: Optional[int] = None

        if random.random() < self._v_accuracy:
            # Correct — follow the cue
            chosen_port = cued_port
        else:
            # Wrong choice — check inhibition (fixed probability)
            if random.random() < self._params.get("inhibition_probability", 0.3):
                self._wait_for_cue_end()
                return "withheld (inhibition)"
            else:
                # Poke a random port (from all 6)
                chosen_port = random.randint(0, 5)

        # Step 3: Wait response time, then poke (fixed mean + noise)
        response_time = self._params.get("response_time", 1.5)
        response_time += random.gauss(0, self._params.get("response_time_std", 0.8))
        response_time = max(0.2, response_time)

        # Leave the platform before going to a port — the mouse can't
        # be on the scales and at a reward port simultaneously.
        self._state.set_weight(0.0)

        if not self._sleep(response_time):
            return "stopped"

        # Inject the poke (mouse commits once it sees the cue — doesn't
        # need it to still be displayed, matching real mouse behaviour
        # where brief cue flashes are followed by a response window)
        self._state.inject_sensor_event(chosen_port, is_activation=True)

        # Step 4: Observe outcome
        return self._observe_outcome(cued_port, chosen_port)

    def _observe_outcome(self, cued_port: int, chosen_port: int) -> str:
        """
        Wait briefly and observe rig response after poking.

        Returns outcome description string.
        """
        # Poll for up to 3 seconds (virtual) for valve or spotlight
        real_wait = self._clock.real_timeout(3.0) if self._clock else 3.0
        deadline = time.monotonic() + real_wait
        while time.monotonic() < deadline and self._running:
            snap = self._get_snapshot()

            # Check for reward (valve pulse)
            if self._any_valve_pulsing(snap):
                # Reward!
                self._update_v("_v_patience", positive=True)
                self._update_v("_v_accuracy", positive=True)
                return f"CORRECT (port {chosen_port})"

            # Check for punishment (spotlights on)
            if self._any_spotlight_on(snap):
                # Punishment
                self._update_v("_v_accuracy", positive=False)
                # Wait for punishment to end before continuing
                self._wait_for_punishment_end()
                return f"WRONG (chose {chosen_port}, target was {cued_port})"

            self._poll_sleep()

        # No clear signal — treat as neutral
        return f"poked {chosen_port} (no outcome detected)"

    # ── Waiting helpers ────────────────────────────────────────────────

    def _wait_for_cue_end(self) -> None:
        """Wait until all cues (LEDs, buzzers, speaker) turn off."""
        while self._running:
            snap = self._get_snapshot()
            if not self._cue_active(snap):
                return
            self._poll_sleep()

    def _wait_for_punishment_end(self) -> None:
        """Wait until spotlights turn off (end of punishment period)."""
        while self._running:
            snap = self._get_snapshot()
            if not self._any_spotlight_on(snap):
                return
            self._poll_sleep()
