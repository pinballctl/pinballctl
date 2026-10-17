# Service Log

Service Log is the feature for machine service and maintenance records.

It is focused on physical maintenance history rather than runtime diagnostics.

<img src="./media/screenshot-feature-servicelog.webp" data-source='{"url":"/login","next_url":"/service","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Service Log feature overview" style="width: 100%;height: auto;">

## What This Feature Does

It records maintenance and repair actions so users and engineers can track what was serviced, when, and why.

## Top Controls

- `New Entry`

Creates a new maintenance/service record.

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

`Edit` button appears when an entry is selected.

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
