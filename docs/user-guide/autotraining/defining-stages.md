# Defining Stages

A stage is a named set of parameter overrides that define how trials run during a particular phase of training.

## The Stage dataclass

```python
from autotraining.stage import Stage

Stage(
    name="introduce_1_led",
    display_name="Introduce 1 Port + LED",
    description="Mouse learns to follow a single LED cue to port 5 for reward.",
    overrides={
        "port_5_enabled": True,
        "response_timeout": 5.0,
    },
    is_warmup=False,
    warmup_after=None,
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Unique identifier (used as dict key and in persistence) |
| `display_name` | `str` | required | Human-readable label for logging and GUI |
| `description` | `str` | `""` | What this stage trains the mouse to do |
| `overrides` | `dict` | `{}` | Parameter values that differ from `BASE_DEFAULTS` |
| `is_warmup` | `bool` | `False` | Mark this as the warm-up stage |
| `warmup_after` | `str \| None` | `None` | Only run warm-up if saved stage is at or past this stage |

### `get_params()`

Call `stage.get_params()` to get the full parameter set (BASE_DEFAULTS merged with overrides):

```python
params = stage.get_params()
# Returns: {all BASE_DEFAULTS with overrides applied}
```

## BASE_DEFAULTS

These are the default values for every parameter. Stages only override what they change:

```python
BASE_DEFAULTS = {
    # Port selection (all disabled by default)
    "port_0_enabled": False,
    "port_1_enabled": False,
    "port_2_enabled": False,
    "port_3_enabled": False,
    "port_4_enabled": False,
    "port_5_enabled": False,

    # Cue settings
    "cue_duration": 0.0,       # 0 = stay on until response
    "led_brightness": 255,

    # Platform settings
    "weight_offset": 3.0,
    "platform_settle_time": 1.0,

    # Trial timing
    "response_timeout": 5.0,
    "wait_duration": 0.0,
    "iti": 1.0,

    # Punishment
    "punishment_duration": 0.0, # 0 = no punishment
    "punishment_enabled": False,

    # Audio
    "audio_enabled": False,
    "audio_proportion": 6,
}
```

## Example: visual training stages

The visual training sequence defines 10 stages in two phases: **port introduction** (learning to follow LED cues across increasing numbers of ports) and a **cue duration ladder** (responding to increasingly brief LED flashes). Here are a few examples:

### Warm-up

```python
Stage(
    name="warm_up",
    display_name="Warm-Up",
    description="Start-of-day warm-up. All 6 ports, no punishment.",
    is_warmup=True,
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "response_timeout": 5.0,
    },
)
```

All ports active with no punishment. Gets the mouse engaged before the real training begins.

### Introduce 1 Port + LED

```python
Stage(
    name="introduce_1_led",
    display_name="Introduce 1 Port + LED",
    description="Mouse learns to follow a single LED cue to port 5.",
    overrides={
        "port_5_enabled": True,
        "response_timeout": 5.0,
    },
)
```

Only port 5 is active. The mouse learns that an LED turning on means "go to this port for reward".

### 2 Ports Active

```python
Stage(
    name="multiple_leds_2x",
    display_name="2 Ports Active",
    description="Ports 3 and 5 active. Mouse must discriminate between two cued ports.",
    overrides={
        "port_3_enabled": True,
        "port_5_enabled": True,
        "response_timeout": 5.0,
    },
)
```

Two ports are now active. The mouse must follow the LED to the correct port rather than always going to the same one.

### 6 Ports Active

```python
Stage(
    name="multiple_leds_6x",
    display_name="6 Ports Active",
    description="All 6 ports enabled with unlimited cue duration.",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "response_timeout": 5.0,
    },
)
```

Full 6-port randomisation with the LED staying on until the mouse responds. This is the gateway to the cue duration ladder.

### Cue Duration 500ms

```python
Stage(
    name="cue_duration_500ms",
    display_name="Cue Duration 500ms",
    description="All 6 ports, LED cue limited to 500ms.",
    overrides={
        "port_0_enabled": True,
        "port_1_enabled": True,
        "port_2_enabled": True,
        "port_3_enabled": True,
        "port_4_enabled": True,
        "port_5_enabled": True,
        "cue_duration": 0.5,
        "response_timeout": 5.0,
    },
)
```

The LED only stays on for 500ms. The mouse must remember which port was cued after the light turns off. The ladder continues down through 250ms and 100ms.

## Organising stages in code

Stage definitions live in `autotraining/definitions/`. Each training variant (audio, visual) gets its own subfolder:

```
autotraining/definitions/
├── audio/
│   ├── __init__.py
│   ├── stages.py      # Stage definitions
│   └── graph.py       # Transition rules
└── visual/
    ├── __init__.py
    ├── stages.py
    └── graph.py
```

### The `_register()` pattern

Stages are collected in a dict called `STAGES`, populated using a helper:

```python
STAGES: dict[str, Stage] = {}

def _register(stage: Stage) -> Stage:
    STAGES[stage.name] = stage
    return stage

_register(Stage(name="warm_up", ...))
_register(Stage(name="phase_1_platform_reward", ...))
# etc.
```

!!! important
    The order of `_register()` calls matters -- it defines the stage ordering used by the `warmup_after` gate logic. Stages should be registered from earliest to latest in the training progression.
