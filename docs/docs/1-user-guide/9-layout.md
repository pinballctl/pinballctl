# Playfield

Arrange the software view of your machine and connect its visual components to named hardware. Use the layout to understand and test responses as the build grows.

## Before you start

Have a saved hardware mapping and, if wanted, a playfield image. Keep outputs disabled before testing keyboard or mouse-triggered events.

## Try it step by step

1. Open **Stage** and confirm the Components list contains the expected hardware. **Expected:** your saved mapping supplies the intended devices.

2. Place/select a component and edit its position, size or appearance. Use Auto Layout only when you want it to rearrange the layout. **Expected:** the selected component is identifiable on the canvas.

3. Where needed, configure a keyboard binding and its key-down/key-up gesture mapping in the inspector. **Expected:** the two gestures correspond to the intended input behaviour.

4. Choose **Save Changes**, then open Live View to observe the saved layout. **Expected:** positions and bindings persist; test one input at a time with output power disconnected.

<img src="./media/screenshot-feature-layout-stage.webp" data-source='{"url":"/login","next_url":"/playfield","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Playfield stage tab" style="width: 100%;height: auto;">

**Screen guide:** 1. Components identifies devices. 2. Stage positions them. 3. The selected component inspector edits appearance and bindings; Save Changes persists the arrangement.

## Helpful checks

Save before leaving. Clear Layout changes the authored arrangement; it is not a way to reset hardware or game state.

**Safety:** Test controls can fire configured events and downstream actions. A drawn solenoid or a simulated press is not electrically isolated by the canvas.

## If the result is different

If a component is missing, check the hardware list/mapping first. If position or binding disappears, verify save success. If a shortcut does nothing, check focus and the configured gesture before editing a rule.

## Continue your build

Next: [Hardware](7-hardware.md), [Live View](20-live-view.md), [Events](27-events.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## Page Structure

Playfield is split into two tabs:

1. `Stage`
2. `Settings`

## Stage Tab



Stage contains the visual canvas and component editing workflow.

Main areas:

- playfield canvas
- components card
- component inspector (when a component is selected)
- save action in the page header

Component inspector supports:

- appearance and size controls
- bound key capture/removal
- key-down/key-up gesture mapping
- trigger/action test controls
- remove component action

Drag and placement behavior:

- components move by drag on canvas
- selected component is highlighted
- updates persist after `Save Changes`

## Components Card

The `Components` card is the hardware component list and quick layout control area.

Use it to:

- view discovered component groups (`Buttons`, `LEDs`, `Solenoids`, `Other`)
- run `Auto Layout`
- run `Clear Layout`
- verify the hardware list is loaded before editing on-canvas positions

<img src="./media/screenshot-playfield-components-card.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"playfield\"]","wait_for":"h1"},{"action":"click","selector":"[data-emu-toggle=\"hw\"]","wait_for":"[data-emu-panel=\"hw\"]:not(.d-none)"}],"target":".emu-side-col .emu-card:has([data-emu-toggle=\"hw\"])" }' alt="Playfield Components card expanded" style="width: 100%; max-width: 400px; height: auto;">

## Component Inspector

Select a component from the `Components` list to open and focus the `Component Inspector`.

Inspector usage:

- validate which element is selected
- tune appearance, color, size, and rotation
- capture and manage keyboard bindings
- configure trigger/action test controls
- remove a component if required

The example below selects `Right Flipper Button` from the Components list and shows the populated inspector.

<img src="./media/screenshot-playfield-component-inspector.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"playfield\"]","wait_for":"#emu-stage-pane"},{"action":"click","selector":"[data-emu-toggle=\"hw\"]","wait_for":"[data-emu-panel=\"hw\"]:not(.d-none)"},{"action":"click","selector":"#emu-buttons button.emu-chip:has-text(\"Right Flipper Button\")","wait_for":"#emu-settings:not(.d-none)"}],"target":".emu-side-col .emu-card:has(#emu-selected-label)"}' alt="Playfield Component Inspector with Right Flipper Button selected" style="width: 100%; max-width: 400px; height: auto;">

## Settings Tab

<img src="./media/screenshot-feature-layout-options.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"playfield\"]","wait_for":"#emu-options-tab"},{"action":"click","selector":"#emu-options-tab","wait_for":"#emu-options-pane.show.active"}]}' alt="Playfield Settings tab" style="width: 100%;height: auto;">

Settings groups layout-level controls into Playfield Dimensions and Background Image sections within one settings card.

Primary controls:

- width
- height
- ratio display

Background Image controls let you upload or remove the image, choose its fit and position, and adjust opacity.

`Auto Layout` and `Clear Layout` remain on the Layout tab for regenerating or resetting component placement.

## Keyboard Binding System

Binding flow:

1. Select a component in `Stage`.
2. Click `Capture` in inspector.
3. Press a key.
4. Configure key-down and key-up gestures.

This allows interaction testing without physical hardware input.

## Event and Trigger Testing

Playfield can fire bound events and show response state visually.

Common uses:

- validate rule-trigger mappings
- test event-driven reactions
- verify component linkage behavior

## Save Workflow

Recommended flow:

1. Arrange components in `Stage`.
2. Tune layout-level values in `Settings`.
3. Test key bindings and events.
4. Click `Save Changes`.

## Related Features

- [Rules](7.1-rules.md)
- [Lighting](8-lighting.md)
- [Hardware](7-hardware.md)
