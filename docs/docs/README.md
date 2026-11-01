# Your machine. Your rules. Your game.

Pinball CTL helps you bring a homebrew pinball machine to life. Connect switches and outputs, choose what happens when the ball hits a target, and build the lighting, sound and scoring around your game.

You don't need to finish the whole machine before making something work. Start with one input. Watch it appear in the software. Give it a simple rule. Once that works, add the next piece.

## Choose your next step

- [Quick Start](1-user-guide/0-quick-start.md): one physical input and a safe first rule.
- [Detailed Setup](1-user-guide/1-getting-started.md): prepare the Pi, install the development build and connect your controller.
- [Feature Guides](1-user-guide/3-featured.md): learn the tools for your next part of the build.
- [Troubleshooting](1-user-guide/26-troubleshooting.md): work from a symptom to a safe check.

## How the parts fit together

Use your browser to author the project. The Raspberry Pi runs the application and bridge, plus host services such as audio and displays. The ESP32-S3 reads physical inputs, handles supported real-time output behaviour and enforces configured output safety limits. A USB data cable carries framed JSON between the Pi and ESP.

Events report what happened. Rules decide what happens next. Save records your authored configuration; sync deploys supported configuration to the ESP. Neither step is permission to bypass arming or output safety checks.

## Development version

This manual follows current committed `main`, including Backup / Restore. Older tagged releases may lack features shown here even when the version number matches. Record the installed Git revision using Detailed Setup. Game and Ball Management are also evolving. Read their guides before configuring session lifecycle, physical observations or recovery.

## Game and ball management

[Game Management](1-user-guide/26-game-management.md) covers logical sessions, credits and player turns. [Ball Management](1-user-guide/27-ball-management.md) covers physical device observations and reconciliation. A logical game state is not proof of a ball's physical position.

## Work safely

Keep coils disconnected for first-input and first-rule tests. Use suitable drivers, fuses and flyback protection for high-current loads; never connect them directly to GPIO. Disconnect output power while wiring. Firmware limits cannot correct unsafe wiring. Read [Hardware](1-user-guide/7-hardware.md) before testing outputs.

## Advanced reference

Read [Advanced Reference](2-technical-notes/README.md) for architecture, the bridge protocol, event dispatch and development information. The ESP development plan describes goals and must not be read as a shipped feature list.
