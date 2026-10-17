# Media

Media is where you build, organise, and play the visual content for your machine.

You can use it to:

- create scenes from text, image, video, and Godot layers
- upload and organise your media library
- add custom fonts for text layers
- choose which displays scenes should target
- set default startup scenes for each display
- monitor what the Godot runtime is doing

## Media Tabs

Media is split into six tabs:

1. `Scenes`
2. `Library`
3. `Fonts`
4. `Displays`
5. `Settings`
6. `Runtime`

## Scenes

<img src="./media/screenshot-feature-media-scenes.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#media-tab-scenes"},{"action":"click","selector":"#media-tab-scenes","wait_for":"#media-pane-scenes.show.active"},{"action":"click","selector":"#media-scene-list [data-scene-id]","wait_for":"#media-scene-editor .media-editor-stack"}]}' alt="Media Scenes tab" style="width: 100%;height: auto;">

The `Scenes` tab is the main authoring workspace.

It is arranged in three parts:

- `Scenes` on the left so you can quickly switch between scene setups
- a live preview in the middle so you can play, scrub, and test the scene
- `Options`, `Layers`, and `Inspector` on the right for editing

### Scene Browser

Use the left-hand `Scenes` column to:

- add a new scene
- switch between existing scenes
- see which display a scene is aimed at
- collapse the browser when you want more room for the preview

### Scene Preview

The middle preview lets you:

- see the current scene on a scaled stage
- drag and resize layers directly on the stage
- play and stop the preview
- scrub through video content
- open the scene in a Godot window or fullscreen for live testing

### Options

The `Options` card controls how the whole scene behaves.

This includes:

- scene name
- target displays
- playback settings such as priority, loop, and audio
- scene policies such as interrupt and duplicate handling
- queue settings
- audio behaviour while the scene is active

### Layers

The `Layers` card is your scene stack.

You can:

- add a new layer
- reorder layers by dragging
- remove layers
- select a layer from the list for editing

The order of the list is the visual order used by the scene.

### Inspector

The `Inspector` shows all settings for the selected layer.

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

Scenes use these display roles and targets in their `Options` card.

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

The `Runtime` tab shows what Media is doing right now.

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

1. Upload your media in `Library`.
2. Open `Scenes` and add a new scene.
3. Set the target display in `Options`.
4. Add image, video, and text layers in `Layers`.
5. Use the `Inspector` to place and style each layer.
6. Preview the scene, then open it in a window or fullscreen to test it.

### Add a live score overlay

1. Select the text layer in `Inspector`.
2. Set `Text Source` to `Variable`.
3. Choose the score variable.
4. Pick a font, colour, and effects.
5. Resize the layer on the stage until it looks right.

### Use a Godot scene pack

1. Upload the `.pck` in `Library`.
2. Add a `Godot Scene` layer in `Scenes`.
3. Select the pack and choose the entry scene.
4. Decide whether it should be `Layered` or `Primary`.
5. Test it in a Godot window from the preview toolbar.

## Related Features

- [Rules](7-rules.md)
- [Audio](17-audio.md)
- [Settings](16-settings.md)
