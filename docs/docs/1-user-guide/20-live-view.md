# Live View

Live View is the runtime testing page for the current table state.

It combines:

- a live stage preview of the playfield
- manual event firing tools
- media scene launch controls
- lighting scene preview controls

It is designed for validation and testing rather than authoring.

<img src="./media/screenshot-feature-live-view.webp" data-source='{"url":"/login","next_url":"/liveview","dark_mode":true,"settle_ms":3000,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Live View feature overview" style="width: 100%;height: auto;">

## Purpose

Use Live View to:

- watch incoming events affect the playfield stage
- manually trigger system events for testing
- launch media scenes without leaving the page
- preview lighting scenes on the live stage
- validate Rules, scoring, lighting, and media behavior together

Live View does not replace the authoring modules such as Rules, Lighting, Media, or Playfield. It is the runtime test bench for the configuration you already built elsewhere.

## Page Layout

Live View has a single tab:

1. `Live View`

The page is split into two columns:

- left: the live playfield stage
- right: runtime control cards

The right-hand column currently includes:

- `System Events`
- `Scene Trigger`
- `Lighting`

## Stage Preview

The stage is a live visual representation of the table.

It shows:

- playfield components
- switch and output feedback
- animated table reactions such as flippers and plungers
- lighting overlay preview for active lighting scenes

The stage updates from the event stream, so it reflects both real hardware events and test events triggered from Live View itself.

## Runtime Interaction

Live View supports several ways to test behavior.

### Keyboard Input

Keyboard shortcuts mapped in the Playfield module can trigger the matching hardware gestures and events.

This is useful when:

- hardware is not connected
- you want to test quickly from a laptop
- you want to validate a mapping before trying it on the cabinet

### Mouse Input On The Stage

You can also interact directly with components on the playfield stage.

Supported behavior includes:

- right-clicking a component to open available trigger actions
- firing configured trigger paths immediately from that menu
- using combined options such as `PRESSED + RELEASED` where appropriate

This is especially useful for validating Rules and scene input mappings without needing the real hardware path.

## System Events Card

The `System Events` card lets you manually trigger system events from the current event registry.

Use it to:

- test Rules that depend on system-level events
- validate event-driven media or lighting behavior
- confirm downstream integrations are reacting correctly

This card is driven from the registered system event list, so it follows the same event catalogue used elsewhere in the app.

## Scene Trigger Card

The `Scene Trigger` card launches media scenes from Live View using the same runtime path as the Media Runtime tab.

It includes:

- `Scene`
- `Display`
- `Window mode`
- `Play Scene`
- `Stop Scene`

### Scene

Choose from the available Media scenes.

### Display

Choose which configured Media display should receive the scene.

### Window Mode

Current options are:

- `Windowed`
- `Fullscreen`

`Windowed` is the default option in Live View.

### Play And Stop

`Play Scene` launches the selected scene on the selected display.

`Stop Scene` stops the currently selected display runtime.

This is useful when:

- testing scene launch behavior quickly
- comparing displays
- checking a Godot scene without switching to the Media module

## Lighting Card

The `Lighting` card allows you to play lighting scenes directly on the Live View stage.

It includes:

- `Scene`
- `Play Scene`
- `Stop Scene`

### What It Does

When you press `Play Scene`:

- the lighting scene starts in the Live View overlay immediately
- if the bridge is online, the same lighting preview is also sent to hardware
- if the bridge is offline, the scene still plays locally in Live View only

When you press `Stop Scene`:

- the local Live View lighting preview stops immediately
- hardware preview is also stopped when available

This makes the card useful even when the machine hardware is disconnected.

## Event And Visual Behavior

Live View listens to the application event stream and updates the stage in real time.

Examples include:

- button highlight and pulse behavior
- plunger movement
- flipper movement and hold state
- output visuals for supported devices
- lighting scene playback
- lighting pixel actions and blink timing

Because the stage follows the same event flow as the rest of the app, it is useful for diagnosing whether a problem is:

- the trigger
- the rule
- the runtime action
- or the final visual output

## Lighting Preview Behavior

Lighting in Live View is not just a static editor preview.

It responds to:

- lighting scenes started from the `Lighting` card
- runtime lighting actions triggered by Rules
- pixel-level lighting actions such as blink and timed expiry

This means Live View can be used to validate both:

- authored lighting scenes
- rule-driven lighting effects

## Working Without Hardware

Live View remains useful when the bridge or cabinet hardware is offline.

You can still:

- trigger keyboard-driven playfield events
- fire system events manually
- launch media scenes
- preview lighting scenes locally on the stage

This makes it a practical development and testing tool on a desk or laptop, not just on the full machine.

## Typical Workflow

1. Open `Live View`.
2. Trigger input from hardware, keyboard, or the stage context menu.
3. watch the stage for immediate table feedback.
4. Use `System Events` to test event-driven rules manually.
5. Use `Scene Trigger` to launch a media scene on a chosen display.
6. Use `Lighting` to preview a lighting scene on the stage.
7. Confirm the expected runtime behavior before moving back to the authoring modules.

## When To Use Live View Vs Other Modules

Use `Live View` when you want to test the current runtime behavior.

Use `Playfield` when you want to author the table layout.

Use `Rules` when you want to define trigger and action behavior.

Use `Lighting` when you want to author fixtures and lighting scenes.

Use `Media` when you want to build scenes and manage runtime displays.

## Related Features

- [Playfield](9-layout.md)
- [Rules](7.1-rules.md)
- [Lighting](8-lighting.md)
- [Media](18-media.md)
- [Scoring](10-scoring.md)
- [Logs](14-logs.md)
