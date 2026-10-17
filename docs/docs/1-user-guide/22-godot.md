# Godot

Godot support lets you package animated scenes, menus, score displays, and custom UI into a `.pck` and run that content inside Pinball CTL.

This page covers the full workflow:

- building a Godot project that works well inside Pinball CTL
- wiring scene interactions to machine events
- sending custom events back out of the scene
- exporting the project as a `.pck`
- loading the pack into the Media module

## What Pinball CTL Expects

Pinball CTL treats a Godot pack as a reusable media asset.

The usual flow is:

1. Build and test the scene in a normal Godot project.
2. Export that project as a `.pck`.
3. Upload the `.pck` in `Media -> Library`.
4. Add a `Godot Scene` layer in `Media -> Scenes`.
5. Choose the `Godot Scene Pack`, `Entry Scene`, and `Render Mode`.
6. Add `Input Mapping` rows so cabinet events can drive the scene.

Godot content works best when it is authored as a self-contained scene with:

- normal Godot UI actions such as `ui_left`, `ui_right`, and `ui_accept`
- a clear root scene that can be used as the exported entry point
- optional helper methods for Pinball CTL runtime input
- optional custom event signals if the scene needs to notify Rules

## Recommended Scene Design

Pinball CTL can inject either:

- Godot actions such as `ui_left`
- keyboard keys such as `Left`, `Right`, `Enter`, or `Up`

The most robust pattern is:

- author your Godot scene against normal Godot input actions
- keep keyboard bindings in the Godot Input Map for local development
- let Pinball CTL trigger those same actions or keys at runtime

That keeps the project easy to test outside Pinball CTL.

## Basic Input Setup In Godot

The host runtime already provides these common actions:

- `ui_left`
- `ui_right`
- `ui_accept`

For a standalone Godot project, add the same bindings in `Project Settings -> Input Map`.

Typical menu bindings are:

- `ui_left` -> Left Arrow
- `ui_right` -> Right Arrow
- `ui_accept` -> Enter or Up Arrow

Here is the simplest standalone-friendly input handler:

```gdscript
func _unhandled_input(event: InputEvent) -> void:
	if not event.is_pressed():
		return
	if event is InputEventKey and event.is_echo():
		return

	if event.is_action_pressed("ui_left"):
		focus_left()
		accept_event()
	elif event.is_action_pressed("ui_right"):
		focus_right()
		accept_event()
	elif event.is_action_pressed("ui_accept"):
		activate_focused()
		accept_event()
```

This is the preferred pattern because the scene stays fully testable with a keyboard before it is ever exported.

## Optional Pinball CTL Runtime Hooks

Pinball CTL will also look for scene methods that can receive input directly.

These are optional, but useful:

```gdscript
func pinballctl_input_action(action: String) -> void:
	match String(action).strip_edges():
		"ui_left":
			focus_left()
		"ui_right":
			focus_right()
		"ui_accept":
			activate_focused()


func pinballctl_input_key(key_name: String, phase: String = "tap") -> void:
	if String(phase).strip_edges().to_lower() == "release":
		return

	match String(key_name).strip_edges().to_lower():
		"left", "arrowleft", "leftarrow":
			focus_left()
		"right", "arrowright", "rightarrow":
			focus_right()
		"up", "arrowup", "uparrow", "enter", "return", "kp_enter":
			activate_focused()
```

Use these when:

- you want a clear explicit bridge from Pinball CTL into the scene
- you want to support either action-based or key-based mappings
- you want to ignore `release` so a press/release pair does not fire twice

## Sending Events Back To Pinball CTL

If your scene should notify the rest of the machine when focus changes or a button is activated, emit custom signals from the scene.

Pinball CTL listens for:

- `pinballctl_focus_changed(mode_name, mode_index)`
- `pinballctl_custom_event(event_name, event_params)`

Example:

