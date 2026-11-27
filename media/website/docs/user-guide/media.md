# Media

Use Scenes to build what appears on a display. Add assets in Library, connect the display in Displays, and use Runtime to check what is playing.

## Before you start

Have a supported image/video/font or scene asset and an appropriate host display environment. Live output needs the configured Godot runtime; browser preview alone does not verify it.

## Build and preview a display scene

1. Upload the needed assets in **Library** or **Fonts**. **Expected:** the files are listed and available to the layer selectors.

2. In **Scenes**, choose **Add Scene**, set its name/target display and add a simple Text or Image layer. **Expected:** the layer appears in the composition and can be selected.

3. Edit the selected layer through its sliders panel. Check order, size, position and opacity. **Expected:** the composition matches the intended display layout.

4. Preview, then **Save Changes**. Check the target in **Displays**, runtime executable/configuration in **Settings**, and status in **Runtime** before live playback. **Expected:** the saved scene reaches the intended real display, or a specific runtime error explains why not.

5. Add a Media **Play Scene** action to a controlled test rule. Trigger it once and verify stop/interrupt/queue behaviour. **Expected:** the correct saved scene runs, without an accidental endless loop or blocked queue.

<img src="./media/screenshot-feature-media-scenes.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#media-tab-scenes"},{"action":"click","selector":"#media-tab-scenes","wait_for":"#media-pane-scenes.show.active"},{"action":"click","selector":"[data-bs-target=\"#media-scene-library\"]","wait_for":"#media-scene-library.show"},{"action":"click","selector":"#media-scene-list [data-scene-id]","wait_for":"#media-layer-list"}]}' alt="Media Scenes tab" style="width: 100%;height: auto;">

1. Browse Scenes selects the saved composition. 2. The preview/layer list edits its content. 3. Scene and layer sliders open different settings panels.

## Check the result

Separate scene settings (display/playback policy) from layer settings (content/geometry). Start with a local image before diagnosing video conversion or custom packs.

**Safety:** Media packs can execute custom Godot code. Use trusted assets and keep output actions isolated while testing scene input mappings or events sent back to Rules.

## Troubleshooting

If browser preview works but the display is blank, check Godot process/runtime logs, display selection, saved scene target and host session access. If a layer is missing, check asset reference, order/opacity and entry scene for packs.

## Related guides

Next: [Godot](godot.md), [Audio](audio.md), [Rules](rules.md), [Troubleshooting](troubleshooting.md).

## Media tabs and scene controls

### Scenes

[screenshot-feature-media-scenes.webp]

Use **Browse Scenes** beside **Save Changes** to choose a scene, or **Add Scene** to create one. The layer list sits beside the preview on desktop and below it on smaller screens. Select a layer to highlight it on the stage, then use its sliders icon to open its settings. Select **Save Changes** to keep your draft edits.

### Scene Browser

**Browse Scenes** shows each scene’s target displays and layer summary. Select a scene to return to the preview, open its settings with the sliders icon, or use the remove control. Removing a scene requires confirmation and takes effect when you save.

### Scene Preview

The scaled stage lets you drag and resize layers, play or stop the preview and scrub through video. To check the runtime output, open the scene in a Godot window or fullscreen.

### Scene Settings

Use the scene’s sliders icon in **Browse Scenes** to set its name, target displays, priority, looping and audio behaviour. The panel also controls interruptions, duplicates and queuing. Closing the panel returns you to the preview with your draft intact.

### Layers

Add or remove layers in the **Layers** list and drag them to change their stacking order. Select a layer to highlight it on the stage. Long lists scroll independently so the preview stays visible.

### Layer Settings

Select a layer’s sliders icon to open its settings, then close the panel to return to the same preview position. Dragging and resizing also work directly on the stage.

Fields vary by type. Edit position, size, rotation and opacity, then choose an image or video asset, a Godot pack and entry scene, or text and its formatting.

### Layer Types

