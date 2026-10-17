# Event Manager

Pi-side event dispatch is implemented in `src/pinballctl/events/manager.py`.

## Ingress Points

Events currently enter dispatch from:
- API ingress (`/api/events/fire`).
- Bridge RX ingress for ESP-origin event payloads.

## Dispatch Model

Dispatch normalizes an `EventContext` and resolves route keys:
- `all`
- `event:<name>`
- `system:<name>` (for known system events)
- `hardware:<deviceClass>:<eventType>` (source-resolved)
- `custom` (pattern-matched custom events)

Handlers are registered per route key.

## Current State

- Registry-driven route catalogs are loaded from rules registry.
- Default registrations are explicit no-op handlers (`_NoopHandler`).
- Coverage reporting distinguishes route registration vs behavior implementation.

This means the structure is in place and measurable, while feature logic can be added route-by-route.

## Mapping Dependency

Hardware route resolution uses `src/instance/hardware/mapping.json` to map source ids to device class.
