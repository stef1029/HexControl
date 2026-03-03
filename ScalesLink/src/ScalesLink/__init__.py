"""
ScalesLink - Scales communication library for behavioural experiment rigs.

This module provides a clean interface for reading weight data from scales
connected to behavioural experiment rigs.

For direct hardware access (e.g., testing):
    from ScalesLink import Scales, ScalesConfig
    
    config = ScalesConfig.from_yaml_dict(rig_config["scales"])
    with Scales(config) as scales:
        weight = scales.get_weight()

For subprocess architecture (recommended for behaviour sessions):
    # Start server subprocess (managed by PeripheralManager)
    # Then use client in protocols:
    
    from ScalesLink import ScalesClient
    
    client = ScalesClient(tcp_port=5100)
    client.connect()
    weight = client.get_weight()

For zeroing scales before sessions:
    from ScalesLink import zero_scales, zero_all_scales
    
    success, message = zero_scales("COM10")
"""

from .scales import Scales, ScalesConfig
from .calibrate import run_calibration
from .client import ScalesClient, quick_get_weight
from .zero import zero_scales, zero_all_scales, ZeroResult, get_summary
from .manager import ScalesManager

__all__ = [
    # Direct hardware access
    "Scales",
    "ScalesConfig",
    "run_calibration",
    # Client for subprocess architecture
    "ScalesClient",
    "quick_get_weight",
    # Manager for subprocess lifecycle
    "ScalesManager",
    # Zeroing utilities
    "zero_scales",
    "zero_all_scales",
    "ZeroResult",
    "get_summary",
]
