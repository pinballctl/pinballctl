# Build a Godot backglass

Build a backglass from a blank Godot 4.6 project. You’ll make a menu with a **View scores** button, then a scoreboard that shows the active player’s score, player number, ball number and credits. You can test the menu on a keyboard before connecting it to PinballCTL.

## 1. Create a project and a scene

1. In Godot’s Project Manager, choose **Create**. Name the project **Pinball Backglass**, choose an empty folder and select the **Compatibility** renderer. Open the project.
2. Choose **User Interface** in the **Scene** panel to create a root **Control**. Rename it **Backglass**, then save the scene as `res://backglass.tscn`. Godot uses `res://` for files inside the project folder.
3. In **Project → Project Settings → Display → Window**, set **Viewport Width** to **1280** and **Viewport Height** to **720**. Set **Stretch → Mode** to **canvas_items** so the layout can scale to another window size.
4. Select **Backglass** in the Scene tree, choose **Add Child Node** and add a **ColorRect** named **Background**. In the 2D toolbar, open **Layout → Full Rect** to fill the scene. In the Inspector, set **Color** to a dark colour such as `#101823`. Keep Background first in the tree so the controls draw on top.

## 2. Build the menu and scoreboard

1. Add a **CenterContainer** under **Backglass**, name it **Menu**, and use **Layout → Full Rect**. Add a **VBoxContainer** under Menu and name it **Items**. The center container centres the box, and the vertical box stacks its children in order.
2. Under Menu’s **Items**, add a **Label** named **Title** with **Text** set to `Pinball Backglass`. Add a **Button** named **ViewScores** and set its **Text** to `View scores`. The node name and its visible text are separate fields.
3. Add a second **CenterContainer** directly under **Backglass**, name it **Scoreboard**, and set it to **Full Rect**. Add a **VBoxContainer** named **Items** inside it. Add the following children to that second Items box.

| Node type | Node name | Inspector → Text |
| --- | --- | --- |
| Label | `Title` | `Scoreboard` |
| Label | `Score` | `Score {{SCORE}}` |
| Label | `Turn` | `Player {{PLAYER}}   Ball {{BALL}}` |
| Label | `Credits` | `Credits {{CREDIT}}` |
| Button | `Back` | `Back to menu` |

![Godot Inspector showing Score {{SCORE}} in the Label’s Text field](./media/godot-scoreboard-inspector.webp)

4. For each box, set **Theme Overrides → Constants → Separation** to **16**. For the title labels, set **Theme Overrides → Font Sizes → Font Size** to **64**. Use **36** for the scoreboard values and **28** for the buttons. Set each label’s **Horizontal Alignment** to **Center**.
5. Check the Scene tree. Indentation matters because the script in the next step looks up the buttons by their full path.

```text
Backglass (Control)
├── Background (ColorRect)
├── Menu (CenterContainer)
│   └── Items (VBoxContainer)
│       ├── Title (Label)
│       └── ViewScores (Button)
└── Scoreboard (CenterContainer)
    └── Items (VBoxContainer)
        ├── Title (Label)
        ├── Score (Label)
        ├── Turn (Label)
        ├── Credits (Label)
        └── Back (Button)
```

## 3. Connect the menu buttons

Select **Backglass** and click **Attach Script** above the Scene tree. Choose **GDScript** and save it as `res://backglass.gd`. Replace the script contents with the following, then save the script and the scene.

```gdscript
extends Control

@onready var menu: CenterContainer = $Menu
@onready var scoreboard: CenterContainer = $Scoreboard


func _ready() -> void:
    $Menu/Items/ViewScores.pressed.connect(_show_scoreboard)
    $Scoreboard/Items/Back.pressed.connect(_show_menu)
    _show_menu()


func _show_menu() -> void:
    scoreboard.hide()
    menu.show()


func _show_scoreboard() -> void:
    menu.hide()
    scoreboard.show()


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_accept"):
        pinballctl_input_action("ui_accept")
        accept_event()
    elif event.is_action_pressed("ui_cancel"):
        pinballctl_input_action("ui_cancel")
        accept_event()


func pinballctl_input_action(action: String) -> void:
    match action:
        "ui_accept":
            if menu.visible:
                _show_scoreboard()
            else:
                _show_menu()
        "ui_cancel":
            _show_menu()
```

Click **Run Current Scene** or press **F6**. Click **View scores** and **Back to menu** to test both buttons. With the game window focused, try **Enter** to switch screens and **Esc** to return to the menu. If the script reports a missing node, compare the node names and indentation with the tree above.

![The tutorial’s backglass menu running in Godot with its View scores button](./media/godot-tutorial-menu.webp)

The scoreboard shows literal placeholders in standalone Godot. PinballCTL supplies the live values after it loads the exported scene. The labels should keep their placeholder text in the editor.

## 4. Export and load the backglass

