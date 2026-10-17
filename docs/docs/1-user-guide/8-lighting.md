# Lighting

Lighting is the scene authoring workflow for playfield effects and event-driven feedback.

It lets you build scenes, preview compiler output, and sync lighting data to ESP.

## Page Structure

Lighting is split into three tabs:

1. `Stage`
2. `Fixtures`
3. `Runtime`

## Fixtures Tab

<img src="./media/screenshot-feature-lighting-fixtures.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"lighting\"]","wait_for":"#lighting-tab-fixtures"},{"action":"click","selector":"#lighting-tab-fixtures","wait_for":"#lighting-tab-fixtures-pane.show.active"}]}' alt="Lighting fixtures tab" style="width: 100%;height: auto;">

Sourced from the hardware mapping, the fixtures list all available lighting hardware and let you refine metadata. For single LEDs you can set colour defaults, and for RGB strips you can define pixel count, length, and layout.

Use it to:

- review available fixtures
- inspect fixture layout/type metadata
- control cast targeting and selection scope
- validate which fixtures a scene will affect

## Stage Tab

<img src="./media/screenshot-feature-lighting-stage.webp" data-source='{"url":"/login","next_url":"/lighting","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Lighting stage tab" style="width: 100%;height: auto;">

Stage is where scene playback and scene-level authoring happen.

A scene is a set of lighting patterns built either on a custom timeline or by choosing pre-defined patterns. Multiple scenes can be created and then triggered by Rules, either individually or layered.

Main areas:

- scene preview/stage area
- scene selector and `Add Scene`
- options/editor card for selected scene
- save and sync actions in the header

Scene options include:

- title
- duration (`seconds`, `minutes`, `frames`)
- end behavior (`stop`, `repeat`, `bounce`)
- pattern selection
- priority and blend mode
- cast scope/mask

When pattern is `Custom Timeline`, timeline editing is available:

- frame scrubber and frame stepping
- marker/tag pins
- clear frame action
- per-frame visual editing

Playback behavior:

- `Play` / `Stop` controls
- preview follows compiled output path
- updates reflect scene/pattern changes after compile

Selection controls (available on Stage in both timeline and non-timeline modes):

- click a pixel to select it
- click and drag on the stage to box-select multiple pixels
- hold `Shift` and click pixels to add/remove individual pixels from the current selection

## Runtime Tab

<img src="./media/screenshot-feature-lighting-runtime.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"lighting\"]","wait_for":"#lighting-tab-runtime"},{"action":"click","selector":"#lighting-tab-runtime","wait_for":"#lighting-tab-runtime-pane.show.active"}]}' alt="Lighting runtime tab" style="width: 100%;height: auto;">

Runtime shows what the ESP is doing right now, using the currently synced lighting data.

Use it to:

- confirm ESP connection/headless state
- check whether a scene is actively playing
- see the active scene list (or current scene fallback)
- monitor priority/blend/pause/order context for scene layering
- spot pixel overrides that are currently holding LEDs

## Layering and Scene Overlays (Simple Explanation)

Think of scenes as stacked transparent sheets of light.

- the base sheet is usually a background scene (for example `Attract`)
- higher-priority sheets can appear above it (for example `Game Mode`, then `Bonus`)
- blend mode decides what happens to lower sheets when a higher one starts:
  - `Stop Lower`: lower scene is stopped and does not continue
  - `Pause Lower`: lower scene is paused, then can continue when the top scene ends
  - `Play Over`: higher scene plays on top without stopping lower scenes

Direct pixel commands from Rules (like `LIGHT_PIXELS_SET`) are treated as immediate overrides, so those LEDs stay in the requested state until released. After release, scene-driven output resumes.

## Top Actions

- `Add Scene`: create a new scene
- `Play` / `Stop`: preview selected scene locally
- `Run selected scene on ESP`: start/stop selected scene on hardware
- `All Lights On/Off`: force all visible lights on to help locate fixtures quickly, then toggle back to normal preview
- `Sync Lighting`: compile and queue lighting sync to ESP
- `Save Changes`: persist local lighting config

If local and ESP revisions differ, an out-of-sync warning is shown.

## Custom Timeline

The custom timeline gives you exact control of which pixels are on/off and the colour at every specific frame.

## Timeline Tags

Frame tags are managed from the tag modal.

Rules:

- lowercase letters/numbers with `_` or `-`
- max length `64`
- unique per scene

Tags are available in Rules `Apply Lighting Scene` actions (`Start at: Tag`).

## Save and Sync Workflow

1. Build or edit scene in `Stage`.
2. Validate cast/fixture targeting in `Fixtures`.
3. Click `Save Changes`.
4. Click `Sync Lighting`.
5. Optionally open `Runtime` to confirm live ESP state.

## Pattern Reference

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

- [Rules](7-rules.md)
- [Playfield](9-layout.md)
- [Hardware](10-hardware.md)
