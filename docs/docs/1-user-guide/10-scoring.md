# Scoring

Scoring is the feature for designing how points are awarded during gameplay.

It supports fixed points, progressive hit ramps, and combo-based awards.

## Page Structure

Scoring is split into three tabs:

1. `Base Points`
2. `Scoring Rules`
3. `Combos`

## Base Points Tab

<img src="./media/screenshot-feature-scoring.webp" data-source='{"url":"/login","next_url":"/scoring","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Scoring base points tab" style="width: 100%;height: auto;">

Use this tab for straightforward score awards.

Each row configures:

- Source mode (`Hardware` or `Event`)
- Trigger (hardware event type or event name)
- Point value
- Optional notes

Typical uses:

- baseline points for common switch hits
- points for named gameplay events
- initial score model before advanced rules

## Scoring Rules Tab

<img src="./media/screenshot-feature-scoring-scoring-rules.webp" data-source='{"url":"/login","next_url":"/scoring","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Scoring rules tab" style="width: 100%;height: auto;">

Use this tab for progressive scoring logic.

Rules are collapsible cards that support:

- source and trigger setup
- minimum hits
- optional hit window (`min hits within ms`)
- base points and points-per-hit scaling
- bonus cap and cooloff behavior
- optional emitted event

Example ramp model:

- `minHits = 1`
- `basePoints = 20`
- `pointsPerHit = 10`
- `cooloffMs = 1500`
- `cooloffStep = 1`

This rewards fast repeat hits while decaying value when play slows.

## Combos Tab

<img src="./media/screenshot-feature-scoring-combos.webp" data-source='{"url":"/login","next_url":"/scoring","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Scoring combos tab" style="width: 100%;height: auto;">

Use this tab for multi-step scoring sequences.

Each combo supports:

- ordered or any-order matching
- step time window
- award points
- optional temporary multiplier
- optional emitted event

Each step can use:

- `Hardware`: button source + button event trigger
- `Event`: fired event name trigger

Example ordered combo:

- step 1: left lane event
- step 2: right lane event
- step 3: top target event
- award: 300 points
- multiplier: x1.5 for 8 seconds

## Save and Runtime Behavior

- Changes stay staged until you click `Save Changes`.
- Saved scoring config is persisted in instance data.
- Runtime scoring listens to matching inputs and awards points in real time.

## Integration Notes

Scoring integrates with the event system.

This allows scoring to:

- react to events fired by other modules
- emit events for Rules and Lighting
- participate in mode-level gameplay flows

## Practical Workflow

1. Add baseline rows in `Base Points`.
2. Add scaling rules in `Scoring Rules`.
3. Add sequence rewards in `Combos`.
4. Save and test in gameplay or emulation.
5. Tune values based on game feel.

## Related Pages

- [Rules](7-rules.md)
- [Lighting](8-lighting.md)
- [Playfield](9-layout.md)
