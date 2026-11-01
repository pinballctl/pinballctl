# Media

Build what appears on your machine displays. Start with one saved scene and one layer, then add animation, runtime values and event-driven playback.

## Before you start

Have a supported image/video/font or scene asset and an appropriate host display environment. Live output needs the configured Godot runtime; browser preview alone does not verify it.

## Try it step by step

1. Upload the needed assets in **Library** or **Fonts**. **Expected:** the files are listed and available to the layer selectors.

2. In **Scenes**, choose **Add Scene**, set its name/target display and add a simple Text or Image layer. **Expected:** the layer appears in the composition and can be selected.

3. Edit the selected layer through its sliders panel. Check order, size, position and opacity. **Expected:** the composition matches the intended display layout.

4. Preview, then **Save Changes**. Check the target in **Displays**, runtime executable/configuration in **Settings**, and status in **Runtime** before live playback. **Expected:** the saved scene reaches the intended real display, or a specific runtime error explains why not.

5. Add a Media **Play Scene** action to a controlled test rule. Trigger it once and verify stop/interrupt/queue behaviour. **Expected:** the correct saved scene runs, without an accidental endless loop or blocked queue.

<img src="./media/screenshot-feature-media-scenes.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#media-tab-scenes"},{"action":"click","selector":"#media-tab-scenes","wait_for":"#media-pane-scenes.show.active"},{"action":"click","selector":"[data-bs-target=\"#media-scene-library\"]","wait_for":"#media-scene-library.show"},{"action":"click","selector":"#media-scene-list [data-scene-id]","wait_for":"#media-layer-list"}]}' alt="Media Scenes tab" style="width: 100%;height: auto;">

**Screen guide:** 1. Browse Scenes selects the saved composition. 2. The preview/layer list edits its content. 3. Scene and layer sliders open different settings panels.

## Helpful checks

Separate scene settings (display/playback policy) from layer settings (content/geometry). Start with a local image before diagnosing video conversion or custom packs.

**Safety:** Media packs can execute custom Godot code. Use trusted assets and keep output actions isolated while testing scene input mappings or events sent back to Rules.

## If the result is different

If browser preview works but the display is blank, check Godot process/runtime logs, display selection, saved scene target and host session access. If a layer is missing, check asset reference, order/opacity and entry scene for packs.

## Continue your build

Next: [Godot](22-godot.md), [Audio](17-audio.md), [Rules](7.1-rules.md), [Troubleshooting](26-troubleshooting.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## Media Tabs

Media is split into six tabs:

1. `Scenes`
2. `Library`
3. `Fonts`
4. `Displays`
5. `Settings`
6. `Runtime`

## Scenes



The `Scenes` tab is the main authoring workspace.

Use `Browse Scenes` beside `Save Changes` to choose a scene, then compose it on the preview. A compact layer list sits to the right of the preview on desktop and below it on smaller screens; click a layer to highlight it on the preview and use its sliders icon to edit it in a right-side panel. The sliders icon beside a scene in `Browse Scenes` opens a right-side panel for display targets and playback behaviour. Changes remain in your draft until you select `Save Changes`.

### Scene Browser

Use `Browse Scenes` to switch scenes. The single-column browser shows each scene’s displays and layer summary, with remove and settings icons on the right. Removing a scene asks for confirmation and stays in your draft until saved. Choosing a scene closes the panel and returns to the preview. Use `Add Scene` to create a scene and open its settings.

You can:

- add a new scene
- switch between existing scenes
- see which display a scene is aimed at
- close the browser to return to the composition

### Scene Preview

The preview lets you:

- see the current scene on a scaled stage
- drag and resize layers directly on the stage
- play and stop the preview
- scrub through video content
- open the scene in a Godot window or fullscreen for live testing

### Scene Settings

The `Scene Settings` panel controls how the whole scene behaves. Close the panel to return to the preview without losing draft changes.

This includes:

- scene name
- target displays
- playback settings such as priority, loop, and audio
- scene policies such as interrupt and duplicate handling
- queue settings
- audio behaviour while the scene is active

### Layers

The `Layers` column beside the preview is your scene stack (below the preview on smaller screens). Long lists scroll independently, keeping the preview visible.

You can:

- add a new layer
- reorder layers by dragging
- remove layers
- select a layer from the list for editing

The order of the list is the visual order used by the scene.

### Layer Settings

Click a layer in the list to select and highlight it in the preview. Click its sliders icon to open its settings in the right-side panel. Close the panel to return to the same preview position. Dragging and resizing on the stage still work directly.

Depending on the layer type, this can include:

- position and size
- text content or live variable source
- font, colour, background, and text effects
- image or video asset selection
- Godot scene pack and entry scene selection
- rotation and opacity

## Layer Types

Each scene can use a mix of layer types:

- `Text` for labels, scores, player information, and other live values
- `Image` for backgrounds, logos, frames, and artwork
- `Video` for attract loops, animations, and motion backgrounds
- `Godot Scene` for richer animated content loaded from a `.pck` file

### Text Layers

Text layers can use:

- fixed text that you type directly
- a live variable such as score
- custom fonts from the `Fonts` tab
- text effects such as outline, glow, underline, and uppercase

### Godot Scene Layers

Godot scene layers use uploaded `.pck` files from the Library.

You can run them in two ways:

- `Layered`: the Godot scene behaves like a normal layer inside the scene
- `Primary`: the Godot scene takes over the full window for that scene

When `Primary` is selected, the rest of the scene layout is ignored while that Godot scene is active.

> **Godot Compatibility Warning**
>
> Most self-contained Godot scenes work well, especially display-style content, score scenes, and animated UI. More complex exports may need testing first if they expect project-wide settings, special input handling, or other whole-project behaviour.

## Library

<img src="./media/screenshot-feature-media-library-current.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-library","wait_for":"#media-pane-library.show.active"},{"action":"wait","selector":"#media-assets-table"}]}' alt="Media Library tab" style="width: 100%;height: auto;">