```gdscript
signal pinballctl_focus_changed(mode_name: String, mode_index: int)
signal pinballctl_custom_event(event_name: String, event_params: Dictionary)


func _emit_focus_event() -> void:
	var mode_name := "CLASSIC"
	var mode_index := 0
	pinballctl_focus_changed.emit(mode_name, mode_index)
	pinballctl_custom_event.emit("BACKGLASS_MENU_FOCUS_CHANGED", {})
	pinballctl_custom_event.emit("BACKGLASS_MENU_FOCUS_" + mode_name, {})


func activate_focused() -> void:
	var mode_name := "CLASSIC"
	pinballctl_custom_event.emit("BACKGLASS_MENU_SELECTED", {})
	pinballctl_custom_event.emit("BACKGLASS_MENU_SELECTED_" + mode_name, {})
```

### Important Custom Event Rule

At the moment, custom scene events should be treated as event names only.

For reliable rule matching:

- keep `event_params` empty: `{}`
- encode the useful detail into the event name itself

Good:

- `BACKGLASS_MENU_FOCUS_CHANGED`
- `BACKGLASS_MENU_FOCUS_CLASSIC`
- `BACKGLASS_MENU_SELECTED_CLASSIC`

Avoid relying on extra custom parameters for Rules matching.

## Example Reference Project

