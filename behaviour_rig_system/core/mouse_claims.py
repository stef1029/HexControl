"""
Mouse allocation service.

Tracks which mice are currently in use by which rigs, preventing the
same mouse from being claimed by two rig windows simultaneously. This
is pure business logic with no GUI dependency — the launcher
instantiates one and passes its methods to child rig windows.

Threadsafe via an internal lock so that concurrent rig windows don't
race on claim/release.
"""

import threading


class MouseClaims:
    """
    Prevents duplicate mouse allocation across multiple open rig windows.

    Usage::

        claims = MouseClaims()

        if claims.try_claim("mouse_001", "Rig 1"):
            print("claimed!")
        else:
            print("already claimed by", claims.claimed_by("mouse_001"))

        claims.release_all("Rig 1")
    """

    def __init__(self):
        self._claims: dict[str, str] = {}  # mouse_id -> rig_name
        self._lock = threading.Lock()

    def try_claim(self, mouse_id: str, rig_name: str) -> bool:
        """
        Attempt to claim a mouse for a rig.

        Returns True if the claim succeeded (either the mouse was free
        or already claimed by the same rig). Returns False if the mouse
        is claimed by a different rig.
        """
        with self._lock:
            current = self._claims.get(mouse_id)
            if current is not None and current != rig_name:
                return False
            self._claims[mouse_id] = rig_name
            return True

    def release_all(self, rig_name: str) -> None:
        """Release all mice claimed by the given rig."""
        with self._lock:
            self._claims = {m: r for m, r in self._claims.items() if r != rig_name}

    def claimed_by(self, mouse_id: str) -> str | None:
        """Return the rig name that currently holds this mouse, or None."""
        with self._lock:
            return self._claims.get(mouse_id)

    def get_all(self) -> dict[str, str]:
        """Return a snapshot of all claims: ``{mouse_id: rig_name}``."""
        with self._lock:
            return dict(self._claims)
