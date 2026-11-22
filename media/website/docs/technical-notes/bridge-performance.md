# Bridge performance and overload

Platform → Performance shows throughput, outstanding work, and event confirmation
latency, including a separate measurement of time spent in the bridge queue.
Scoring notifications retain their full data on the host bus and in event logs.
They stay local when neither authored nor confirmed deployed rules reference them;
unknown or changed deployments keep forwarding. Forwarded scoring notifications
carry only the event identity and trigger fields used by the ESP, rather than the
full award breakdown. This reduces traffic without changing safety thresholds.
Connected Live View events run on the ESP and enter the host event bus on their
confirmation, just like real switch notifications. Offline Live View uses the
local fallback. Host-derived/scoring notifications already published locally
carry bridge-only context: their confirmation runs dependent host rules without
publishing the same notification to scoring/audio/media again. This context also
retains parameters that the compact ESP echo does not include; it is not sent on
the serial wire and its history is bounded to 256 events (not durable across a
bridge restart).

Firmware v0.0.10 marks events whose deployed rules were evaluated. For those
events the host does not repeat pixel-lighting actions or statically configured
LCD actions that the firmware can execute. LCD placeholders are expanded only
on the host. Older firmware and offline simulation retain host fallbacks.
Confirmations acknowledge ESP event handling, not physical output movement.
Firmware advertises its supported event window: older firmware defaults to eight;
v0.0.9 supports sixteen with enlarged serial buffers and bounded output pumping.

If an event waits over 100 ms in the bridge queue, or a pending confirmation takes
over 250 ms, the bridge stops gameplay activations and disarms coils. Firmware
v0.0.11 adds a confirmed runtime pause: output timers and old button gestures are
cleared, while releases and physical switch levels remain tracked. After at least
two seconds and a continuous quiet second with drained queues, the bridge requests
recovery. Previously armed coils are re-armed through the existing generation and
heartbeat checks; recovery itself does not activate outputs. Inputs held across
the pause must release and press again. Rejected events are never replayed.

Three overloads within 60 seconds, a firmware fault, or an unconfirmed recovery
leave the system disarmed. Firmware faults are never automatically cleared. The
Performance diagnostic reset requests the same handshake with coils left disarmed;
normal isolated recovery needs no UI or game-specific Start event. Older firmware
without the pause handshake cannot recover automatically. Platform notifications
`PLATFORM_OVERLOAD`, `PLATFORM_OVERLOAD_FAULT` and
`PLATFORM_OVERLOAD_RECOVERED` are emitted on the host bus
and recorded in the event log.

`.venv/bin/python tests/tools/bridge-load-test.py --mode fire` runs bounded diagnostic events that do not
match configured rules and stops escalating on overload. Use the project Python
environment and provide `--output /path/to/report.json`. Its ECHO round trips measure
host IPC and serial responsiveness, not switch-to-coil latency. Dev-board results
do not establish electrical timing or performance with a complete machine attached.
