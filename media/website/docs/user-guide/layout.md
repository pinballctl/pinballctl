# Playfield

Use Playfield to arrange mapped components, test the saved layout in Live View, and inspect game progress in Rules State.

## At a glance

**Stage**. Place components, then select one to open its inspector.

**Settings**. Configure the appearance and scale of the layout.

**Live View**. Test the saved layout, watch events, and preview lighting and display scenes.

**Rules State**. Check counters, flags and timers as the game runs.

## Before you start

Have a saved hardware mapping and, if wanted, a playfield image. Keep outputs disabled before testing keyboard or mouse-triggered events.

## Place a mapped component

1. Open **Stage** and confirm the Components list contains the expected hardware. **Expected:** your saved mapping supplies the intended devices.

2. Place/select a component and edit its position, size or appearance. Use Auto Layout only when you want it to rearrange the layout. **Expected:** the selected component is identifiable on the canvas.

3. Where needed, configure a keyboard binding and its key-down/key-up gesture mapping in the inspector. **Expected:** the two gestures correspond to the intended input behaviour.

4. Choose **Save Changes**, then select **Live View** to observe the saved layout. **Expected:** positions and bindings persist; test one input at a time with output power disconnected.

<img src="./media/screenshot-feature-layout-stage.webp" data-source='{"url":"/login","next_url":"/playfield/?tab=stage","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Playfield stage tab" style="width: 100%;height: auto;">

1. Components identifies devices. 2. Stage positions them. 3. The selected component inspector edits appearance and bindings; Save Changes persists the arrangement.

## Check the result

Save before leaving. Clear Layout changes the authored arrangement; it is not a way to reset hardware or game state.

**Safety:** Test controls can fire configured events and downstream actions. A drawn solenoid or a simulated press is not electrically isolated by the canvas.

## Troubleshooting

If a component is missing, check the hardware list/mapping first. If position or binding disappears, verify save success. If a shortcut does nothing, check focus and the configured gesture before editing a rule.

## Related guides

Next: [Hardware](hardware.md), [Events in Logs](logs.md#find-and-inspect-an-event).

## Stage and layout settings

### Stage Tab



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
- remove component action

Drag and placement behavior:

- components move by drag on canvas
- selected component is highlighted
- updates persist after `Save Changes`

### Components Card

The `Components` card is the hardware component list and quick layout control area.

Use it to:

- view discovered component groups (`Buttons`, `LEDs`, `Solenoids`, `Other`)
- run `Auto Layout`
- run `Clear Layout`
- verify the hardware list is loaded before editing on-canvas positions

<img src="./media/screenshot-playfield-components-card.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"playfield\"]","wait_for":"h1"},{"action":"click","selector":"[data-emu-toggle=\"hw\"]","wait_for":"[data-emu-panel=\"hw\"]:not(.d-none)"}],"target":".emu-side-col .emu-card:has([data-emu-toggle=\"hw\"])" }' alt="Playfield Components card expanded" style="width: 100%; max-width: 400px; height: auto;">

### Component Inspector

Select a component from the `Components` list to open and focus the `Component Inspector`.

Inspector usage:

- validate which element is selected
- tune appearance, color, size, and rotation. The Size slider runs from 10% to 250% in 5% steps, and Live View uses the saved size.
- capture and manage keyboard bindings
- configure trigger/action test controls
- remove a component if required

The example below selects `Right Flipper Button` from the Components list and shows the populated inspector.

<img src="./media/screenshot-playfield-component-inspector.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"playfield\"]","wait_for":"#emu-stage-pane"},{"action":"click","selector":"[data-emu-toggle=\"hw\"]","wait_for":"[data-emu-panel=\"hw\"]:not(.d-none)"},{"action":"click","selector":"#emu-buttons button.emu-chip:has-text(\"Right Flipper Button\")","wait_for":"#emu-settings:not(.d-none)"}],"target":".emu-side-col .emu-card:has(#emu-selected-label)"}' alt="Playfield Component Inspector with Right Flipper Button selected" style="width: 100%; max-width: 400px; height: auto;">

### Settings Tab

<img src="./media/screenshot-feature-layout-options.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"playfield\"]","wait_for":"#emu-options-tab"},{"action":"click","selector":"#emu-options-tab","wait_for":"#emu-options-pane.show.active"}]}' alt="Playfield Settings tab" style="width: 100%;height: auto;">

The last Playfield tab, **Settings**, groups layout-level controls into Playfield Dimensions and Background Image sections within one settings card. Playfield remembers the last tab used in this browser.

Primary controls:

- width
- height
- ratio display

Background Image controls let you upload or remove the image, choose its fit and position, and adjust opacity.

`Auto Layout` and `Clear Layout` are on the Stage tab for regenerating or resetting component placement.

### Keyboard Binding System

Binding flow:

1. Select a component in `Stage`.
2. Click `Capture` in inspector.
3. Press a key.
4. Configure key-down and key-up gestures.

This allows interaction testing without physical hardware input.

## Live View

Choose **Save Changes** after editing, then select **Live View**. The stage reads the latest saved layout and reflects events from the machine and the test controls. Click the stage or tab into the view before using a keyboard shortcut. Shortcuts send events only while this tab is active. Switching tabs releases any held inputs that have a key-up gesture.

<img src="./media/screenshot-feature-live-view.webp" data-source='{"url":"/login","next_url":"/playfield/?tab=live","dark_mode":true,"settle_ms":3000,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Live View feature overview" style="width: 100%;height: auto;">

- Press a saved shortcut or right-click a component and choose an available gesture. For buttons with both gestures, **Pressed + Released** performs a complete press.
- Use **System Events** to select and trigger a configured system event.
- Use **Lighting** to start or stop a scene and watch the overlay. With the bridge offline, the preview can still play locally.
- Use **Scene Trigger** to choose a scene, display, and window mode and play or stop the scene through the media runtime.

With an ESP connected, Live View inputs use the normal event path and can actuate configured hardware. Keep output power disconnected while testing inputs. Offline preview shows software behaviour and cannot verify wiring, electrical outputs or time-critical response.

## Rules State

Select **Rules State** to inspect counters, flags and timers without leaving Playfield. The table shows each value's scope, associated player, and live value. It refreshes while the tab is open.

<img src="./media/screenshot-live-view-rules-state.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_url":"/playfield/?tab=rules-state"}' alt="Playfield Rules State showing global and per-player values">

## Related features

- [Rules](rules.md)
- [Lighting](lighting.md)
- [Hardware](hardware.md)
