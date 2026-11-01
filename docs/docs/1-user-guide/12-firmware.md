# Firmware

Keep controller firmware compatible with the Pi software and its safety checks. Download an intended image here; applying it to the ESP is a separate ESPLink operation.

## Before you start

Know the exact controller model, application revision and intended firmware source. Use a trusted manifest and perform updates outside gameplay with output power removed.

## Try it step by step

1. Open **Firmware**, choose **Default** or a trusted **Custom URL**, then **Load** where required. **Expected:** a version list or explicit fetch error.

2. Read the version notes, source and status. Select the image intended for your board and application revision. **Expected:** a deliberate choice; Latest alone is not evidence of compatibility.

3. Choose **Download** for that version. **Expected:** the image becomes locally available; this does not flash the controller.

4. Open **ESPLink**, confirm the intended device and apply the local version. Watch the console and then verify live identity/version after reconnect. **Expected:** the intended firmware is running, or a clear failure that needs recovery.

<img src="./media/screenshot-feature-firmware.webp" data-source='{"url":"/login","next_url":"/firmware","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Firmware feature overview" style="width: 100%;height: auto;">

**Screen guide:** 1. Source selects the manifest. 2. Version notes describe the image. 3. Downloaded status means locally cached, not installed on the ESP.

## Helpful checks

Keep a record of the firmware version alongside the installed Git revision and a project backup. Removing a local download does not revert firmware already running on the controller.

**Safety:** Do not interrupt flashing or apply a binary for another board. Firmware updates are maintenance operations, not a way to clear a fault during a game.

## If the result is different

If the list is empty, check source/network and fetch errors. If download succeeds but the device version is unchanged, inspect ESPLink apply results; downloading alone never updates the ESP.

## Continue your build

Next: [ESPLink](11-esplink.md), [Service Log](13-service-log.md), [Backup / Restore](25-backup-restore.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## What This Feature Does

It provides a controlled view of firmware versions and allows you to download/remove local versions for deployment.

## Source Controls

At the top of the card:

- Source selector:
  - `Default`
  - `Custom URL`
- Remote URL input (shown in custom mode)
- `Load` for remote manifest fetch

Status line shows:

- latest version badge
- source label
- version count summary

## Versions Table

Columns:

- Version
- Date
- Notes
- Size
- Status
- Action

Status badges include:

- Downloaded (local)
- Remote

Row actions:

- `Download` for remote-only versions
- `Remove` for local versions

## Footer Action

- `Remove All Local Versions`

Use this to clear local cache when resetting firmware set.

## Data Behaviour

Firmware view merges local and selected-remote manifests.

Ordering:

- newest first by date/version sort

Formatting:

- dates shown in readable UK format
- sizes shown as B/KB/MB

## Official Release Usage

Updates from official Pinball CTL releases are available and listed here.

Typical workflow:

1. load default source
2. review available versions/notes
3. download required local version
4. apply from ESPLink

## Practical Examples

### Use official default feed

- keep Source = Default
- review latest badge
- download selected stable version

### Temporary custom release source

- switch Source = Custom URL
- enter manifest URL
- Load and review
- download targeted version

## Related Features

- [ESPLink](11-esplink.md)
- [Hardware](7-hardware.md)
- [Service Log](13-service-log.md)
