# Integrity Check

Find broken references between modules and review each proposed cleanup before applying it. A clean reference report does not replace a physical machine test.

## Before you start

Save work and create a project backup before applying cleanup. Know which assets/rules you intend to keep; an Unused item is not automatically unwanted.

## Try it step by step

1. Choose **Run Check**. Filter by Errors or a specific kind/name. **Expected:** each issue names the affected item and its references.

2. Read details/Used By and inspect the source module. **Expected:** you can decide whether the right fix is restoring a missing dependency or removing the reference.

3. Use per-row **Resolve** only after reviewing the confirmation. Use **Resolve All** only if every proposed cleanup is intended. **Expected:** confirmed changes are applied and a result is shown.

4. Rerun the check, inspect affected configurations and sync changed artifacts deliberately. **Expected:** references are corrected; rebuilt local artifacts are not falsely treated as deployed.

<img src="./media/screenshot-feature-integrity-check.webp" data-source='{"url":"/login","next_url":"/integrity","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Integrity Check feature overview" style="width: 100%;height: auto;">

**Screen guide:** 1. Status/kind filters narrow the report. 2. Used By explains dependency impact. 3. Resolve requires review; rerun and sync are separate steps.

## Helpful checks

Resolve one issue first and inspect its effect. A deliberately retained asset may be Unused until a later rule references it.

**Safety:** Cleanup can change authored configurations. Back up first; never assume cleanup or a rebuild arms outputs or safely deploys to the ESP.

## If the result is different

If an issue returns, check whether another saved reference still points to the missing item. For build/sync failures, preserve the error and inspect the owning module rather than repeatedly using Resolve All.

## Continue your build

Next: [Backup / Restore](25-backup-restore.md), [Rules](7.1-rules.md), [Hardware](7-hardware.md), [Logs](14-logs.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

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
