# Bridge Event Flow

Use **ESPLink** to check the live connection, then **Logs → Events** to follow an input through the host.

## Follow a switch event

1. The ESP reads the input and handles any applicable local action. It publishes the observation as a framed event.
2. The bridge decodes the frame and validates the source and provenance. Mapped physical observations can feed Game and Ball. Synthetic events take the host test or Rules path allowed for that event.
3. Host work runs outside the serial receive loop. For a managed turn, scoring from the input is processed before a drain can advance the player.
4. Committed manager results reach Rules, presentation and the shared event log through the host dispatch path. Compare the original input and any derived events by timestamp and source.

## Follow a device command

Host code enqueues a command to the bridge. Commands expecting replies use a request ID for correlation. Inspect the acknowledgement for a configuration or control operation before treating it as applied. An input event arriving during an RPC is independent traffic.

Use [Bridge Protocol](bridge-protocol.md) for frame fields and [Event Dispatch Internals](event-manager.md) for host routes. When investigating load, compare bridge status and [Performance](../1-user-guide/23-performance.md) during the same test. Measure on the target machine with the actual rules and event mix.
