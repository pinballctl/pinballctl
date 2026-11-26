# Backglass development

The Pinball CTL vector sample lives in `media/backglass/sample/`. It includes eight scenes for attract mode, menus, high scores, live play and short cues. Follow the [Godot Backglass tutorial](../user-guide/godot.md) to preview the sample or build a menu and scoreboard from a blank project.

## Preview and validate the sample

Open `media/backglass/sample/project.godot` in Godot 4.6 or run these commands from the repository root.

```sh
godot --path media/backglass/sample
godot --headless --path media/backglass/sample --editor --import --quit
godot --headless --path media/backglass/sample --script res://tests/smoke.gd
```

Use Left and Right as flippers and Enter or Space as Start. The sample smoke test checks scene entry points, menu actions, live value updates and timed cues. Before using the pack in a cabinet, check cabinet input mapping, display scaling and playback on the target device.

## Export and integrate

Export the sample with its **Linux** preset.

```sh
godot --headless --path media/backglass/sample --export-pack Linux /absolute/path/pinballctl-sample.pck
```

Upload the pack in **Media** and select an entry under `res://ctl_sample/entries/`. Keep new sample resources under `res://ctl_sample/` to avoid collisions with the host project. The tutorial covers [cabinet button mappings](../user-guide/godot.md#run-and-export-the-vector-sample) and [live values and cue queues](../user-guide/godot.md#supply-live-values-and-queue-cues). See [Godot media runtime](godot-runtime.md) for the host, display lifecycle and event interface.

See [Backglass asset provenance](backglass-assets.md) for the vector artwork and animation sources.
