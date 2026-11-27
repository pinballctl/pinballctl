# Development and testing

Run these commands from the repository root. Use Python 3.11 or later for the
application; the website build uses Python 3.12 or later.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Source layout

| Path | Responsibility |
| --- | --- |
| `src/pinballctl/webapp/` | Flask application, feature modules, templates and browser assets |
| `src/pinballctl/runtime/bridge/` | USB serial, framed commands, state and reconnect handling |
| `src/pinballctl/runtime/events/` | Host event ingress, routing and audit logs |
| `src/pinballctl/runtime/game/`, `ball/`, `scoring/` | Game lifecycle, physical ball observations and scoring |
| `src/firmware/` | ESP32-S3 input/output runtime and safety |
| `src/pinballctl/runtime/godot/` | Godot media host |
| `media/backglass/` | Separately editable sample Godot projects |
| `media/website/docs/` | User, technical, developer and build guides, plus topic-based Developer Notes |
| `media/website/utils/` | Website build, checks and screenshot utilities |
| `tests/`, `utils/` | Regression tests and project utilities |

See [App Layout](../technical-notes/app-layout.md) to trace requests and locate persisted state.
The normal editable-checkout instance is `src/instance/`; it contains machine data,
media and logs. Keep those files and `.local/` backups out of source commits.

## Run the application

```sh
.venv/bin/pinballctl start
.venv/bin/pinballctl status
.venv/bin/pinballctl stop
```

The UI normally listens on port 8888. Test against a separate configuration when
changing runtime behaviour. Starting the application may start its configured
services and connect to local devices; disconnect output power for initial tests.

For a manual checkout, use `pinballctl start --web-only`, `pinballctl reload --web-only`
or `pinballctl stop --web-only` to control Gunicorn independently of the serial
bridge and Godot supervisor. The supervisor owns display autoplay.
For a systemd installation, use `pinballctl service start web`, `pinballctl service reload web`
or `pinballctl service stop web`. The `runtime` selector manages the bridge and Godot supervisor.

## Module interface layout

Use the shared module header for the page title and intro. Place page-wide
actions on the right and tabs directly below the header. Use the shared tab
and table styles in `core/static/css/interface.css` so spacing stays consistent
as actions wrap on smaller screens.

| Action | Appearance |
| --- | --- |
| Navigation, inspection and secondary actions | Neutral outline in the page header |
| Sync and device operations | Blue outline in the page header |
| Save and Add | Green outline in the page header |
| Destructive actions | Red outline in the page header and a filled danger button in confirmation dialogs |

Use Title Case for action labels and keep acronyms uppercase, as in
**Sync to ESP**, **Save Changes**, and **Add Row**. Pair action labels with their
leading Font Awesome icon. For icon-only controls, supply an accessible name
and a tooltip. Give JavaScript-rendered actions the same icon and label
markup through `pinballctlActions.setLabel`.

In a table section, put the title and actions in one centred
`table-section-header` row. The shared toolbar supplies the 12 px gap below
the entire row, keeping both sides aligned above the table. Put the primary
confirmation on the right in dialogs and drawers.

## Validation

Run the Python regression suite or the tests relevant to your change:

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m unittest discover -s tests -p 'test_bridge_connection.py'
```

Browser tests are the `tests/test_*_ui.cjs` scripts; run the affected script with
Node. Native firmware tests are in `tests/firmware/`. For example, the coil policy
core can be tested without connected hardware:

```sh
c++ -std=c++17 -Isrc/firmware/src tests/firmware/coil_safety_test.cpp -o /tmp/pinballctl-coil-safety-test
/tmp/pinballctl-coil-safety-test
```

The native policy test does not qualify physical switching timing, current or
thermal behaviour. Use [firmware regression checks](firmware-checks.md) when
validating on hardware. Keep arming, watchdogs, timeouts and fault handling intact.
All Pi/ESP commands use a four-byte big-endian length followed by UTF-8 JSON;
never introduce newline-delimited serial commands.

## Firmware and media builds

Use `utils/build-firmware.sh` for firmware builds so the application can discover
registered artifacts. Read its options before running it: the utility updates
firmware version/artifact files and can interact with local setup. Build outputs
and generated instance files are not a substitute for reviewing source changes.
See [Godot](godot-runtime.md) and [Backglass](backglass.md) for media-specific commands.

## Generated files and local work

- Website validation and local previews use temporary `build/website-*` workspaces that are removed afterwards. CI retains `build/site/` only until artifact upload, then removes it.
- `dist/firmware/` and release packages may be needed for device installation; do not clear all of `dist/` as a website cleanup.
- `build/`, Python bytecode and editor caches are generated output.
- `.local/` can contain recovery copies, reports and media backups. Review contents before deleting.
- `gunicorn.ctl` is a runtime socket; do not delete an active socket.
- Test-bench notes live in `media/website/docs/developer-notes/`; reviewed diagrams and illustrations live in `media/website/assets/docs/media/`. Preserve the current engineering sources in `media/website/design/test-bench/` separately from generated website output.

Update the affected website guides in the same change as application behaviour.
Use the [website build and checks](../developer-notes/website-and-search.md#build-output) before review.
