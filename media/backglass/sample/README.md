# Pinball CTL backglass sample

Open `project.godot` in Godot 4.6 or run this from the repository root.

```sh
godot --path media/backglass/sample
```

Left and Right act as the flippers. Enter or Space acts as Start. F1 through F6
preview Attract, Menu, High Scores, Tilt, Bonus and Game Over with demo data.
F7 opens Mode and F8 previews Game Started.
Attract runs as one 38-second scene. Relay waves, hops aside, then watches
the parts fall as a striped progress bar names each one. The panel below
Relay shows shot updates during the three-ball replay. Each ball has its
own launch, reaction and drain poses.
Start opens the menu at any point. The replay's score is separate from the
live score.

Game Started loops every 30 seconds and keeps the controller’s score, player
and ball visible. Relay draws eight gestures and expressions per loop from
a shuffled library of sixteen. The scene plays until Media replaces it.

See the [Godot user guide](../../website/docs/user-guide/godot.md#pinball-ctl-vector-sample)
for export, cabinet button mappings, placeholders and queue setup.
