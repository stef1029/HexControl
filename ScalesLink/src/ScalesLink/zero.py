"""
Scales Zeroing Utility

Provides functions for zeroing (taring) scales on behaviour rigs.
This is a standalone utility that can be used before starting a session.

Usage:
    from ScalesLink.zero import zero_scales, zero_all_scales
    
    # Zero a single scales unit
    success, message = zero_scales("COM10", baud_rate=9600)
    
    # Zero multiple scales from config (resolves board names via registry)
    results = zero_all_scales(rig_configs)
"""

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

import serial


@dataclass
class ZeroResult:
    """Result of a zeroing operation."""
    rig_name: str
    com_port: str
    success: bool
    message: str


def zero_scales(
    com_port: str,
    baud_rate: int = 9600,
    timeout: float = 2.0,
) -> tuple[bool, str]:
    """
    Zero (tare) scales on the specified COM port.
    
    Sends the 'e' command to end acquisition, waits, then sends 't' to tare.
    This is the same sequence used by the old zs.py script.
    
    Args:
        com_port: Serial port (e.g., "COM10")
        baud_rate: Baud rate for serial connection
        timeout: Serial timeout in seconds
        
    Returns:
        Tuple of (success, message)
    """
    ser = None
    try:
        # Open serial connection
        ser = serial.Serial(com_port, baud_rate, timeout=timeout)
        
        # Send 'e' to end acquisition mode
        ser.write(b'e')
        time.sleep(2)
        
        # Send 't' to tare
        ser.write(b't')
        time.sleep(3)
        
        return True, "Zeroed successfully"
        
    except serial.SerialException as e:
        return False, f"Serial error: {e}"
    except Exception as e:
        return False, f"Error: {e}"
    finally:
        if ser is not None and ser.is_open:
            try:
                ser.close()
            except Exception as e:
                logger.warning(f"[Scales] error closing serial: {e}")


def zero_all_scales(
    rig_configs: list[dict],
    registry = None,
    callback: Optional[callable] = None,
) -> list[ZeroResult]:
    """
    Zero scales on all configured rigs.
    
    Board names are resolved to COM ports via the board registry.
    Falls back to com_port if board_name is not set (legacy support).
    
    Args:
        rig_configs: List of rig configuration dicts from rigs.yaml.
                     Each should have a "scales" sub-dict with "board_name".
        registry: A BoardRegistry instance for resolving board names to COM ports.
        callback: Optional function called with (rig_name, status_message)
                  after each rig is processed.
    
    Returns:
        List of ZeroResult objects with success/failure for each rig.
    """
    results = []
    
    for rig in rig_configs:
        rig_name = rig.get("name", "Unknown")
        scales_config = rig.get("scales")
        
        # Skip rigs without scales config
        if scales_config is None:
            results.append(ZeroResult(
                rig_name=rig_name,
                com_port="N/A",
                success=False,
                message="No scales configured"
            ))
            if callback:
                callback(rig_name, "No scales configured")
            continue
        
        # Skip disabled scales
        if not scales_config.get("enabled", True):
            results.append(ZeroResult(
                rig_name=rig_name,
                com_port=scales_config.get("com_port", "N/A"),
                success=False,
                message="Scales disabled"
            ))
            if callback:
                callback(rig_name, "Scales disabled")
            continue
        
        # Skip non-wired scales (wireless scales don't support tare command)
        if not scales_config.get("is_wired", False):
            results.append(ZeroResult(
                rig_name=rig_name,
                com_port="N/A",
                success=False,
                message="Wireless scales (tare not supported)"
            ))
            if callback:
                callback(rig_name, "Wireless scales (tare not supported)")
            continue
        
        # Resolve COM port: prefer board registry, fall back to legacy com_port
        board_name = scales_config.get("board_name", "")
        com_port = ""
        baud_rate = scales_config.get("baud_rate", 115200)
        
        if board_name and registry is not None:
            try:
                com_port = registry.find_board_port(board_name)
            except (KeyError, RuntimeError) as e:
                results.append(ZeroResult(
                    rig_name=rig_name,
                    com_port=board_name,
                    success=False,
                    message=f"Board not found: {e}"
                ))
                if callback:
                    callback(rig_name, f"Board not found: {e}")
                continue
        else:
            # Legacy fallback
            com_port = scales_config.get("com_port", "")
        
        if not com_port:
            results.append(ZeroResult(
                rig_name=rig_name,
                com_port="N/A",
                success=False,
                message="No board_name or com_port configured"
            ))
            if callback:
                callback(rig_name, "No board_name or com_port configured")
            continue
        
        if callback:
            callback(rig_name, f"Zeroing {com_port}...")
        
        success, message = zero_scales(com_port, baud_rate)
        
        results.append(ZeroResult(
            rig_name=rig_name,
            com_port=com_port,
            success=success,
            message=message
        ))
        
        if callback:
            callback(rig_name, message)
    
    return results


