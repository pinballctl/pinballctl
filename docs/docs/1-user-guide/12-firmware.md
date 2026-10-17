# Firmware

Firmware manages available firmware version lists and local version lifecycle.

<img src="./media/screenshot-feature-firmware.webp" data-source='{"url":"/login","next_url":"/firmware","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Firmware feature overview" style="width: 100%;height: auto;">

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
- [Hardware](10-hardware.md)
- [Service Log](13-service-log.md)
