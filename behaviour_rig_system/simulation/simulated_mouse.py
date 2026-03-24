"""
Simulated Mouse — Automated agent that interacts with a VirtualRigState.

Observes rig state (LEDs, speaker, spotlights, valves) and injects events
(port pokes, weight changes) based on a multi-dimensional Rescorla-Wagner
learning model with five independent associative strengths:

    V_platform    — "platform → things happen"       → controls mount delay
    V_patience    — "waiting → cue appears"           → controls platform patience
    V_engagement  — "responding to cue → reward"      → controls timeout probability
    V_accuracy    — "follow cue → reward"             → controls port choice accuracy
    V_inhibition  — "wrong port → punishment"         → controls response withholding

Events emitted:
    "log"              (message: str)       — status messages for the GUI log
    "learning_update"  (v_values: dict)     — current V values after each trial
"""

from __future__ import annotations

import random
import threading
import time
from enum import Enum, auto
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from BehavLink.simulation import RigStateSnapshot, VirtualRigState


class _Phase(Enum):
    """Internal state machine phases."""
    IDLE = auto()
    ON_PLATFORM = auto()
    CUE_VISIBLE = auto()
    AWAITING_OUTCOME = auto()
    ITI = auto()


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

    def __init__(self, params: dict, state: "VirtualRigState") -> None:
        """
        Args:
            params: Dict of mouse parameters (from ParameterFormBuilder).
            state: Shared VirtualRigState to observe and inject events into.
        """
        self._state = state
        self._params = params

        self._listeners: dict[str, list[Callable]] = {}

        # Learning state — five independent associative strengths
        self._v_platform: float = params.get("v_platform_initial", 0.1)
        self._v_patience: float = params.get("v_patience_initial", 0.1)
        self._v_engagement: float = params.get("v_engagement_initial", 0.95)
        self._v_accuracy: float = params.get("v_accuracy_initial", 0.1)
        self._v_inhibition: float = params.get("v_inhibition_initial", 0.0)

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
            except Exception:
                pass

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
        Sleep for *seconds* in short increments so stop() is responsive.

        Returns False if the mouse was stopped during the sleep (caller
        should exit its loop).
        """
        remaining = seconds
        while remaining > 0 and self._running:
            chunk = min(remaining, 0.1)
            time.sleep(chunk)
            remaining -= chunk
        return self._running

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
            "_v_platform": "v_platform_alpha",
            "_v_patience": "v_patience_alpha",
            "_v_engagement": "v_engagement_alpha",
            "_v_accuracy": "v_accuracy_alpha",
            "_v_inhibition": "v_inhibition_alpha",
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
                "platform": round(self._v_platform, 3),
                "patience": round(self._v_patience, 3),
                "engagement": round(self._v_engagement, 3),
                "accuracy": round(self._v_accuracy, 3),
                "inhibition": round(self._v_inhibition, 3),
            },
        )

    # ── Main behaviour loop ────────────────────────────────────────────

    def _run(self) -> None:
        """Main thread loop — state machine driving mouse behaviour."""
        self._emit("log", message=(
            f"V initial: platform={self._v_platform:.2f} patience={self._v_patience:.2f} "
            f"engagement={self._v_engagement:.2f} accuracy={self._v_accuracy:.2f} "
            f"inhibition={self._v_inhibition:.2f}"
        ))

        trial_number = 0

        while self._running:
            try:
                # ── IDLE: wait, then mount platform ────────────────
                mount_delay = self._lerp(
                    1.0 - self._v_platform,
                    self._params.get("mount_delay_min", 1.0),
                    self._params.get("mount_delay_max", 6.0),
                )
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
                    f"V: plat={self._v_platform:.2f} pat={self._v_patience:.2f} "
                    f"eng={self._v_engagement:.2f} acc={self._v_accuracy:.2f} "
                    f"inh={self._v_inhibition:.2f}"
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

        Periodically checks patience — the mouse may leave early if
        V_patience is low.  Returns the cued port, or None if the mouse
        left or was stopped.
        """
        patience_check_interval = 1.0  # check patience every second
        time_on_platform = 0.0

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

            # Patience check — might leave early
            time_on_platform += self._POLL_INTERVAL
            if time_on_platform >= patience_check_interval:
                time_on_platform = 0.0
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

            time.sleep(self._POLL_INTERVAL)

        return None

    # ── Phase: respond to cue ──────────────────────────────────────────

    def _respond_to_cue(self, cued_port: int, trial_number: int) -> str:
        """
        Decide how to respond to a cue and observe the outcome.

        Returns a string describing the outcome for logging.
        """
        # Step 1: Will the mouse respond at all? (engagement)
        effective_timeout_prob = (
            self._params.get("timeout_prob_max", 0.4) * (1.0 - self._v_engagement)
        )
        if random.random() < effective_timeout_prob:
            # Timeout — mouse ignores the cue
            self._update_v("_v_engagement", positive=False)
            # Wait for cue to disappear
            self._wait_for_cue_end()
            return "timeout (disengaged)"

        # Step 2: Choose port
        chosen_port: Optional[int] = None

        if random.random() < self._v_accuracy:
            # Correct — follow the cue
            chosen_port = cued_port
        else:
            # Wrong choice — check inhibition
            if random.random() < self._v_inhibition:
                # Withhold — mouse suppresses the wrong response
                self._update_v("_v_engagement", positive=False)
                self._wait_for_cue_end()
                return "withheld (inhibition)"
            else:
                # Poke a random port (from all 6)
                chosen_port = random.randint(0, 5)

        # Step 3: Wait response time, then poke
        response_time = self._lerp(
            1.0 - self._v_engagement,
            self._params.get("response_time_min", 0.8),
            self._params.get("response_time_max", 5.0),
        )
        response_time += random.gauss(0, self._params.get("response_time_std", 0.8))
        response_time = max(0.2, response_time)

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
        # Poll for up to 3 seconds (scaled) for valve or spotlight
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and self._running:
            snap = self._get_snapshot()

            # Check for reward (valve pulse)
            if self._any_valve_pulsing(snap):
                # Reward!
                self._update_v("_v_platform", positive=True)
                self._update_v("_v_patience", positive=True)
                self._update_v("_v_engagement", positive=True)
                self._update_v("_v_accuracy", positive=True)
                return f"CORRECT (port {chosen_port})"

            # Check for punishment (spotlights on)
            if self._any_spotlight_on(snap):
                # Punishment
                self._update_v("_v_inhibition", positive=True)
                self._update_v("_v_accuracy", positive=False)
                # Wait for punishment to end before continuing
                self._wait_for_punishment_end()
                return f"WRONG (chose {chosen_port}, target was {cued_port})"

            time.sleep(self._POLL_INTERVAL)

        # No clear signal — treat as neutral
        return f"poked {chosen_port} (no outcome detected)"

    # ── Waiting helpers ────────────────────────────────────────────────

    def _wait_for_cue_end(self) -> None:
        """Wait until all cues (LEDs, buzzers, speaker) turn off."""
        while self._running:
            snap = self._get_snapshot()
            if not self._cue_active(snap):
                return
            time.sleep(self._POLL_INTERVAL)

    def _wait_for_punishment_end(self) -> None:
        """Wait until spotlights turn off (end of punishment period)."""
        while self._running:
            snap = self._get_snapshot()
            if not self._any_spotlight_on(snap):
                return
            time.sleep(self._POLL_INTERVAL)