The sample project at [pinballctl-backglass](https://github.com/pinballctl/pinballctl-backglass) is the reference implementation for interactive Godot content.

Useful files:

- [scripts/main.gd](https://github.com/pinballctl/pinballctl-backglass/blob/main/scripts/main.gd)
- [scripts/mode_orb.gd](https://github.com/pinballctl/pinballctl-backglass/blob/main/scripts/mode_orb.gd)
- [README.md](https://github.com/pinballctl/pinballctl-backglass/blob/main/README.md)

That sample shows:

- keyboard-friendly Godot development
- Pinball CTL action and key input hooks
- focus and select events emitted back to Pinball CTL
- a simple reusable menu component

## Exporting As A `.pck`

Pinball CTL consumes exported Godot packs, not raw project folders.

### In The Godot Editor

1. Open your project in Godot.
2. Go to `Project -> Export`.
3. Create an export preset that supports pack export.
4. Choose `Export PCK/ZIP`.
5. Save the output as a `.pck`.

### From The Command Line

If you prefer CLI export, the typical pattern is:

```bash
godot --headless --path /path/to/project --export-pack "Linux/X11" MyScene.pck
```

Notes:

- the preset name must match one defined in your Godot project
- the output must be a `.pck`
- Pinball CTL reads the exported pack and discovers available entry scenes from it

## Uploading The Pack To Media

Open `Media -> Library` and upload the `.pck`.

After upload, Pinball CTL treats it as a `Godot Scene` asset and indexes the scenes inside the pack.

The library entry stores:

- the uploaded pack name
- the detected scene entries
- the default entry scene

## Adding A Godot Layer

In `Media -> Scenes`:

1. Create or open a scene.
2. Add a layer.
3. Set `Type` to `Godot Scene`.
4. Choose `Godot Scene Pack`.
5. Choose `Entry Scene`.
6. Choose `Render Mode`.

<img src="./media/screenshot-feature-media-scenes.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#media-tab-scenes"},{"action":"click","selector":"#media-tab-scenes","wait_for":"#media-pane-scenes.show.active"},{"action":"click","selector":"#media-scene-list [data-scene-id]","wait_for":"#media-scene-editor .media-editor-stack"}]}' alt="Media Scenes authoring view" style="width: 100%;height: auto;">

Render modes:

- `Layered`: the Godot content behaves like a normal layer inside the stack
- `Primary`: the Godot scene owns the whole runtime window for that scene

Use `Primary` for menus, full-screen score scenes, and other UI that should control the full display.

## Media Inspector Mapping

<img src="./media/screenshot-feature-godot-inspector.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"target":"#media-scene-layer-inspector [data-layer-card] .media-editor-stack","target_content":true,"target_padding":18,"before_capture_js":"document.body.classList.add(\"docs-capture\");","click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#media-tab-scenes"},{"action":"click","selector":"#media-tab-scenes","wait_for":"#media-pane-scenes.show.active"},{"action":"click","selector":"#media-scene-list [data-scene-id=\"scene_1c30b7d1\"]","wait_for":"#media-scene-editor .media-editor-stack"},{"action":"click","selector":"#media-layer-list [data-layer-item=\"0\"]","wait_for":"[data-godot-map-add]"}]}' alt="Godot layer inspector with input mapping" style="width: 100%;height: auto;">

The `Input Mapping` section sits directly below `Entry Scene` on a `Godot Scene` layer.

Each mapping row defines:

- `Trigger Type`
- the trigger details for that type
- `Resolved Event`
- `Input Kind`
- `Action` or `Key`
- `Phase`

### Trigger Types

The trigger side mirrors the Rules module structure:

- `Hardware`
- `System`
- `Custom`

#### Hardware

Choose:

- the hardware device
- the hardware gesture such as `CLICKED`

Pinball CTL resolves that into the canonical event name internally.

#### System

Choose:

- a system category
- a system event

#### Custom

Enter the event name directly.

## Mapping To Actions Or Keys

You can map a trigger to either:

- `Action`
- `Key`

### Action Mapping

Use this when your scene listens for Godot actions:

```text
Hardware -> Left Flipper -> CLICKED -> Action -> ui_left -> Clicked
Hardware -> Right Flipper -> CLICKED -> Action -> ui_right -> Clicked
Hardware -> Start Button -> CLICKED -> Action -> ui_accept -> Clicked
```

### Key Mapping

Use this when your scene listens for keys instead of actions.

When `Input Kind` is `Key`, the key field becomes a capture box:

- click the field
- press the key you want to send
- Pinball CTL stores the normalized key name

Examples:

```text
Hardware -> Left Flipper -> CLICKED -> Key -> Left -> Clicked
Hardware -> Right Flipper -> CLICKED -> Key -> Right -> Clicked
Hardware -> Start Button -> CLICKED -> Key -> Up -> Clicked
```

## Example Menu Scene

The backglass sample uses:

- left flipper -> `Left`
- right flipper -> `Right`
- start / launch -> `Up`

That allows the same scene to work:

- as a normal Godot project on a keyboard
- as a Pinball CTL-driven runtime scene

## Testing The Pack

A good validation sequence is:

1. Run the scene in Godot with a keyboard.
2. Export the `.pck`.
3. Upload it to `Media -> Library`.
4. Add it to a `Godot Scene` layer.
5. Launch it from `Media -> Runtime`.
6. Test cabinet input through the `Input Mapping` section.
7. Check the event log if the scene emits custom events back out.

## Troubleshooting

### The Scene Looks Wrong In The Scene Editor Preview

The editor preview is not a full embedded Godot renderer.

Use the real runtime for final validation:

- `Media -> Runtime`
- or a launched window from the scene preview/runtime controls

### The Wrong Entry Scene Appears

If the selected entry scene does not belong to the chosen pack, Pinball CTL resets it to that pack’s own entry list. Re-select the pack and then choose the entry scene again.

### Inputs Do Not Trigger

Check these in order:

1. The layer `Type` is `Godot Scene`.
2. The correct `Godot Scene Pack` is selected.
3. The correct `Entry Scene` is selected.
4. The mapping row was saved.
5. The hardware trigger matches the real event type, usually `CLICKED`.
6. The scene actually listens for the mapped action or key.

### Custom Events Do Not Appear In The Event Log

Check:

1. the scene emits `pinballctl_custom_event`
2. the event name is non-empty
3. the parameters are empty: `{}`
4. the running `.pck` was re-exported after the latest scene changes

## Summary

To build a Godot pack that works well in Pinball CTL:

- keep the scene keyboard-friendly in plain Godot
- prefer `ui_*` actions for scene logic
- optionally support `pinballctl_input_action(...)` and `pinballctl_input_key(...)`
- export the project as a `.pck`
- upload the pack in `Media`
- add a `Godot Scene` layer
- configure `Input Mapping`
- emit custom event names back to Pinball CTL when the scene needs to drive Rules
