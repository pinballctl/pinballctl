# App Layout

| Area | Source |
| --- | --- |
| Start, stop and status commands | `src/pinballctl/cli.py` |
| Flask application factory and module discovery | `src/pinballctl/app/__init__.py` |
| Module pages, endpoints and assets | `src/pinballctl/app/modules/` |
| USB serial, command queue and bridge state | `src/pinballctl/bridge/` |
| Event bus, dispatch and audit logging | `src/pinballctl/events/` |
| Game transactions and command registry | `src/pinballctl/game/` |
| Ball observation and movement | `src/pinballctl/ball/runtime.py` |
| Scoring, rules, audio, lighting and media | Feature packages under `src/pinballctl/` |
| ESP32-S3 firmware | `src/firmware/` |
| Godot display host and sample pack project | `src/godot/` and `backglass/`, respectively |
| Website and user guides | `website/` and `docs/docs/` |

## Trace a request

Start with the module's blueprint. Many modules put page routes in `views.py` and JSON routes in `api.py`. Game and Ball share the Game module's web implementation. Follow the route into its runtime or service for validation and persistence. For a device command, follow the bridge enqueue or RPC call into `bridge/daemon.py`, then the framed receiver in `src/firmware/src/System.cpp`.

For an editable checkout, the application instance normally lives under `src/instance/`. Mapping, rules and media data live in feature directories there. Manager state is in `game/management.sqlite` relative to that instance. Use [Backup / Restore](../1-user-guide/25-backup-restore.md) to move authored data and selected runtime state.

## Shared interface styling

The base template loads Bootstrap, the existing module styles and core helpers, then
`src/pinballctl/app/core/static/css/interface.css`. This shared layer defines the
light/dark palette, navigation, tables, forms, cards and dialog presentation.
Use these shared controls when adding modules instead of introducing page-specific
versions of the same styles. Preserve semantic warning, error and disabled states.

Configuration dialogs can opt into the right-hand panel with `app-drawer` on their
existing Bootstrap `modal` element. Keep the existing dialog IDs, labelled title,
dismiss controls and Bootstrap lifecycle handlers: the class changes presentation,
not validation, persistence or device commands. Confirmation and status dialogs
remain centred. Check both themes, keyboard dismissal and narrow screens when
changing this layer.
