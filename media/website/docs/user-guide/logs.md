# Logs

Use **Logs** to inspect live and archived application, bridge, raw ESP and event logs. Open the **Events** tab to follow controller inputs, rule activity and updates from Scoring, Game Management and Ball Management.

## At a glance

**Sources**. Switch between application, bridge, raw ESP, and event logs.

**Event category**. Narrow Events without changing the underlying file.

**JSON / View**. Inspect the details of one line.

**Tail / Refresh / Download**. Follow new lines, reload the view, or save the selected file.

## Before you start

Have access to the running application and the approximate time/source of the issue. Keep output power off when reproducing an input or rule problem.

## Find and inspect an event

Open the **Events** tab in **Logs** to see what the controller and application reported. For a physical test, use a connected ESP and a saved hardware mapping, and keep coils disconnected. Operate one mapped input and open its record in the **JSON** inspector. The **name** identifies the event used by Rules or Scoring, the **source** identifies the input or software component that reported it, and **parameters** include details such as event type or value. Use the source UID to tell apart inputs that produce the same event.

Use **Event category** to narrow the view to **API**, **Rules**, **Bridge**, **Scoring**, **Game Management** or **Ball Management**. Manual ball resets appear under **Ball Management**. Set the line count and use **Keyword Filter** to look for a device UID, event name or error. For an older occurrence, select the archived file and keep the timestamp and error for comparison before clearing or purging the log.

<img src="./media/screenshot-feature-logs.webp" data-source='{"url":"/login","next_url":"/logs/?target=events&manager=ball","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Logs feature overview" style="width: 100%;height: auto;">

To trace an input into a rule, open **Rules → Add Rule → Triggers** and select the source and event shown in the log. Confirm the source UID when the input has a friendly name. For a controlled test, add the custom-event action from [Quick Start](getting-started.md#quick-start), then save and check sync status. Operate the input again and look for both the input and the custom event in **Logs**.

[Playfield Live View](layout.md#live-view) can also generate test events. Keep outputs disabled because simulated events can run real rules and actions. Use a distinct test event name and avoid rules that emit their own trigger. Offline tests exercise the host path. Check wiring, ESP timing, arming and delivery on the connected machine with the appropriate safe test setup.

## Check the result

Filters apply to the visible buffer; an empty filtered view does not prove an event never occurred. Turn filtering off and increase the window if needed.

**Safety:** Logs can contain project details or credentials supplied in user text. Review/redact before sharing, and do not rapidly fire outputs to generate diagnostic traffic.

## Troubleshooting

For a silent input, first verify the live ESP connection and check the **Events** tab with filters cleared. Verify the pin identity, polarity, saved mapping and hardware sync. If the input appears but the rule result is missing, check the trigger source, enabled state, conditions and saved rule. Use route and coverage diagnostics to check registration, then look for the result of the rule in the log.

For sync and transport errors, use **Bridge**. For application errors, use **Web Error**. If logs are unavailable, check the locations reported by `pinballctl status` and the service account’s permissions.

## Related guides

See [Hardware](hardware.md), [Rules](rules.md), [ESPLink](esplink.md), [Performance](performance.md) and [Troubleshooting](troubleshooting.md). For the runtime path, see [Event Dispatch Internals](../technical-notes/event-manager.md) and [Bridge Event Flow](../technical-notes/bridge-event-flow.md).

## Log controls and JSON inspector

### What This Feature Does

It provides live and historical log access in-browser for operational checks and troubleshooting.

### Control Bar Reference

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

### Viewport Behaviour

- renders log lines as interactive rows
- auto-tail updates while enabled
- supports large buffer management

Rows with parseable JSON show JSON-specific affordance.

### JSON Inspector

Click `JSON` or row to open inspector modal.

Modal includes:

- structured syntax-highlighted JSON view
- fallback raw line view if not JSON
- close actions and `Esc` support

### Tailing and Selection Behaviour

When text selection is active in viewport:

- render updates are deferred to avoid disrupting text copy/select

Tail can be toggled off for static analysis.

### Typical Workflow

1. Select source.
2. Set line window.
3. Apply keyword filter.
4. Inspect JSON rows when needed.
5. Use purge only for deliberate log reset.

### Practical Examples

### Bridge troubleshooting

- source = Bridge
- tailing on
- filter for `error`, `timeout`, or device ID

### Event audit

- source = Events
- inspect JSON payloads for event names/fields

## Related Features

- [Dashboard](dashboard.md)
- [ESPLink](esplink.md)
- [Service Log](service-log.md)
