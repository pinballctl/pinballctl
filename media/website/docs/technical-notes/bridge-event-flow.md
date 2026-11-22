# Bridge Event Flow

Open **ESPLink** for the live connection and **Logs → Events** to follow a switch edge. Compare the event name, source, gesture and acknowledgement before investigating the output.

## Physical and Live View inputs

1. The ESP debounces a physical switch and evaluates its local rules. It publishes the event with physical provenance and the input level when available.
2. Live View submits a synthetic switch edge through the Events API. While connected, the bridge forwards it as `EVENT_FIRE`. The ESP evaluates the same eligible rules and returns the event confirmation.
3. The bridge sends confirmed events through the Pi's ordered host worker. Rules, audio and presentation consume the event, and Live View updates from the event stream. When the bridge is offline, the Events API can dispatch locally.
4. Only bridge-validated physical events can drive bound coin/start inputs and trusted Ball observations. The Pi publishes committed manager results for scoring, Rules and presentation.

## Where the actions run

Rules runtime version 3 keeps mixed rules in one authored definition. For a simple switch trigger, the ESP can run supported GPIO and lighting actions while the Pi runs audio or other host actions from the same event. The Pi uses the ESP's event acknowledgement to avoid resending locally owned actions.

Rules that need Pi-side conditions or trigger history wait for that evaluation. Output requests from the Pi still pass the ESP's freshness checks and coil safety policy. A controller acknowledgement confirms event handling. Bench observation is how you verify electrical output. [Coil Safety](coil-safety.md)

## Sync and diagnostics

Hardware Sync drains outstanding event confirmations before it starts applying configuration. Activations that arrive during the serial work are discarded so a held or queued press cannot fire later. Fresh events are accepted again after sync. [Bridge performance](bridge-performance.md)

Use [Bridge Protocol](bridge-protocol.md) for command framing and [Event Dispatch Internals](event-manager.md) for host routing.
