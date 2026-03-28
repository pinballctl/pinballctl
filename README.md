# PinballCTL Backglass Menu

This repository contains a standalone Godot project for a backglass-style menu scene intended to run inside the `pinballctl` Godot media runtime.

The current scene presents a horizontally scrolling mode-select carousel. It is designed to work in two environments:

- standalone during Godot development, using normal keyboard input
- embedded/exported as a `.pck` and launched by `pinballctl` as part of a media scene

## Purpose

The goal of this project is to keep menu and backglass UI development independent from the main `pinballctl` repository while still making the scene easy to drive from real pinball hardware at runtime.

That means:

- menu behavior should be authored in Godot
- keyboard control should keep working for local development and testing
- `pinballctl` should later be able to trigger the same actions from flippers, start buttons, or service buttons

## Project Structure

- [project.godot](/Users/andy/Repositories/other/pinballctl-backglass/project.godot): Godot project configuration and Input Map
- [scenes/main.tscn](/Users/andy/Repositories/other/pinballctl-backglass/scenes/main.tscn): main menu scene
- [scripts/main.gd](/Users/andy/Repositories/other/pinballctl-backglass/scripts/main.gd): menu logic, focus movement, selection handling
- [scenes/mode_orb.tscn](/Users/andy/Repositories/other/pinballctl-backglass/scenes/mode_orb.tscn): reusable carousel item scene
- [scripts/mode_orb.gd](/Users/andy/Repositories/other/pinballctl-backglass/scripts/mode_orb.gd): visual behavior for each orb

## Input Model

This project now uses Godot input actions instead of raw keycode handling.

Current actions:

- `ui_left`: move focus left
- `ui_right`: move focus right
- `ui_accept`: activate the currently focused mode

Keyboard bindings are defined in [project.godot](/Users/andy/Repositories/other/pinballctl-backglass/project.godot) so local development remains simple.

Current development bindings:

- Left Arrow -> `ui_left`
- Right Arrow -> `ui_right`
- Up Arrow -> `ui_accept`
- Enter / Keypad Enter -> `ui_accept`

## Runtime Integration Intent

When exported as a `.pck` and loaded by `pinballctl`, this scene should not depend on a physical keyboard. Instead, the `pinballctl` Godot runtime should inject the same Godot-style actions that the keyboard triggers during development.

Expected runtime action mapping:

- left flipper -> `ui_left`
- right flipper -> `ui_right`
- start / action button -> `ui_accept`
- optional back / service button -> `ui_cancel` if the scene later needs it

This keeps the scene portable. The scene only understands Godot actions; it does not need to know about pinball hardware identifiers.

## Scene API

The root script in [main.gd](/Users/andy/Repositories/other/pinballctl-backglass/scripts/main.gd) exposes a small API intended for runtime control:

- `focus_left()`
- `focus_right()`
- `activate_focused()`
- `pinballctl_input_action(action: String)`

`pinballctl_input_action()` currently accepts:

- `ui_left`
- `ui_right`
- `ui_accept`

This gives two possible integration paths for the runtime:

- inject real Godot input actions into the runtime
- call the scene method directly with action names

Both approaches preserve the same scene behavior.

## Selection Event

The scene emits a signal when a mode is activated:

- `mode_selected(mode_name: String, mode_index: int)`

This is intended as the clean handoff point when the runtime later needs to react to menu choices.

Possible future uses:

- trigger a `pinballctl` event when a mode is selected
- launch another media scene
- start gameplay in a selected rule/config mode

## Events And `pinballctl`

At the moment this project is still scene-local. It does not directly send or receive `pinballctl` events by itself.

The intended model is:

1. `pinballctl` receives hardware events from switches/buttons/flippers
2. `pinballctl` maps those hardware events to Godot UI actions such as `ui_left`, `ui_right`, and `ui_accept`
3. the Godot runtime forwards those actions into this scene
4. this scene updates focus/selection and emits `mode_selected(...)`
5. a later integration layer may translate that selection back into a higher-level `pinballctl` event

Example future flow:

- left flipper pressed
- `pinballctl` sends `ui_left` to the active Godot runtime
- this scene moves focus left
- start button pressed
- `pinballctl` sends `ui_accept`
- this scene activates the focused mode and emits `mode_selected("MULTIBALL", 1)`

## Development Notes

- Keep scene behavior action-based, not hardware-based.
- Prefer Godot Input Map actions over hard-coded keyboard keycodes.
- If additional menu behaviors are added, expose them as Godot actions first.
- If this project grows, keep the runtime-facing API small and explicit.

## Export

This project is intended to be exportable as a Godot `.pck` for upload into the `pinballctl` media library.

Recommended workflow:

1. develop and test locally in Godot with keyboard input
2. export the scene package
3. upload the `.pck` into `pinballctl`
4. launch it through the media runtime
5. later connect flipper/button hardware through injected UI actions
