# Logs

Logs is the feature for viewing runtime output from web, bridge, ESP, and event streams.

<img src="./media/screenshot-feature-logs.webp" data-source='{"url":"/login","next_url":"/logs","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Logs feature overview" style="width: 100%;height: auto;">

## What This Feature Does

It provides live and historical log access in-browser for operational checks and troubleshooting.

## Control Bar Reference

### Source

Available sources:

- Web Error
- Web Access
- Bridge
- ESP Raw
- Events

Source preference is remembered in local storage.

### Lines

- numeric line count for current-window view
- min/step controlled input

### Filter

- keyword filter applied client-side to visible buffer

### Log File

- `Current` and archive entries (when available)

Archive mode hides controls that are not applicable to archived logs.

### Action buttons

- `Refresh`
- `Clear`
- `Purge`
- `Tailing` toggle

`Purge` permanently clears the current log file (with confirmation).

## Viewport Behaviour

- renders log lines as interactive rows
- auto-tail updates while enabled
- supports large buffer management

Rows with parseable JSON show JSON-specific affordance.

## JSON Inspector

Click `JSON` or row to open inspector modal.

Modal includes:

- structured syntax-highlighted JSON view
- fallback raw line view if not JSON
- close actions and `Esc` support

## Tailing and Selection Behaviour

When text selection is active in viewport:

- render updates are deferred to avoid disrupting text copy/select

Tail can be toggled off for static analysis.

## Typical Workflow

1. Select source.
2. Set line window.
3. Apply keyword filter.
4. Inspect JSON rows when needed.
5. Use purge only for deliberate log reset.

## Practical Examples

### Bridge troubleshooting

- source = Bridge
- tailing on
- filter for `error`, `timeout`, or device ID

### Event audit

- source = Events
- inspect JSON payloads for event names/fields

## Related Features

- [Dashboard](5-dashboard.md)
- [ESPLink](11-esplink.md)
- [Service Log](13-service-log.md)
