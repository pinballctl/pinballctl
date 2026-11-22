# App layout and services

Use this map to find the process, code and stored data involved in a change. In an editable checkout, machine data lives under `src/instance/`.

| Area | Location |
| --- | --- |
| CLI and systemd unit definitions | `src/pinballctl/cli.py` and `src/pinballctl/runtime/ops/service.py` |
| Flask application factory, authentication and module discovery | `src/pinballctl/webapp/` |
| Admin pages, routes and browser assets | `src/pinballctl/webapp/modules/` |
| Serial ownership, queue, RPC and bridge state | `src/pinballctl/runtime/bridge/` |
| Event ingress, dispatch and audit logging | `src/pinballctl/runtime/events/` |
| Rules registry, host evaluation and deployment compiler | `src/pinballctl/runtime/rules/` and `src/pinballctl/runtime/ops/rules_blob.py` |
| Game and credit transactions, Ball observations and Scoring | `src/pinballctl/runtime/game/`, `ball/` and `scoring/` |
| Audio, lighting, media and Godot supervision | `src/pinballctl/runtime/audio/`, `lighting/` and `media/` |
| Packaged Godot player | `src/pinballctl/runtime/godot/` |
| ESP32-S3 firmware | `src/firmware/` |
| Sample backglass project and website | `media/backglass/` and `media/website/` |

Within the firmware, `protocol/` handles commands and deployment, `runtime/` handles rules and lighting, and `drivers/` groups implementations by device function. Coil arming and limits live under `safety/`.

## Cabinet services

| Unit | Runs |
| --- | --- |
| `pinball-web.service` | Gunicorn and the Flask admin webapp |
| `pinball-runtime.target` | The group containing the serial bridge and media supervisor |
| `pinball-bridge.service` | Serial connection, heartbeat, event ingress and ordered Pi-side rule work |
| `pinball-media.service` | Godot supervisor and display autoplay |

On systemd, `pinballctl service stop web` closes the admin listener. The runtime target, bridge, and media processes continue running. The Godot supervisor supplies a private authenticated loopback interface for scene events and leaderboard requests. Scene events use the same runtime ingress as other host events.

For manual development, `pinballctl start` starts local processes. Use `--web-only` with `start`, `reload` or `stop` to manage only Gunicorn. [Development and testing](../developer-guide/development.md)

## Trace a change

1. Start in the feature's web blueprint for an admin request. Most modules use `views.py` or `api.py`.
2. Follow the runtime function it calls. The request may update authored files, execute a manager transaction or queue a bridge command.
3. For ESP work, follow the framed command from `runtime/bridge/daemon.py` to `src/firmware/src/System.cpp` and the firmware protocol handler.
4. Check the acknowledgement for a sync or device command before relying on the result.

Hardware mappings, rules and presentation data are stored in their feature directories under the instance. Game, Ball and Scoring use `game/management.sqlite`. Built firmware is registered in the local ESPLink catalogue. Website sources and example backglass content live under `media/`. [Backup and restore](../user-guide/backup-restore.md) · [Godot runtime](../developer-guide/godot-runtime.md)

## Shared interface styling

The webapp base template loads Bootstrap and `src/pinballctl/webapp/core/static/css/interface.css` for the shared palette, navigation, tables, forms and dialogs. Configuration dialogs can use `app-drawer` on an existing Bootstrap modal. Preserve dialog IDs, labels, dismissal controls and lifecycle handlers. Check both themes, keyboard dismissal and narrow screens when changing this layer.