def get_summary(results: list[ZeroResult]) -> str:
    """
    Generate a summary string from zeroing results.
    
    Args:
        results: List of ZeroResult objects
        
    Returns:
        Human-readable summary string
    """
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    lines = []
    
    if successful:
        lines.append(f"✓ Zeroed successfully ({len(successful)}):")
        for r in successful:
            lines.append(f"    {r.rig_name} ({r.com_port})")
    
    if failed:
        if lines:
            lines.append("")
        lines.append(f"✗ Failed ({len(failed)}):")
        for r in failed:
            lines.append(f"    {r.rig_name}: {r.message}")
    
    if not results:
        return "No scales found to zero"
    
    return "\n".join(lines)


# ── Configuration (for standalone use) ────────────────────────
RIGS_CONFIG_PATH: str = r"C:\Dev\projects\rigs_config.yaml"
BOARD_REGISTRY_PATH: str = r"C:\Dev\projects\board_registry.json"
RIG_NUMBER: int = 3
# ──────────────────────────────────────────────────────────────


def main():
    """Zero scales for a single rig, using the config above."""
    import yaml

    config_path = Path(RIGS_CONFIG_PATH)
    if not config_path.exists():
        print(f"ERROR: Rigs config not found: {config_path}")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    rigs = config.get("rigs", [])
    if RIG_NUMBER < 1 or RIG_NUMBER > len(rigs):
        print(f"ERROR: RIG_NUMBER={RIG_NUMBER} is out of range (1-{len(rigs)})")
        return

    rig = rigs[RIG_NUMBER - 1]
    rig_name = rig.get("name", f"Rig {RIG_NUMBER}")
    scales_cfg = rig.get("scales")
    if not scales_cfg:
        print(f"ERROR: No 'scales' section found for {rig_name}")
        return

    board_name = scales_cfg.get("board_name", "")
    baud_rate = scales_cfg.get("baud_rate", 115200)
    is_wired = scales_cfg.get("is_wired", False)

    if not is_wired:
        print(f"{rig_name}: Wireless scales — tare not supported over serial")
        return

    if not board_name:
        print(f"ERROR: No 'board_name' in scales config for {rig_name}")
        return

    # Resolve COM port via board registry
    try:
        _brs_root = Path(__file__).resolve().parents[3] / "behaviour_rig_system"
        if str(_brs_root) not in sys.path:
            sys.path.insert(0, str(_brs_root))
        from core.board_registry import BoardRegistry
        registry = BoardRegistry(Path(BOARD_REGISTRY_PATH))
        com_port = registry.find_board_port(board_name)
    except Exception as e:
        print(f"Failed to resolve board '{board_name}': {e}")
        return

    print(f"Zeroing scales for {rig_name}")
    print(f"  Board: {board_name} -> {com_port} @ {baud_rate}")

    success, message = zero_scales(com_port, baud_rate)
    if success:
        print(f"  ✓ {message}")
    else:
        print(f"  ✗ {message}")


if __name__ == "__main__":
    main()
