# Architecture

This section covers the internal design of the Behaviour Rig System for developers who need to understand, modify, or extend the codebase.

## Guides

- [System Overview](system-overview.md) -- Three-layer architecture, event-driven communication, and dependency structure
- [Session Lifecycle](session-lifecycle.md) -- The `SessionStatus` state machine, startup sequence, and cleanup
- [GUI System](gui-system.md) -- Mode management, parameter widget generation, and thread-safe event handling
- [Autotraining Engine](autotraining-engine.md) -- Internal state machine, `TransitionContext`, and stage-scoped rolling accuracy
- [BehavLink Protocol Spec](behavlink-protocol.md) -- Wire-level binary protocol, frame format, CRC16, and command bytes
- [Threading Model](threading-model.md) -- All threads in the system, why they exist, and how they communicate safely