Use **Text** for labels, scores and player information, **Image** for still artwork, and **Video** for attract loops or animation. **Godot Scene** loads interactive or animated content from an uploaded `.pck` file.

### Text Layers

Enter fixed text or select a live variable such as score. Choose a font from **Fonts**, then set the colour, background and text effects such as outline, glow, underline or uppercase.

### Godot Scene Layers

Select an uploaded `.pck` file from **Library**. **Layered** places the Godot scene in the layer stack. **Primary** gives it the whole runtime window for the duration of the scene.

> Most self-contained Godot scenes work well. Test a more complex pack in the runtime if it relies on project-wide settings, special input handling or other whole-project behaviour.

### Library

<img src="./media/screenshot-feature-media-library-current.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-library","wait_for":"#media-pane-library.show.active"},{"action":"wait","selector":"#media-assets-table"}]}' alt="Media Library tab" style="width: 100%;height: auto;">

Use **Upload Asset** beside **Save Changes** to select or drop in images, videos or Godot `.pck` packs. The dialog shows upload progress. The Library lists each file’s name, kind, format, status, size and whether it is in use.

### Fonts

<img src="./media/screenshot-feature-media-fonts.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-fonts","wait_for":"#media-pane-fonts.show.active"},{"action":"wait","selector":"#media-fonts-table"}]}' alt="Media Fonts tab" style="width: 100%;height: auto;">

Use **Upload Font** beside **Save Changes** to add a `.ttf` file or a ZIP containing `.ttf` files. Browse or filter the custom and system fonts. Uploaded fonts are available in the text layer inspector.

### Displays

<img src="./media/screenshot-feature-media-displays-current.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-displays","wait_for":"#media-pane-displays.show.active"},{"action":"wait","selector":"#media-displays-table"}]}' alt="Media Displays tab" style="width: 100%;height: auto;">

Refresh detection to review display names, sizes, roles and screen mapping. Enable or disable individual displays for use as targets in **Scene Settings**.

### Settings

<img src="./media/screenshot-feature-media-settings.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-defaults","wait_for":"#media-pane-defaults.show.active"},{"action":"wait","selector":"#media-defaults-editor"}]}' alt="Media Settings tab" style="width: 100%;height: auto;">

Set the Godot binary path and control port, choose whether the runtime restarts automatically after it stops, and show or hide the debug panel. For each display, select a default startup scene and decide whether to play it automatically at startup.

### Runtime

<img src="./media/screenshot-feature-media-runtime-current.webp" data-source='{"url":"/login","next_url":"/media","dark_mode":true,"settle_ms":1400,"click":[{"action":"type","selector":"input[name=\"username\"]","value":"admin"},{"action":"type","selector":"input[name=\"password\"]","value":"password"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-runtime","wait_for":"#media-pane-runtime.show.active"},{"action":"wait","selector":"#media-runtime-table"}]}' alt="Media Runtime tab" style="width: 100%;height: auto;">

The **Runtime Engine** and **Launches** tables show the engine status, Godot launch details and active scenes. Check them when a scene is missing from its expected display. Use a launch’s stop control or **Stop All** to end playback.

Select **Launch** beside **Save Changes** to choose a display, window mode and scene. **Windowed** opens a separate test window. A successful **Launch / Play** closes the panel, and a failed launch leaves it open so you can adjust the settings.

<img src="./media/screenshot-media-launch-panel.webp" data-source='{"url":"/login","next_url":"/media/","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#media-tab-runtime"},{"action":"click","selector":"#media-launch-button","wait_for":"#media-launch-settings.show"}]}' alt="Media launch settings panel" style="width: 100%;height: auto;">

To update text in a running scene, enter the token name without braces, such as `score` for `{{SCORE}}`. Enter the new value and choose **Update Token**.

### Typical Workflows

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

- [Rules](rules.md)
- [Audio](audio.md)
- [Settings](settings.md)
