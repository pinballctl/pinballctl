# Lighting

Configure fixtures before creating scenes. Use Stage to build and preview the scene, then Runtime to check what is playing.

## Before you start

Save the hardware mapping and check fixture identity/type. Use a safe lighting power/driver arrangement; keep coil power off during scene tests.

## Set up a fixture and preview a scene

1. Open **Fixtures** and verify the intended LEDs/strips, pixel counts and layout. **Expected:** the scene will address the right fixtures rather than a guessed device.

2. Open **Stage → Add Scene** and configure its name, cast, pattern/timeline, duration and end behaviour. **Expected:** a small explicit effect with a known stop/repeat policy.

3. Preview and scrub the scene; inspect its cast scope. **Expected:** only the intended virtual fixtures change. Preview cannot certify electrical wiring.

4. Choose **Save Changes**, compile/sync through the supported header workflow and inspect the result. **Expected:** saved authored data and deployed status are clear.

5. Add a Lighting **Play Scene** action to a safe test rule, save/review sync and trigger its observed input once. **Expected:** the saved effect runs and stops/repeats according to its settings.

<img src="./media/screenshot-feature-lighting-fixtures.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"lighting\"]","wait_for":"#lighting-tab-fixtures"},{"action":"click","selector":"#lighting-tab-fixtures","wait_for":"#lighting-tab-fixtures-pane.show.active"}]}' alt="Lighting fixtures tab" style="width: 100%;height: auto;">

1. Fixtures identifies the light targets. 2. Stage authors the scene. 3. Save/sync and Runtime show the deployment/playback path.

## Check the result

Keep scene names descriptive and check cast scope before adding priority/blending or multiple overlays. A scene preview and a deployed ESP effect are different validation steps.

**Safety:** Use appropriate supplies/drivers and brightness/current limits for the actual fixtures. Flashing effects can be uncomfortable; use low intensity and a short preview when testing.

## Troubleshooting

For a missing effect, check fixture identity, cast, selected scene, saved state and sync errors. For a scene that never stops, inspect end behaviour and active overlays before adding another trigger.

## Related guides

Next: [Hardware](hardware.md), [Rules](rules.md), [Playfield Live View](layout.md#live-view).

## Tabs and playback controls

### Fixtures Tab

[screenshot-feature-lighting-fixtures.webp]

**Fixtures** lists available lighting hardware from the saved mapping. Select a fixture’s sliders button to open its editor. Set the default colour for a single LED, or configure an RGB strip’s pixel count, length and layout. These details help you confirm which fixtures a scene’s cast targets.

### Stage Tab

<img src="./media/screenshot-feature-lighting-stage.webp" data-source='{"url":"/login","next_url":"/lighting","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Lighting stage tab" style="width: 100%;height: auto;">

Use **Browse Scenes** to select a scene or **Add Scene** to create one. The preview sits beside **Scene Settings** on desktop, and pixel controls appear when you select a fixture or light. Draft edits remain local to the editor until you select **Save Changes**.

In **Scene Settings**, name the scene, select a pattern and choose its cast. Set the duration in seconds, minutes or frames, and choose an end behaviour such as **Stop**, **Repeat** or **Bounce**. Set priority and blend mode when several scenes may run together.

Select a fixture in **Cast** to locate it and open its controls. A strip selection begins at pixel 0. Click a pixel to select it, drag a box to select several, or hold **Shift** and click to add or remove individual pixels. For a preset pattern, click near a pixel on a line-layout strip to select the strip, or drag from there to move it. This also works just outside the playfield outline.

### Runtime Tab

<img src="./media/screenshot-feature-lighting-runtime.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"lighting\"]","wait_for":"#lighting-tab-runtime"},{"action":"click","selector":"#lighting-tab-runtime","wait_for":"#lighting-tab-runtime-pane.show.active"}]}' alt="Lighting runtime tab" style="width: 100%;height: auto;">

**Runtime** shows the ESP connection and which synced scenes are playing. Check each scene’s priority, blend mode, paused state and order, and look for pixel overrides that may be holding specific LEDs.

### Layering and Scene Overlays (Simple Explanation)

Scenes such as **Game Mode** or **Bonus** can play above a background scene such as **Attract**. **Stop Lower** ends the lower scene. **Pause Lower** lets it resume when the top scene ends. **Play Over** keeps both running.

A direct pixel command such as `LIGHT_PIXELS_SET` holds the affected lights at the requested state. Releasing the override returns control to the scene.

### Top Actions

Use **Play** and **Stop** to preview the selected scene locally. The preview follows the compiled output. **Run selected scene on ESP** starts or stops the selected scene on hardware. **All Lights On/Off** helps you locate fixtures and toggles back to the normal preview.

**Save Changes** saves the lighting configuration on the Pi. **Sync Lighting** compiles and queues it for deployment to the ESP. The sync button stays muted while checking status or when both revisions match. A green outline indicates that the revisions differ and need syncing.

### Custom Timeline

Choose **Custom Timeline** to control the colour and on/off state of each pixel frame by frame. Use the scrubber or frame-step controls to navigate, use the clear-frame action to reset the selected frame, and use the marker pins to locate tags.

