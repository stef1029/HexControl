"""
Autotraining System - Adaptive Training Flowchart

Manages automatic progression through training stages based on mouse
performance. The system monitors trial outcomes and transitions between
stages according to configurable rules.

Architecture:
    - stage.py:         Stage dataclass (parameter set for a training phase)
    - transitions.py:   Transition rules and condition evaluation
    - engine.py:        Graph walker that manages active stage and transitions
    - persistence.py:   Save/load mouse training state across sessions
    - definitions/:     Stage definitions and transition graph (pure data)
"""
