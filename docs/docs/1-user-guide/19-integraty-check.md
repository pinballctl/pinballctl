# Integrity Check

Integrity Check audits cross-module dependencies and helps you safely resolve orphaned references.

<img src="./media/screenshot-feature-integrity-check.webp" data-source='{"url":"/login","next_url":"/integrity","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Integrity Check feature overview" style="width: 100%;height: auto;">

## What It Checks

Integrity Check scans references across:

- hardware mapping
- rules
- playfield layout
- lighting
- audio
- scoring

It reports:

- `OK` items with valid references
- `Errors` for orphaned references
- `Unused` items with zero references

## Page Structure

Top actions:

- `Run Check`
- `Resolve All` (enabled only when actionable issues exist)

Filters:

- status tabs: `All`, `OK`, `Errors`, `Unused`
- `Kind`
- `Keyword`

Results table columns:

- status
- kind
- name
- details / used by
- per-row `Resolve`

## Resolve Behavior

`Resolve` (row):

- opens shared confirmation modal
- resolves only that selected issue
- refreshes report after apply

`Resolve All`:

- opens shared confirmation modal
- applies all fixable issues
- refreshes report and shows a formatted applied-changes report

## Compile + Sync Notes

When cleanup updates source configs, Integrity Check also rebuilds affected runtime artifacts using each module's own compile path:

- rules changes -> rebuild `rules.pd` + `rules_meta.json`
- lighting changes -> rebuild `lighting.pd` + `lighting.compiled.json` + `lighting_meta.json`

This marks artifacts as changed locally, but does not mark them as synced to ESP. You still need to run the relevant sync step.

## Typical Workflow

1. Open `Integrity Check`.
2. Click `Run Check`.
3. Filter by `Errors` (or `Unused`) and inspect `Used By`.
4. Resolve individually with row `Resolve` or bulk with `Resolve All`.
5. Re-run check to confirm clean state.
6. Sync affected modules to ESP.

## Related Features

- [Hardware](7-hardware.md)
- [Rules](7.1-rules.md)
- [Lighting](8-lighting.md)
- [Audio](17-audio.md)
- [Scoring](10-scoring.md)
- [ESPLink](11-esplink.md)
