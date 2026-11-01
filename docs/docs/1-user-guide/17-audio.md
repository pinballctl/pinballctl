# Audio

Add sound feedback to your game, one cue at a time. Keep the asset, its playback cue and the rule that requests it easy to distinguish.

## Before you start

Have a supported sound file, a working host audio device and a safe listening volume. Keep coil power disconnected when testing event-driven cues.

## Try it step by step

1. In **Library**, choose **Upload Asset** and select the sound. **Expected:** the asset appears in the library or an explicit upload/format error is reported.

2. Create/edit a cue in **Cues**, select the asset and choose its playback behaviour. **Expected:** the cue references an existing file and has a deliberate loop/stop policy.

3. Check **Outputs** and preview at low volume. **Expected:** sound is heard from the intended device; a successful file upload alone does not establish audio output.

4. Choose **Save Changes**, then add **Play Cue** to a test rule using the observed input/event. **Expected:** one input produces the intended cue.

5. Check **Audio Usage Map** before removing or duplicating assets. **Expected:** references can be understood without breaking an existing cue.

<img src="./media/screenshot-feature-audio-library.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Audio library tab" style="width: 100%;height: auto;">

**Screen guide:** 1. Library stores files. 2. Cues define playback behaviour. 3. Outputs verifies routing; the Usage Map helps trace references.

## Helpful checks

Test a short one-shot cue before loops or overlapping audio. Use a stable device choice suitable for the service account, not only your desktop login.

**Safety:** Start with low amplifier volume. Simulated inputs can run other rules; isolate the test and keep powered outputs disabled.

## If the result is different

If preview is silent, check file, output selection, mute/volume and service audio permissions before changing the rule. If preview works but the input does not, inspect the trigger, enabled/saved rule and cue reference.

## Continue your build

Next: [Rules](7.1-rules.md), [Events](27-events.md), [Media](18-media.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## Page Structure

Audio is split into four tabs:

1. `Library`
2. `Cues`
3. `Outputs`
4. `Audio Usage Map`

## Library Tab



Library is where audio files are managed.

Use the sliders icon at the right of an asset row to edit its title in the side panel. **Save Title** applies the change; closing or cancelling leaves the title unchanged.

<img src="./media/screenshot-audio-asset-settings.webp" data-source='{"url":"/login","next_url":"/audio/","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"[data-audio-asset-name-edit]","wait_for":"#audio-asset-settings.show"}]}' alt="Audio asset title settings" style="width: 100%;height: auto;">

Use **Upload Asset** beside **Save Changes** to open the upload dialog from any tab. Drop files into the dialog or choose files; upload progress appears there. Assets remain available in Library.

Key behavior:

- drag-and-drop multi-file upload
- per-row inline player
- friendly name editing
- sort by name, added date, and duration
- usage count pills per asset

Notes:

- if no friendly name is set, UI derives one from filename
- very short assets are shown with fractional-second durations

## Cues Tab

<img src="./media/screenshot-feature-audio-cues.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#audio-tab-cues"}]}' alt="Audio cues tab" style="width: 100%;height: auto;">

Cues define how assets play at runtime.

Per cue settings include:

- cue name
- linked library asset
- output target
- bus (`SFX`, `Music`, `Voice`, `Ambient`)
- volume (`0.0` to `2.0`)
- loop toggle
- repeat count
- cooldown (ms)

Editor behavior:

- `Save Changes` enables only when there are real changes
- unsaved exit prompts use the shared confirm flow
- preview playback goes through backend routing for runtime-accurate output targeting

## Outputs Tab

<img src="./media/screenshot-feature-audio-outputs.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#audio-tab-outputs"}]}' alt="Audio outputs tab" style="width: 100%;height: auto;">

Outputs shows devices and runtime playback state.

Key behavior:

- detected playback devices for current host
- active runtime entries and orphan entries
- stop actions for active/orphan playback processes
- environment checks for audio backend/library readiness

## Audio Usage Map Tab

<img src="./media/screenshot-feature-audio-audio-usage-map.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#audio-tab-events"}]}' alt="Audio usage map tab" style="width: 100%;height: auto;">

Audio Usage Map is a read-only reference of where assets are used.

Use it for:

- audit and cleanup
- verifying reuse before adding duplicate assets
- debugging event-to-cue mappings quickly

## Runtime Model

Audio subscribes to Pi-side event flow.

In practice:

- events can trigger cues
- multiple systems can reference the same cue
- behavior stays centrally configurable from Audio

## Typical Workflow

1. Choose **Upload Asset** to upload audio files.
2. Define cue behavior in `Cues`.
3. Validate devices and playback in `Outputs`.
4. Confirm usage and reuse in `Audio Usage Map`.

## Related Features

- [Rules](7.1-rules.md)
- [Scoring](10-scoring.md)
- [Playfield](9-layout.md)
- [Settings](16-settings.md)
