# ScalesLink Quick Start

## Direct usage (context manager)

For standalone use or testing:

```python
from ScalesLink import Scales, ScalesConfig

config = ScalesConfig(
    port="COM10",
    baud_rate=115200,
    scale=0.22375,
    intercept=-5617.39,
    is_wired=True,
)

with Scales(config, log_path="scales_log.csv") as scales:
    weight = scales.get_weight()
    if weight is not None:
        print(f"Weight: {weight:.2f} g")
```

## Subprocess usage (via ScalesManager)

The typical usage in the rig system runs scales in a subprocess with TCP communication:

```python
from ScalesLink import ScalesManager

manager = ScalesManager(
    com_port="COM10",
    baud_rate=115200,
    tcp_port=5101,
    is_wired=True,
    calibration_scale=0.22375,
    calibration_intercept=-5617.39,
    session_folder="D:\\session",
    log_callback=print,
)

if manager.start():
    # Read weight through TCP client
    weight = manager.client.get_weight()
    print(f"Weight: {weight}")

    # ... run experiment ...

    manager.stop()
```

## Quick one-shot reading

```python
from ScalesLink import quick_get_weight

weight = quick_get_weight(tcp_port=5101)
if weight is not None:
    print(f"Weight: {weight:.2f} g")
```

## Loading config from YAML

```python
from ScalesLink import ScalesConfig

yaml_dict = {
    "board_name": "rig_1_scales",
    "baud_rate": 115200,
    "is_wired": True,
    "calibration_scale": 0.22375,
    "calibration_intercept": -5617.39,
}

config = ScalesConfig.from_yaml_dict(yaml_dict, registry=board_registry)
```

The `from_yaml_dict()` factory resolves `board_name` to a COM port via the board registry.
