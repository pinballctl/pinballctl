# Events

Events tell the rest of the system what just happened. An event name describes the occurrence; its source identifies where it came from, and parameters carry details. Rules listen for these events and decide what to do next.

## Before you start

Have a saved hardware mapping and a running application. Use a connected ESP for physical input tests; keep coils disconnected. Events is an API/runtime service in this baseline, not a separate visual Event Manager page. Observe events through Logs and Live View, and select them in the Rules editor.

## Follow one event

1. Open **Logs** and select the event log. Operate one mapped input once. **Expected:** a record for the real input, including its event name and source.
2. Expand the record in the JSON inspector where available. Record the name, source UID and useful parameters. **Expected:** you can distinguish that input from another device producing the same kind of event.
3. Open **Rules → Add Rule → Triggers** and select the corresponding source and event. **Expected:** the rule targets the observed device rather than a guessed label.
4. For a safe test, add the custom-event action from [Quick Start](0-quick-start.md), save and review sync status. Operate the input again. **Expected:** the log shows the input and your distinct derived event.

<img src="./media/screenshot-feature-logs.webp" alt="Logs viewer with event records and controls for inspecting runtime messages" style="width:100%;height:auto;">

**Screen guide:** use the log selector to choose events, inspect the record's name/source, then match those values in Rules. A friendly device name helps authoring but does not replace source identity.

## Helpful hints and safety

Change one input or rule at a time. A simulated event can exercise real rules and actions; it is not automatically a harmless preview. Keep outputs disabled and avoid existing gameplay event names for tests. Never create a rule that repeatedly emits its own trigger.

Live View can generate configured tests; connected and offline event paths differ. Offline results do not prove physical wiring, ESP timing, output arming or delivery to hardware.

## If an event is missing

Check the live ESP/bridge connection, pin identity, polarity, mapping save and hardware sync first. If the input event exists but its rule result does not, check the trigger source, enabled state, conditions and saved rule. Route/coverage diagnostics describe registration and cannot alone prove that a gameplay action executed.

## Continue your build

Read [Hardware](7-hardware.md), [Rules](7.1-rules.md), [Live View](20-live-view.md) or [Troubleshooting](26-troubleshooting.md). Developers can inspect [Event Dispatch Internals](../2-technical-notes/event-manager.md) and [Bridge Event Flow](../2-technical-notes/3-bridge-event-flow.md).
