# Service Log

Record what changed on the physical machine, when it changed and what you checked afterwards. Use runtime Logs separately for event and process diagnostics.

## Before you start

Have the maintenance details and any appropriate attachments ready. Avoid personal or secret information in records intended for sharing.

## Try it step by step

1. Choose **New Entry** and enter the required engineer/operator, service type, title and work description. **Expected:** the entry describes a specific maintenance action.

2. Add parts, outcome, follow-up and relevant attachments, then **Save Entry**. **Expected:** the entry appears in the list and its details can be reopened.

3. Use type/date filters to find it, or open **Entry settings** to correct it. **Expected:** the saved record reflects what actually happened, including incomplete follow-up.

<img src="./media/screenshot-feature-servicelog.webp" data-source='{"url":"/login","next_url":"/service","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Service Log feature overview" style="width: 100%;height: auto;">

**Screen guide:** 1. Filters select the history. 2. The list selects a record. 3. Entry settings opens the editor without confusing service history with live runtime logs.

## Helpful checks

Record the installed application revision and firmware version when the work involves an update. Distinguish a completed test from a test still required.

**Safety:** Disconnect power before physical service. A service note is not an interlock or proof that a replaced coil/driver is safe.

## If the result is different

If a record is missing, clear filters and check save feedback. For an attachment failure, check allowed type/count and service write permissions; preserve the original file.

## Continue your build

Next: [Logs](14-logs.md), [Backup / Restore](25-backup-restore.md), [Hardware](7-hardware.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## What This Feature Does

It records maintenance and repair actions so users and engineers can track what was serviced, when, and why.

## Top Controls

- `New Entry`

Opens a right-side entry form. The **Entry settings** sliders icon uses the same panel for existing records. Required fields, attachments, Save and Cancel retain their existing behaviour.

## Filter Controls

- Service type filter
- Date `From`
- Date `To`
- `Apply`
- `Clear`

Service types:

- Service
- Repair
- Recall
- Warranty

## Main Layout

Two-pane layout:

- left: Entries list + count badge
- right: Entry details panel

Details panel shows:

- title/meta/type
- work summary
- parts replaced
- outcome
- follow-up notes
- attachments

The **Entry settings** sliders button appears when an entry is selected.

## New/Edit Entry Modal

Fields:

- Engineer (required)
- Service type (required)
- Title (required)
- Work description (required)
- Parts replaced
- Outcome / result
- Follow-up notes
- Attachments (up to 5 files)

Attachment note in UI:

- PNG, JPG, PDF, DOCX

Modal actions:

- Cancel
- Save Entry

## Typical Workflow

1. Create entry after physical work is complete.
2. Capture parts/outcome details.
3. Add supporting attachments.
4. Save and verify details in right panel.

## Practical Examples

### Weekly cleaning log

Record:

- engineer/operator
- service type = Service
- checklist summary
- follow-up for next clean interval

### Coil replacement record

Record:

- type = Repair
- replaced part ID
- result after test
- attach invoice/photo

## Related Features

- [Dashboard](5-dashboard.md)
- [Logs](14-logs.md)
- [Settings](16-settings.md)

## Entry editor

<img src="./media/screenshot-service-entry-panel.webp" data-source='{"url":"/login","next_url":"/service","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"[data-action=\"new\"]","wait_for":"#service-new-modal.show"}]}' alt="Service entry settings panel" style="width:100%;height:auto;">
