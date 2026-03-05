"""
Board Registry - USB serial device discovery by serial number.

Replaces hardcoded COM port references with human-readable board names
that are resolved at runtime by matching USB VID, PID, and serial number.

Usage:
    from core.board_registry import BoardRegistry

    registry = BoardRegistry(Path("path/to/board_registry.json"))
    port = registry.find_board_port("rig_1_behaviour")  # -> "COM7" or raises

    # Discovery tool (run as script):
    python -m core.board_registry
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import serial.tools.list_ports


@dataclass(frozen=True)
class BoardInfo:
    """Describes one registered USB serial board."""

    name: str
    description: str
    vid: int
    pid: int
    serial_number: str
    baudrate: int

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "BoardInfo":
        """Create a BoardInfo from a JSON dict entry."""
        return cls(
            name=name,
            description=d.get("description", ""),
            vid=int(d["vid"], 16) if isinstance(d["vid"], str) else d["vid"],
            pid=int(d["pid"], 16) if isinstance(d["pid"], str) else d["pid"],
            serial_number=d.get("serial_number", ""),
            baudrate=d.get("baudrate", 115200),
        )


class BoardRegistry:
    """
    Registry of known USB serial boards.

    Each board is identified by a human-readable key (e.g. ``"rig_1_behaviour"``)
    and matched at runtime by USB VID, PID, and serial number.
    """

    def __init__(self, registry_path: Path):
        self._path = registry_path
        self._boards: dict[str, BoardInfo] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def boards(self) -> dict[str, BoardInfo]:
        """All registered boards keyed by human-readable name."""
        return dict(self._boards)

    @staticmethod
    def is_direct_port(name: str) -> bool:
        """Return ``True`` if *name* is a raw COM port (e.g. ``"COM9"``) rather than a board registry key."""
        if not name:
            return False
        upper = name.upper()
        return upper.startswith("COM") or name.startswith("/dev/")

    def resolve_port(self, name: str) -> str:
        """
        Resolve a board name **or** raw COM port to a port string.

        If *name* looks like a direct COM port (e.g. ``"COM9"``),
        it is returned as-is without consulting the registry.
        Otherwise it is looked up via :meth:`find_board_port`.
        """
        if self.is_direct_port(name):
            return name
        return self.find_board_port(name)

    def resolve_baudrate(self, name: str, default: int = 115200) -> int:
        """
        Return the baud rate for *name*.

        If *name* is a raw COM port, *default* is returned.
        Otherwise the value from the registry is used.
        """
        if self.is_direct_port(name):
            return default
        return self.get_baudrate(name)

    def find_board_port(self, board_name: str) -> str:
        """
        Resolve a board name to its current COM port.

        Args:
            board_name: Human-readable key (e.g. ``"rig_1_behaviour"``).

        Returns:
            The COM port string (e.g. ``"COM7"``).

        Raises:
            KeyError: If *board_name* is not in the registry.
            RuntimeError: If the board is not currently connected.
        """
        info = self._boards.get(board_name)
        if info is None:
            raise KeyError(
                f"Board '{board_name}' not found in registry. "
                f"Known boards: {', '.join(sorted(self._boards))}"
            )
        return self._scan_for_board(info)

    def find_board_port_safe(self, board_name: str) -> Optional[str]:
        """
        Like :meth:`find_board_port` but returns ``None`` instead of raising.
        """
        try:
            return self.find_board_port(board_name)
        except (KeyError, RuntimeError):
            return None

    def get_board_info(self, board_name: str) -> BoardInfo:
        """
        Return the :class:`BoardInfo` for a registered board.

        Raises:
            KeyError: If *board_name* is not in the registry.
        """
        if board_name not in self._boards:
            raise KeyError(
                f"Board '{board_name}' not found in registry. "
                f"Known boards: {', '.join(sorted(self._boards))}"
            )
        return self._boards[board_name]

    def get_baudrate(self, board_name: str) -> int:
        """Return the baud rate configured for *board_name*."""
        return self.get_board_info(board_name).baudrate

    def reload(self) -> None:
        """Reload the registry from disk."""
        self._boards.clear()
        self._load()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Parse the JSON registry file."""
        if not self._path.exists():
            raise FileNotFoundError(
                f"Board registry not found: {self._path}\n"
                "Run 'python -m core.board_registry' to discover connected boards."
            )
        with open(self._path) as f:
            data = json.load(f)

        for name, entry in data.get("boards", {}).items():
            self._boards[name] = BoardInfo.from_dict(name, entry)

    @staticmethod
    def _scan_for_board(info: BoardInfo) -> str:
        """Scan USB serial ports for a board matching *info*."""
        for port_info in serial.tools.list_ports.comports():
            if (
                port_info.vid == info.vid
                and port_info.pid == info.pid
                and port_info.serial_number == info.serial_number
            ):
                return port_info.device

        raise RuntimeError(
            f"Board '{info.name}' ({info.description}) not found.\n"
            f"  Expected VID:PID = {info.vid:#06x}:{info.pid:#06x}, "
            f"serial = {info.serial_number}\n"
            "  Check that the device is plugged in."
        )


# ======================================================================
# Discovery tool
# ======================================================================

def discover_boards() -> None:
    """Print every connected USB serial device as a copy-paste-ready JSON snippet."""
    from colorama import Fore, Style, init
    init()

    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No USB serial devices detected.")
        return

    print(f"\n  {len(ports)} device(s) found. Copy any entry below into board_registry.json:\n")

    for p in sorted(ports, key=lambda x: x.device):
        vid_str = f'"0x{p.vid:04x}"' if p.vid is not None else "null"
        pid_str = f'"0x{p.pid:04x}"' if p.pid is not None else "null"
        sn_str = f'"{p.serial_number}"' if p.serial_number else "null"

        print(Fore.CYAN + f'        "{p.device}_RENAME_ME"' + Style.RESET_ALL + ": {")
        print(f'            "description": "{p.description}",')
        print(f'            "vid": {vid_str},')
        print(f'            "pid": {pid_str},')
        print(f'            "serial_number": {sn_str},')
        print(f'            "baudrate": 115200')
        print("        },\n")


def main() -> None:
    """Entry-point when run as ``python -m core.board_registry``."""
    print("=" * 70)
    print("  Board Registry — USB Serial Device Discovery")
    print("=" * 70)

    discover_boards()

    registry_path = Path(__file__).parent.parent / "config" / "board_registry.json"
    print(f"  Registry file: {registry_path}\n")

    # If a registry already exists, show which boards are currently found
    try:
        from colorama import Fore, Style
        registry = BoardRegistry(registry_path)
        print("  Current registry status:")
        print("  " + "-" * 50)
        for name, info in sorted(registry.boards.items()):
            try:
                port = registry.find_board_port(name)
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} {name:<25} -> {port}")
            except RuntimeError:
                print(f"  {Fore.RED}✗{Style.RESET_ALL} {name:<25} -> NOT FOUND")
        print()
    except FileNotFoundError:
        print("  No board_registry.json found yet — create one with the values above.\n")


if __name__ == "__main__":
    main()
