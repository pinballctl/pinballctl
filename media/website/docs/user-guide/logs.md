# Logs

Use **Logs** to inspect live and archived application, bridge, raw ESP and event logs. Open the **Events** tab to follow controller inputs, rule activity and updates from Scoring, Game Management and Ball Management.

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

### Choose and filter a log

Select **Web Error**, **Web Access**, **Bridge**, **ESP Raw** or **Events**. The browser remembers the last source you opened. The log file selector shows the **Current Log File** and any available archives for that source.

Use **Lines** to set how many recent entries appear from the current file, and **Keyword Filter** to narrow the entries in the viewer. On the **Events** tab, **Event category** narrows the view further. These controls affect what you see on screen. **Download** saves the selected log file.

### Follow or clear the view

Use **Tail** to follow new entries. While live updates are on, the button reads **Tailing**. Select it again to pause, or use **Refresh** to reload the selected log. While you select text in the viewer, display updates wait so you can copy it.

**Clear** empties the viewer. Use **Purge** only when you intend to permanently clear the current log file. Pinball CTL asks for confirmation before purging. **Clear**, **Purge** and the tailing control are hidden when you select an archive.

### JSON inspector

Select a log row or its **JSON** or **View** button to open the **Log Inspector**. It shows structured, syntax-highlighted JSON when the line contains readable JSON and the original text otherwise. Use **Close** or press **Esc** to return to the log.

### Examples

To investigate a bridge issue as it happens, open **Bridge**, enable **Tail**, and filter for `error`, `timeout` or the device ID. To review event activity, open **Events** and use the inspector to check the event name, source and other fields.

## Related Features

- [Dashboard](dashboard.md)
- [ESPLink](esplink.md)
- [Service Log](service-log.md)
