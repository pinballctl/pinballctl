# Audio

Audio manages sound assets, output routing, and cue-based playback behavior.

It is designed so gameplay systems can trigger predictable audio without embedding sound logic in ESP firmware.

## Page Structure

Audio is split into four tabs:

1. `Library`
2. `Cues`
3. `Outputs`
4. `Audio Usage Map`

## Library Tab

<img src="./media/screenshot-feature-audio-library.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Audio library tab" style="width: 100%;height: auto;">

Library is where audio files are uploaded and managed.

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

<img src="./media/screenshot-feature-audio-cues.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Audio cues tab" style="width: 100%;height: auto;">

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

<img src="./media/screenshot-feature-audio-outputs.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Audio outputs tab" style="width: 100%;height: auto;">

Outputs shows devices and runtime playback state.

Key behavior:

- detected playback devices for current host
- active runtime entries and orphan entries
- stop actions for active/orphan playback processes
- environment checks for audio backend/library readiness

## Audio Usage Map Tab

<img src="./media/screenshot-feature-audio-audio-usage-map.webp" data-source='{"url":"/login","next_url":"/audio","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Audio usage map tab" style="width: 100%;height: auto;">

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

1. Upload assets in `Library`.
2. Define cue behavior in `Cues`.
3. Validate devices and playback in `Outputs`.
4. Confirm usage and reuse in `Audio Usage Map`.

## Related Features

- [Rules](7-rules.md)
- [Scoring](7.1-scoring.md)
- [Playfield](9-layout.md)
- [Settings](16-settings.md)
