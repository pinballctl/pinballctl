# Backglass asset provenance

The [Pinball CTL vector sample](../user-guide/godot.md#pinball-ctl-vector-sample) uses the project’s wordmark, the Relay character and animated vector backdrops.

- `media/backglass/sample/ctl_sample/assets/pinballctl-logo.svg` combines the Pinball CTL mark with a wordmark outlined in Inter 4.1. Inter is available under the [SIL Open Font License](https://rsms.me/inter/).
- `media/backglass/sample/ctl_sample/assets/relay-parts.svg` contains the vector parts for Relay. `relay.gd` positions the parts and draws the expressions and poses.
- `scenery.gd` draws the scene backgrounds. `attract_loop.gd` controls the attract sequence and its three-ball replay. `display.gd` draws the interface and handles scene state.

The videos in the [scene previews](../user-guide/godot.md#scene-previews) show the sample running in Godot. The scenes draw and animate at runtime.
