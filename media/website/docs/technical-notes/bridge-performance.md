# Bridge performance and overload

Open **Platform → Performance** to see outstanding work, event throughput and confirmation latency. Observe the values during the same test you are investigating.

## Read the timings

| Measurement | What it covers |
| --- | --- |
| Bridge queue wait | Time from a request entering the bridge queue until it is sent to the ESP. |
| Confirmation round trip | Time from sending a tracked event until the bridge receives its ESP response. |
| Event delivery latency | Queue wait and confirmation round trip together. |
| Host completion | Time from admission to the ordered Bridge worker through its processing, including queue delay. |
| Live View response | The trip through the configured event pipeline, plus browser event-stream delivery and rendering. |

ESP confirmation indicates event handling. Use a measurement at the hardware to check switch-to-output timing. The bridge bounds outstanding tracked events by the window advertised by firmware, up to 16. Its latency history uses the most recent 256 confirmed round trips.

## Keep the event path responsive

The ESP handles supported local actions before sending the event to the Pi. With rules runtime version 3, one rule can run its coil or pixel action on the ESP and its audio action on the Pi. Pi-evaluated output decisions still use the timed `RULE_ACTIONS` guard. The active rules blob controls the version reported in event acknowledgements. Sync Rules after updating both sides to activate version 3.

Scoring notifications stay local when neither authored nor confirmed deployed rules reference them. When forwarding is needed, the bridge sends compact trigger data and retains the full host payload for downstream processing. An echo can trigger dependent rules without repeating the original scoring or presentation notification. [Bridge event flow](bridge-event-flow.md)

## Startup and sync

The bridge discards activations queued before startup or reconnection is ready. Hardware Sync drains in-flight events before coil configuration, mapping transfer and accelerometer configuration. During the exclusive serial work, new activations are discarded. Releases remain eligible after the transfer, and the planned wait is excluded from their normal send budget. When the heartbeat and deployment checks pass, the ESP can arm. [Coil Safety](coil-safety.md)

## Overload and recovery

A gameplay queue wait over **100 ms**, or a pending confirmation over **250 ms**, triggers the overload path. The bridge stops new activations and requests that the ESP pause rules and disarm. Releases remain eligible to clear held state.

An isolated delivery overload can recover after at least two seconds and a continuous quiet second with the queues drained. The ESP acknowledges recovery while disarmed, then runs automatic arming checks. Inputs held across the pause must release and press again. Discarded activations are never replayed.

Three overloads within 60 seconds, an unconfirmed recovery or a firmware fault can leave the system disarmed. The **Reset overload** diagnostic handles bridge recovery. A latched ESP safety fault needs its own reset. Logs record `PLATFORM_OVERLOAD`, `PLATFORM_OVERLOAD_FAULT` and `PLATFORM_OVERLOAD_RECOVERED`.

## Measure on the bench

With coil power disconnected, compare a Live View event with the ESP acknowledgement and check for queue growth or drops. The bridge diagnostic under `tests/tools/bridge-load-test.py` can exercise bounded delivery and ECHO round trips. Choose a diagnostic event that has no rule actions and use an isolated instance when testing load. [Performance guide](../user-guide/performance.md)

For a physical switch, measure the input edge to a firmware-driven output separately from the input edge to a Pi-driven output, sound or display update. Record physical wire bytes per second and host queue depth during bursts. On a 460800-baud UART with 8N1 framing, a 94-byte frame takes about 2.0 ms to transmit before USB adapter and host delays. Frame size varies with the source, event name and device observations. Native USB has different timing.

Count received and successfully processed events separately. Use the firmware input-drop, missing-sequence, repeated-sequence, host-drop and frame-error counters to distinguish a slow worker from a loss on the inbound path. Missing sequence and firmware-drop counts can describe the same loss. [Performance guide](../user-guide/performance.md#metric-cards)
