# Scoring

Give your game clear rewards, beginning with one event and one fixed award. Add progressive rules and combos only after you can verify the simple award.

## Before you start

Have a known input/event, saved mapping and running Pi runtime. Use a controlled test session and preserve real score history before experiments.

## Try it step by step

1. Open **Base Points** and add/edit one row through its Settings sliders panel. Choose Hardware or Event, the observed trigger and a small point value. **Expected:** the row summary names the intended source and award.

2. Choose **Save Changes**. Trigger that input/event once in a controlled test and inspect the scoring result/event log. **Expected:** one matching award; verify the actual score rather than a dashboard demo value.

3. Only after that works, configure one **Scoring Rules** progression or **Combos** sequence. Read its hit count, time window, cap/multiplier and optional emitted event. **Expected:** its thresholds are explicit and do not duplicate an existing fixed award unintentionally.

4. Save, repeat the required sequence and test the reset/timeout case. **Expected:** the award occurs at the intended threshold and does not persist into an unrelated sequence.

<img src="./media/screenshot-feature-scoring.webp" data-source='{"url":"/login","next_url":"/scoring","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Scoring base points tab" style="width: 100%;height: auto;">

**Screen guide:** 1. Base Points defines a direct award. 2. The Settings sliders panel edits a row. 3. Save Changes persists the whole scoring configuration.

## Helpful checks

A reward event from a Wizard needs an explicit Scoring row if it should award points. Inspect both the triggering and emitted event before adding a second matching award.

**Safety:** Simulated events can activate real Rules as well as scoring. Keep coil power disconnected for authoring tests and back up score/history data before destructive experiments.

## If the result is different

If no award appears, check exact event/source, saved configuration and runtime/session state. If doubled, inspect overlapping Base Points, progressive rules, combos and emitted events before reducing the point value.

## Continue your build

Next: [Events](27-events.md), [Rules](7.1-rules.md), [Rules Wizard](24-rules-wizards.md), [Logs](14-logs.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## Page Structure

Scoring is split into three tabs:

1. `Base Points`
2. `Scoring Rules`
3. `Combos`

Base Points, Scoring Rules and Combos use standard tables, with aligned summary columns. Use the **Settings** sliders icon at the far right of a base-points row, rule or combo to edit it in a right-side panel. Closing keeps your unsaved draft; **Save Changes** in the panel saves the whole scoring configuration using the same operation as the page button. Base Points uses the same sliders settings panel, with source, trigger, points and notes shown as a read-only table summary.

## Base Points Tab



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

<img src="./media/screenshot-feature-scoring-scoring-rules.webp" data-source='{"url":"/login","next_url":"/scoring","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#tab-rules-btn"},{"action":"click","selector":"[data-rule-toggle]","wait_for":"#scoring-settings.show"}]}' alt="Scoring rules tab" style="width: 100%;height: auto;">

Use this tab for progressive scoring logic.

Choose the **Settings** sliders icon beside a scoring rule to open its right-side panel. The list stays visible behind a blurred backdrop. The panel supports:

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

<img src="./media/screenshot-feature-scoring-combos.webp" data-source='{"url":"/login","next_url":"/scoring","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#tab-combos-btn"},{"action":"click","selector":"[data-combo-toggle]","wait_for":"#scoring-settings.show"}]}' alt="Scoring combos tab" style="width: 100%;height: auto;">

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

- [Rules](7.1-rules.md)
- [Lighting](8-lighting.md)
- [Playfield](9-layout.md)


## Game ownership and per-player state

Game Management owns session lifecycle, credits, logical turns and player changes. Scoring applies this page’s award rules, combo progress and multipliers independently for the committed current player. Game Management asks Scoring to finalise the outgoing turn before advancing. Scoring history/high scores are durable owner documents in the shared management database, not a separate game lifecycle. Configure the fixed end-of-turn bonus in Game Management settings. Starting or ending a game by manually emitting a result event is no longer supported. See [Game Management](26-game-management.md).
