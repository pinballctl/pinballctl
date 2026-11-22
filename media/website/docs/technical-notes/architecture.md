# Architecture

Pinball CTL gives time-critical hardware work to the ESP32-S3 and runs game logic and presentation on the Raspberry Pi. The admin webapp is a separate process and can be stopped independently on a cabinet.

## One event pipeline

![The Pi and ESP publish and receive events through the bridge. Each evaluates its own rule actions. The Pi handles game state and presentation, while the ESP handles lighting playback and hardware outputs.](/media/pinballctl-event-pipeline.svg)

For a simple flipper rule, the ESP can run the GPIO action as soon as it sees the switch edge. The same event reaches the Pi, where an audio action from that rule can play its cue. Firmware with rules runtime version 3 supports this per-action routing after Rules Sync.

When a rule depends on a Pi-owned condition or trigger history, the Pi evaluates it first. Any resulting output request must pass the ESP's freshness and coil safety checks. [Bridge event flow](bridge-event-flow.md)

## Services and connections

![The admin webapp, bridge, game runtime and backglass run on the Pi. The USB bridge sends configuration, commands and heartbeats to the ESP and receives events and status. The ESP reads switches and drives playfield outputs.](/media/pinballctl-architecture.svg)

| Component | Responsibility |
| --- | --- |
| Browser and Flask webapp | Author hardware mappings, rules, scoring and presentation. Save settings, request deployments and display status. |
| Pi bridge | Own the USB serial connection, send heartbeats, deliver framed commands, correlate replies and queue observations for the runtime. |
| Pi runtime | Own game and ball state, scoring, rules that need host evaluation, audio and presentation. Persist runtime state and publish committed events. |
| ESP32-S3 | Debounce inputs, execute supported local rule actions, drive outputs and enforce coil safety. |
| Godot supervisor | Start and manage display processes. Provide scene events and leaderboard access over a private loopback interface. |

## Save, sync and verify

1. Save a mapping or ruleset in the web interface. The Pi stores the editable source in its instance directory.
2. Run the relevant Sync action. The Pi builds the deployed files and sends them through the bridge. The sync status reports whether the ESP applied them.
3. With coil power disconnected, test one mapped input. Compare Logs, the Playfield Live View tab and the Coil safety status with the observed response.

The ESP needs a healthy bridge heartbeat for coil arming. Stopping the admin webapp leaves the bridge, runtime and backglass services running when the systemd units are installed. [App layout and services](app-layout.md) · [Coil Safety](coil-safety.md)