### Timeline Tags

Manage frame tags in the tag dialog. Each tag must be unique within its scene and use up to 64 lowercase letters, digits, underscores or hyphens. In a Rule’s **Apply Lighting Scene** action, choose **Tag** in **Start at** to start from a named frame.

### Save and Sync Workflow

1. Build or edit the scene in **Stage**.
2. Check that the cast targets the intended hardware in **Fixtures**.
3. Select **Save Changes**, then **Sync Lighting**.
4. Open **Runtime** to confirm the ESP’s playback state.

### Pattern Reference

<table>
  <thead>
    <tr>
      <th>Pattern</th>
      <th>What It Looks Like</th>
      <th>Options</th>
    </tr>
  </thead>
  <tbody>
      <tr><td><code>solid</code><br>Solid</td><td>A steady colour fill across the selected cast.</td><td><code>Colour</code>, <code>Brightness</code></td></tr>
      <tr><td><code>pulse</code><br>Pulse</td><td>All selected lights pulse brighter and dimmer together.</td><td><code>Colour</code>, <code>Brightness</code>, <code>PeriodMs</code></td></tr>
      <tr><td><code>rainbow</code><br>Rainbow</td><td>A flowing rainbow cycle moving across fixtures.</td><td><code>Brightness</code>, <code>Speed</code>, <code>Segments</code>, <code>Saturation</code></td></tr>
      <tr><td><code>alternating</code><br>Alternating</td><td>Alternates odd/even pixels between Colour 1 and Colour 2.</td><td><code>Brightness</code>, <code>SwitchMs</code>, <code>Colour 1</code>, <code>Colour 2</code></td></tr>
      <tr><td><code>chase</code><br>Chase</td><td>A moving block of light that travels along strips.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Width</code></td></tr>
      <tr><td><code>wave</code><br>Wave</td><td>A directional wave band sweeping across the playfield.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Direction</code>, <code>ColourMode</code>, <code>Band</code>, <code>Hold</code></td></tr>
      <tr><td><code>rainbow_gradient</code><br>Rainbow Gradient</td><td>A smooth rainbow gradient drift over time.</td><td><code>Brightness</code>, <code>Speed</code>, <code>Spread</code>, <code>Saturation</code></td></tr>
      <tr><td><code>sparkle</code><br>Sparkle</td><td>Random twinkles that pop on and off.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Density</code>, <code>MinOnMs</code>, <code>MaxOnMs</code>, <code>Seed</code></td></tr>
      <tr><td><code>strobe</code><br>Strobe</td><td>Fast flashing strobe effect.</td><td><code>Colour</code>, <code>Brightness</code>, <code>RateHz</code>, <code>DutyCycle</code></td></tr>
      <tr><td><code>breath</code><br>Breath</td><td>A soft inhale/exhale fade effect.</td><td><code>Colour</code>, <code>Brightness</code>, <code>PeriodMs</code>, <code>MinIntensity</code>, <code>MaxIntensity</code></td></tr>
      <tr><td><code>fade_in_out</code><br>Fade In Out</td><td>Classic full-scene fade in and fade out.</td><td><code>Colour</code>, <code>Brightness</code>, <code>PeriodMs</code>, <code>MinBrightness</code>, <code>MaxBrightness</code></td></tr>
      <tr><td><code>fade_stagger</code><br>Fade Stagger</td><td>Fade pattern with per-light phase offsets.</td><td><code>Colour</code>, <code>Brightness</code>, <code>PeriodMs</code>, <code>MinBrightness</code>, <code>MaxBrightness</code>, <code>PhaseOffset</code>, <code>Seed</code></td></tr>
      <tr><td><code>color_wipe</code><br>Color Wipe</td><td>Colour wipes from one side/direction to the other.</td><td><code>Colour</code>, <code>Brightness</code>, <code>StepMs</code>, <code>Direction</code>, <code>ClearAfter</code></td></tr>
      <tr><td><code>theater_chase</code><br>Theater Chase</td><td>Marquee-style dotted chase pattern.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Spacing</code>, <code>Tail</code></td></tr>
      <tr><td><code>scanner</code><br>Scanner</td><td>A back-and-forth scanner beam.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Width</code>, <code>Bounce</code></td></tr>
      <tr><td><code>twinkle_fade</code><br>Twinkle Fade</td><td>Twinkles that rise and fade smoothly.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Density</code>, <code>RiseMs</code>, <code>FallMs</code>, <code>Seed</code></td></tr>
      <tr><td><code>fire</code><br>Fire</td><td>Heat-like flicker fire simulation.</td><td><code>Brightness</code>, <code>Speed</code>, <code>Cooling</code>, <code>Sparking</code>, <code>Seed</code></td></tr>
      <tr><td><code>meteor_rain</code><br>Meteor Rain</td><td>Comet/meteor streaks with trailing fade.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>TailLength</code>, <code>Decay</code>, <code>Bounce</code></td></tr>
      <tr><td><code>ping</code><br>Ping</td><td>A pulse expanding from an origin point.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Thickness</code>, <code>Falloff</code>, <code>Origin</code></td></tr>
      <tr><td><code>radar</code><br>Radar</td><td>A rotating sweep beam like a radar arm.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>SweepDeg</code>, <code>Tail</code></td></tr>
      <tr><td><code>ripple</code><br>Ripple</td><td>Concentric ripple rings radiating outward.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Rings</code>, <code>Thickness</code>, <code>Falloff</code></td></tr>
      <tr><td><code>chevron</code><br>Chevron</td><td>Angled chevron sweep pattern.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Direction</code>, <code>SpreadDeg</code>, <code>Length</code>, <code>Thickness</code>, <code>Tail</code></td></tr>
      <tr><td><code>spiral</code><br>Spiral</td><td>A rotating spiral movement around an origin.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Turns</code>, <code>Thickness</code>, <code>Direction</code>, <code>Origin</code></td></tr>
      <tr><td><code>lightning</code><br>Lightning</td><td>Irregular lightning-style flashes and branches.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Density</code>, <code>Width</code>, <code>Decay</code>, <code>Branches</code>, <code>Seed</code></td></tr>
      <tr><td><code>orbit</code><br>Orbit</td><td>A point/beam orbiting around a centre radius.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Radius</code>, <code>Tail</code>, <code>Direction</code></td></tr>
      <tr><td><code>equalizer</code><br>Equalizer</td><td>Bar-like motion inspired by audio equalizers.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Bands</code>, <code>Smoothing</code>, <code>Direction</code>, <code>Seed</code></td></tr>
      <tr><td><code>comet_burst</code><br>Comet Burst</td><td>Multiple comet bursts fired from an origin.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Count</code>, <code>SpreadDeg</code>, <code>Tail</code>, <code>Width</code>, <code>Origin</code>, <code>Seed</code></td></tr>
      <tr><td><code>cross_sweep</code><br>Cross Sweep</td><td>Cross (plus or X) sweep across the cast.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Width</code>, <code>Style</code>, <code>Direction</code></td></tr>
      <tr><td><code>noise_wash</code><br>Noise Wash</td><td>Organic noise shimmer/wash with optional rainbow mode.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Scale</code>, <code>Contrast</code>, <code>ColourMode</code></td></tr>
      <tr><td><code>zone_pulse</code><br>Zone Pulse</td><td>Grouped zone pulsing based on fixture IDs.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>GroupBy</code>, <code>PrefixLen</code>, <code>Overlap</code></td></tr>
      <tr><td><code>arc_fan</code><br>Arc Fan</td><td>Fan of arc beams sweeping from an origin.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>BeamCount</code>, <code>BeamSpreadDeg</code>, <code>BeamWidthDeg</code>, <code>Tail</code>, <code>Origin</code>, <code>Direction</code></td></tr>
      <tr><td><code>ticker</code><br>Ticker</td><td>Scrolling ticker-style moving window.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>Window</code>, <code>Direction</code>, <code>Text</code></td></tr>
      <tr><td><code>morse_beacon</code><br>Morse Beacon</td><td>Flashes a text message in Morse timing.</td><td><code>Colour</code>, <code>Brightness</code>, <code>DotMs</code>, <code>Message</code></td></tr>
      <tr><td><code>step_sequence</code><br>Step Sequence</td><td>User-defined sequence of colour/time/intensity steps.</td><td><code>Steps</code>, <code>Brightness</code></td></tr>
      <tr><td><code>dual_scanner</code><br>Dual Scanner</td><td>Two scanner beams using two colours.</td><td><code>Colour 1</code>, <code>Colour 2</code>, <code>Brightness</code>, <code>Speed</code>, <code>Trail</code>, <code>Direction</code></td></tr>
      <tr><td><code>spark_gap</code><br>Spark Gap</td><td>Spark effect with dynamic dark gaps.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>GapWidth</code>, <code>GapCount</code>, <code>Softness</code></td></tr>
      <tr><td><code>impact_burst</code><br>Impact Burst</td><td>Impact ring burst with decay.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>RingWidth</code>, <code>Decay</code>, <code>Origin</code>, <code>Seed</code></td></tr>
      <tr><td><code>drift_palette</code><br>Drift Palette</td><td>Palette-driven colour drift across fixtures.</td><td><code>Palette</code>, <code>Brightness</code>, <code>Speed</code>, <code>Spread</code></td></tr>
      <tr><td><code>random_strobe_groups</code><br>Random Strobe Groups</td><td>Grouped random strobe bursts.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>GroupCount</code>, <code>Duty</code>, <code>Seed</code></td></tr>
      <tr><td><code>heartbeat_double</code><br>Heartbeat Double</td><td>Double-beat heartbeat pulse shape.</td><td><code>Colour</code>, <code>Brightness</code>, <code>Speed</code>, <code>SecondLevel</code>, <code>Sharpness</code></td></tr>
      <tr><td><code>custom</code><br>Custom Timeline</td><td>Timeline-authored frames and markers for exact control.</td><td><code>Brightness</code>, <code>Tween</code></td></tr>
  </tbody>
</table>

## Related Features

- [Rules](rules.md)
- [Playfield](layout.md)
- [Hardware](hardware.md)
