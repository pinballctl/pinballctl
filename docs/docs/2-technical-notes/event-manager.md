# Event Dispatch Internals

Start with the event name and source shown in [Logs](../1-user-guide/14-logs.md). For host processing, follow the ingress through `events/bus.py` and `events/manager.py`.

## Ingress and routing

The Events API accepts permitted injected events. The bridge supplies controller observations. Game and Ball publish committed lifecycle results through their outbox. The normalized context carries the event name, source and payload used to select routes.

| Route key | Scope |
| --- | --- |
| `all` | Every dispatched event |
| `event:<name>` | Exact event name |
| `system:<name>` | Known system event |
| `hardware:<deviceClass>:<eventType>` | Hardware source resolved through the saved mapping |
| `custom` | Recognised custom event |

## Check routing and execution separately

The registry describes available events and the coverage endpoint reports handler registration. To verify that a rule actually executes, inspect its trigger, source, enabled state and action result. Check the hardware mapping if a source does not resolve to the expected device class.

Keep physical and synthetic inputs distinct when testing. Reserved manager events are produced by their owner. Use a typed manager request for an operation such as starting a game, then follow its result in Logs. See [Management Ownership](management-ownership.md).