The `Library` tab stores the files your scenes use.

On Library, use **Upload Asset** beside **Save Changes** to open the asset upload dialog. Drop files into the dialog or choose files; upload progress appears there. Assets remain available in Library.

You can upload:

- image files
- video files
- Godot `.pck` scene packs

The library shows useful information such as:

- name
- kind
- format
- status
- whether the asset is already in use
- file size

Use the Library when you want to prepare content first, then build scenes from it later.

## Fonts

<img src="./media/screenshot-feature-media-fonts.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-fonts","wait_for":"#media-pane-fonts.show.active"},{"action":"wait","selector":"#media-fonts-table"}]}' alt="Media Fonts tab" style="width: 100%;height: auto;">

The `Fonts` tab is where you manage the fonts used by text layers.

You can:

- choose **Upload Font** beside **Save Changes** on the Fonts tab to open the font upload dialog
- upload `.ttf` files
- upload a `.zip` that contains `.ttf` files
- browse both custom and system fonts
- filter the list to find a font quickly

Once uploaded, custom fonts become available in the text layer inspector.

## Displays

<img src="./media/screenshot-feature-media-displays-current.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-displays","wait_for":"#media-pane-displays.show.active"},{"action":"wait","selector":"#media-displays-table"}]}' alt="Media Displays tab" style="width: 100%;height: auto;">

The `Displays` tab shows the output displays that Media can target.

Use it to:

- refresh detection
- confirm display names and sizes
- check display roles
- review screen mapping
- enable or disable specific displays

Scenes use these display roles and targets in `Scene Settings`.

## Settings

<img src="./media/screenshot-feature-media-settings.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-defaults","wait_for":"#media-pane-defaults.show.active"},{"action":"wait","selector":"#media-defaults-editor"}]}' alt="Media Settings tab" style="width: 100%;height: auto;">

The `Settings` tab controls runtime defaults.

This is where you can:

- set the Godot binary path
- set the Godot control port
- enable automatic Godot restart if the runtime process stops unexpectedly
- show or hide the Godot debug panel while testing
- choose the default startup scene for each display
- decide whether a display should auto-play its default scene on start

This tab is useful when you want certain displays to come up with a known scene automatically.

## Runtime

<img src="./media/screenshot-feature-media-runtime-current.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-runtime","wait_for":"#media-pane-runtime.show.active"},{"action":"wait","selector":"#media-runtime-table"}]}' alt="Media Runtime tab" style="width: 100%;height: auto;">

The `Runtime` tab shows what Media is doing right now. Runtime Engine and Launches use standalone tables. Choose **Launch** beside Save Changes to open the right-side panel for display, window mode, scene selection and token updates. Per-launch Stop and Stop All remain on the Runtime tab. A successful **Launch / Play** closes the panel; failed launches leave it open so you can adjust the settings.

<img src="./media/screenshot-media-launch-panel.webp" data-source='{"url":"/login","next_url":"/media/","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-runtime"},{"action":"click","selector":"#media-launch-button","wait_for":"#media-launch-settings.show"}]}' alt="Media launch settings panel" style="width: 100%;height: auto;">

It includes:

- the current runtime engine status
- Godot launch information
- active scene launches
- stop controls for live playback
- a `Stop All` action when you want to clear everything quickly

This is the best place to check when:

- a scene is not appearing on the expected display
- you want to confirm Godot is running
- you need to stop a stuck or unwanted launch

## Typical Workflows

### Build a video or image scene

1. Choose **Upload Asset** to upload your media.
2. Open `Scenes` and add a new scene.
3. Set the target display in `Scene Settings`.
4. Add image, video, and text layers in `Layers`.
5. Use each layer’s sliders icon to open Layer Settings and style it; drag and resize it directly on the preview.
6. Preview the scene, then open it in a window or fullscreen to test it.

### Add a live score overlay

1. Select the text layer and open its sliders settings.
2. Set `Text Source` to `Variable`.
3. Choose the score variable.
4. Pick a font, colour, and effects.
5. Resize the layer on the stage until it looks right.

### Use a Godot scene pack

1. Upload the `.pck` using **Upload Asset**.
2. Add a `Godot Scene` layer in `Scenes`.
3. Select the pack and choose the entry scene.
4. Decide whether it should be `Layered` or `Primary`.
5. Test it in a Godot window from the preview toolbar.

## Related Features

- [Rules](7.1-rules.md)
- [Audio](17-audio.md)
- [Settings](16-settings.md)
