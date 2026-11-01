# Logs

Find out what happened and what to check next. Follow a single event or error through the most relevant log instead of treating every message as a fault.

## Before you start

Have access to the running application and the approximate time/source of the issue. Keep output power off when reproducing an input or rule problem.

## Try it step by step

1. Choose the appropriate **Source**: Events for input/rule investigation, Bridge for transport, or Web Error for application errors. **Expected:** the view matches the component being investigated.

2. Set an appropriate line count and filter for a device UID, event name or error text. **Expected:** the relevant record remains visible without losing surrounding context.

3. Open the JSON inspector for a structured event. Compare name/source/parameters with the Rules trigger. **Expected:** you can explain whether the input arrived and whether a derived event followed.

4. If examining an older occurrence, select the correct archived file. Preserve the timestamp and error before clearing/purging anything. **Expected:** evidence can be compared after a controlled fix.

<img src="./media/screenshot-feature-logs.webp" data-source='{"url":"/login","next_url":"/logs","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Logs feature overview" style="width: 100%;height: auto;">

**Screen guide:** 1. Source chooses the log. 2. Filter narrows the visible records. 3. Structured details identify event/source; preserve timing context.

## Helpful checks

Filters apply to the visible buffer; an empty filtered view does not prove an event never occurred. Turn filtering off and increase the window if needed.

**Safety:** Logs can contain project details or credentials supplied in user text. Review/redact before sharing, and do not rapidly fire outputs to generate diagnostic traffic.

## If the result is different

For a silent input, first verify the live connection and unfiltered Events source. For sync errors, read the matching Bridge log and compatibility result. If logs are unavailable, inspect the locations shown by pinballctl status and service permissions.

## Continue your build

Next: [Events](27-events.md), [ESPLink](11-esplink.md), [Performance](23-performance.md), [Troubleshooting](26-troubleshooting.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

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
