# Autotraining

The autotraining system automatically progresses mice through training stages based on their performance. Instead of manually deciding when a mouse is ready for the next phase, the system evaluates configurable transition rules after every trial and switches stages when conditions are met.

## Overview

The visual autotraining sequence has two phases: **port introduction** (learning to follow LED cues across increasing numbers of ports) and a **cue duration ladder** (responding to increasingly brief LED flashes).

```mermaid
graph TD
    WU[Warm-Up] -->|5 consecutive correct, 10+ trials| SAVED["Mouse's saved stage"]

    S1[Introduce 1 Port] -->|">90% over 30"| S2[Introduce Another Port]
    S2 -->|">90% over 30"| S3[2 Ports Active]
    S2 -.->|"< 30% over 20"| S1

    S3 -->|">90% over 40"| S4[6 Ports Active]
    S3 -.->|"< 30% over 20"| S2

    S4 -->|">90% over 30"| C1[Cue 1000ms]
    S4 -.->|"< 30% over 20"| S3

    C1 -->|">75% over 30"| C2[Cue 750ms]
    C1 -.->|"< 25% over 20"| S4
    C2 -->|">60% over 30"| C3[Cue 500ms]
    C2 -.->|"< 25% over 20"| C1
    C3 -->|">50% over 30"| C4[Cue 250ms]
    C3 -.->|"< 25% over 20"| C2
    C4 -->|">40% over 30"| C5[Cue 100ms]
    C4 -.->|"< 25% over 20"| C3
    C5 -.->|"< 20% over 20"| C4

    style WU fill:#e1f5fe
    style C5 fill:#c8e6c9
```

Solid arrows are forward transitions (progression). Dashed arrows are regression transitions (falling back when performance drops).

## Key concepts

- **Stages** -- Named sets of parameter overrides that define how trials run during each phase of training
- **Transitions** -- Rules that move the mouse between stages based on performance metrics
- **Persistence** -- Training progress is saved between sessions so mice resume where they left off
- **Warm-up** -- Optional start-of-session stage to get the mouse engaged before resuming the real training stage

## Guides

- [Concepts](concepts.md) -- The mental model behind autotraining
- [Defining Stages](defining-stages.md) -- How to create stage definitions
- [Defining Transitions](defining-transitions.md) -- How to write transition rules
- [Persistence & Progress](persistence.md) -- How training state is saved and loaded
- [Creating a Custom Training Sequence](custom-sequence.md) -- End-to-end tutorial