PinballCTL needs a Godot executable on the machine that runs the display. Check **Media → Runtime** for **Godot binary**. If it reports **missing**, set the executable path under **Media → Settings → Godot Binary**.

1. In Godot, choose **Project → Export → Add** and select **Linux** for a Pi setup. If the export window requests templates, install the matching version through **Editor → Manage Export Templates**. With the preset selected, choose **Export PCK/ZIP** and save `Backglass.pck` outside the project folder. [Godot export guide](https://docs.godotengine.org/en/4.6/tutorials/export/exporting_projects.html)
2. In PinballCTL, open **Media → Library** and upload `Backglass.pck`. Go to **Scenes → Add Scene**, name it **Tutorial Backglass**, and select its target display.
3. Add a layer with **Type** set to **Godot Scene**. Choose the uploaded pack, select `res://backglass.tscn` as the **Entry Scene**, and set **Render Mode** to **Primary** so the backglass fills the runtime window.
4. In that layer’s **Input Mapping**, add your cabinet Select input. Use **Hardware** as the trigger type and choose its mapped source and press event. Set **Input Kind** to **Action**, **Action** to `ui_accept`, and **Phase** to **Tap**. This opens the scoreboard from the menu and returns from the scoreboard. For a separate Back input, add another mapping to `ui_cancel`. Save the Media scene.
5. In **Media → Runtime**, choose **Launch**, select the display and **Tutorial Backglass**, and choose **Launch / Play**. Use **Windowed** for a desktop test. Click **View scores** on the running display or use the mapped Select input. Keep coil power disconnected during cabinet input tests.

## 5. Check live values

For a desktop check, open the scoreboard, then reopen **Media → Runtime → Launch**. Choose the same display, enter `score` in **Token** and `00001234` in **Value**, then choose **Update Token**. The score label should change. Try `player`, `ball` and `credit` the same way.

To check that gameplay supplies the values, configure your launch and drain sensors in [Ball Management](27-ball-management.md), then follow these steps.

1. In [Game Management](26-game-management.md), start a test game and add Player 2 if your joining policy allows it.
2. With the scoreboard visible, simulate a launch from Game Management. Trigger a configured [Scoring](10-scoring.md) award and check that Player 1’s score changes on the display.
3. Simulate a drain once the ball-save window has expired. The scoreboard should show the next player and their score. Continue through the players to see the logical ball number change. Add a test credit from **Game Management → Credits** and check the credit label.

![The tutorial scoreboard rendered by PinballCTL showing a sample score, Player 2, Ball 3 and 4 credits](./media/godot-tutorial-scoreboard.webp)

The screenshot uses sample values. If the menu opens but the scoreboard still shows braces, check that the pack is running in PinballCTL and that the Label text uses `{{SCORE}}`, `{{PLAYER}}`, `{{BALL}}` and `{{CREDIT}}` exactly.

## Integration reference

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

The sample project at [the in-repository backglass project](https://github.com/pinballctl/pinballctl/tree/main/backglass) is the reference implementation for interactive Godot content.

Useful files:

- [scripts/main.gd](https://github.com/pinballctl/pinballctl/blob/main/backglass/scripts/main.gd)
- [scripts/mode_orb.gd](https://github.com/pinballctl/pinballctl/blob/main/backglass/scripts/mode_orb.gd)
- [README.md](https://github.com/pinballctl/pinballctl/blob/main/backglass/README.md)

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
godot --headless --path /path/to/project --export-pack "Linux" MyScene.pck
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



Render modes:

- `Layered`: the Godot content behaves like a normal layer inside the stack
- `Primary`: the Godot scene owns the whole runtime window for that scene

Use `Primary` for menus, full-screen score scenes, and other UI that should control the full display.

## Layer Settings Input Mapping

<img src="./media/screenshot-feature-godot-inspector.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1100,"target_padding":18,"before_capture_js":"document.body.classList.add(\"docs-capture\");","click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#media-tab-scenes"},{"action":"click","selector":"#media-tab-scenes","wait_for":"#media-pane-scenes.show.active"},{"action":"click","selector":"[data-bs-target=\"#media-scene-library\"]","wait_for":"#media-scene-library.show"},{"action":"click","selector":"#media-scene-list [data-scene-id=\"scene_1c30b7d1\"]","wait_for":"#media-layer-list"},{"action":"click","selector":"#media-layer-list [data-layer-item=\"0\"] [data-layer-settings]","wait_for":"[data-godot-map-add]"}],"full_page":false}' alt="Godot layer inspector with input mapping" style="width: 100%;height: auto;">

Open the sliders settings for a `Godot Scene` layer. The `Input Mapping` section sits directly below `Entry Scene` in the right-side panel.

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

## Included Hyrule sample

Open the included project for a more complete backglass with menus, animation and a scripted score display.

![The Hyrule sample entry scene open in Godot](./media/godot-backglass-editor.webp)

![The Hyrule sample running in Godot’s preview theatre](./media/hyrule-backglass-preview.webp)

The repository's `backglass/project.godot` opens an Ocarina of Time-inspired
presentation with generated landscapes, a six-destination quest map, animated
awards, original synthesized audio and local high-score entry. The earlier
carousel example remains available at `backglass/scenes/main.tscn`.

Run `godot --path backglass -- --preview` from the repository root to open the
preview gallery. Left/Right selects a scene; Space (Select) plays it. During playback,
P pauses, R replays, A toggles automatic cycling and Select returns to the
gallery. F1 leaves preview. Preview initials use Left/Right to choose letters and
Select to confirm; demonstration scores are never saved or sent to game rules.

Attract is a 44-second film with seven edited shots, a generated Master Sword
close-up, camera movement, crossfades, mist and foreground particles, a Triforce
assembly and title reveal. An original synthesized score follows the edits.
Select opens the menu immediately from every shot. The closing chronicles use
local scores, then fade back to the opening. Reduced motion keeps the images
stationary and removes moving effects while preserving the story and timing.

![Cinematic attract: the Master Sword](./media/hyrule-backglass-attract.webp)

The twenty sequences cover attract, gameplay, skill shot and its outcomes,
bonus, multiball, jackpot, super jackpot, ball saved, extra ball, quest complete,
wizard mode, victory, ball lost, tilt warning, tilt, game over, initials and
records. Menus include instructions, sound volume and reduced-motion settings.
The animations run inside Godot rather than requiring prerecorded video clips.
Bonus spins into a fast tally and exits in three seconds. Quick notifications
use distinct zoom, sweep, pop and stamp animations lasting 1.1–2.2 seconds;
Multiball and major story moments keep their longer cinematic timing. Reduced
motion disables these spins, sweeps and impact flashes. Preview lets quick
sequences finish back on the gameplay display; press R to replay them.

![Fast spinning bonus tally](./media/hyrule-backglass-bonus.webp)

Export the project as a `.pck`, upload it through Media and choose
`res://zelda/main.tscn` as the entry scene. Map flippers to `ui_left`/`ui_right`,
Select to `ui_accept`. Back is a selectable menu option. Selecting a destination emits
`BACKGLASS_START_REQUESTED` with `quest` and `quest_name`; your rules must handle
that request. The backglass waits for controller state and does not start coils,
change scoring or implement the suggested Zelda quests itself.

### Supply controller state

Imported scenes can optionally implement `pinballctl_text_values(values)` to
receive a copy of the current host text values, both when applied and on updates.
Existing token-label substitution is unchanged. Hyrule reads a JSON string from
`BACKGLASS_STATE`, passed using the existing runtime `UPDATE_TEXT` command:

```json
{"cmd":"UPDATE_TEXT","text":{"key":"BACKGLASS_STATE","value":"{\"screen\":\"bonus\",\"bonus\":126000,\"multiplier\":3,\"rupees\":42,\"event_id\":\"bonus-ball-2\"}"}}
```

Supported state fields are `screen`, `score`, `player`, `ball`, `quest` (0–5),
`progress` (three objective markers), `multiplier`, `rupees`, `bonus`, `award`,
`multiball` (boolean) and `event_id`. Send a new event ID to replay the same award;
repeated IDs do not restart it. Omit `screen` for score-only changes. A controller
update interrupts preview. These are media runtime messages; ESP framing and
hardware safety are unaffected.

Scene-only triggers can use actions such as `backglass_bonus`,
`backglass_multiball` and `backglass_game_over`, after setting the relevant score
or award amount. Bonus animation never changes the controller score. Transient
sequences return to gameplay; tilt waits for a new state. Game over offers
initials for a qualifying local score. `BACKGLASS_INITIALS_SUBMITTED` carries
`initials` and `score` back to the controller.

Settings and the top five records are saved in the Godot user's
`hyrule_backglass_v1.json`; these are display-local records. In multiplayer games,
the controller should explicitly request initials for each qualifying player.
The presentation letterboxes non-16:9 displays and uses Compatibility rendering;
validate frame rate and input mapping on the target Pi before cabinet use.

See [the backglass README](https://github.com/pinballctl/pinballctl/blob/main/backglass/README.md)
for every screen ID, controls, state contract, export and validation commands.

### Installing all Hyrule scenes locally

Run `.venv/bin/python backglass/utils/sync_application.py` from the repository to build and install all 25 entries, including the cinematic attract, gameplay events, menus and preview theatre. Repeat after every source or media update to keep the application pack current. Scene IDs remain stable. The sync stops application runtimes to clear cached resources; launch a scene again from Media.

For a clean replacement, add `--replace-existing`. Existing media and configuration are backed up in `.local/media-backups/` before the old library and scenes are cleared. Fonts and display settings are retained. Normal sync preserves unrelated library entries. The installed cabinet mappings use the configured left/right flipper buttons and Launch Button as Select. Enter/Escape are disabled in Hyrule; desktop testing uses arrows and Space. The quest map and preview gallery include Back options.
