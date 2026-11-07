# Architecture

Follow a switch from the ESP32-S3 to the host, then follow a saved rule back to the controller.

| Component | Responsibility |
| --- | --- |
| Browser and Flask app | Configure hardware, rules, scoring and presentation. Read status and submit explicit commands. |
| Bridge daemon | Own the USB serial link, correlate replies and route controller observations. |
| Host runtimes | Manage games, balls, scoring, host-side rules, sound and displays. Persist authored configuration and runtime state. |
| ESP32-S3 | Read inputs, execute supported local rules and guard output activity with arming, watchdog and coil limits. |
| Godot host | Render configured display scenes and apply text values such as the current score. |

## Save, deploy and observe

1. Save a mapping or rule in the web interface. The host stores the authoring data in its instance directory.
2. Use the module's sync action to send the applicable runtime configuration. Check the reported result before relying on it.
3. Operate a mapped input with high-current output power disconnected. Compare the physical event in **Logs → Events** with the state or rule result it produced.

Keep time-critical output decisions close to the hardware. Host requests reach the ESP through the [framed bridge](bridge-protocol.md), where the firmware enforces output safety. For durable game state and the boundary between physical evidence and gameplay, see [Management Ownership](management-ownership.md).
