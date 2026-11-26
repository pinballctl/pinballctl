# Developer Guide

Use this guide to work on Pinball CTL from a checkout, understand the runtime and verify changes on the bench. The [user guide](../user-guide/getting-started.md) covers installing and operating a machine.

<span id="working-on-the-project"></span>

## Development & Releases

- [Development Platform](../build-notes/development-platform.md) covers the local checkout, Pi and ESP32-S3 bench.
- [Development and testing](development.md) covers source layout, Python setup, tests and firmware builds.
- [Releases](releases.md) covers versions, packages and publication.
- [Website](../developer-notes/website-and-search.md) covers the site build, validation and publication.

Read repository `AGENTS.md` before using an assistant to change the project. Keep
changes focused and preserve unrelated staged work. Contribution permissions and
publishing decisions belong to the project owner.

## Architecture & APIs

Start with the [System Overview](../technical-notes/index.md) to see how the Pi, ESP32-S3 and web interface fit together. The [App Layout](../technical-notes/app-layout.md), [Modules API Surface](../technical-notes/modules-api-surface.md) and [Game and Ball Ownership](../technical-notes/management-ownership.md) cover the code, interfaces and state that each component owns.

## Bridge, Firmware & Coil Safety

Use [Bridge Event Flow](../technical-notes/bridge-event-flow.md) to trace a switch event, the [Bridge Protocol](../technical-notes/bridge-protocol.md) to inspect serial messages and [Bridge Performance](../technical-notes/bridge-performance.md) to investigate timing. [Firmware Checks](firmware-checks.md) and [Coil Safety](../technical-notes/coil-safety.md) cover verification and controller safeguards.

## Godot & Backglass

The [Godot media runtime](godot-runtime.md) guide covers host responsibilities and commands. [Backglass development](backglass.md) covers preview, export and integration, and [Asset Provenance](backglass-assets.md) credits the sample’s artwork and animation.

## Test Bench & Hardware

The [Test Bench](../developer-notes/test-bench.md) documents the layout, construction, wiring and components used for bench work. [Hardware Inventory](../developer-notes/hardware-inventory.md) records the project machine’s configured hardware mapping.

## Where information belongs

Keep development instructions and runtime contracts in their existing source directories. Record design decisions, evidence, validation limits and next steps on the relevant topic page.

All authored website documentation, including test-bench notes, lives under
`media/website/docs/`. Component READMEs are short signposts. Documentation images live
in `media/website/assets/docs/` and are copied into the generated site during the build.
Current test-bench engineering sources and drawing generators live in
`media/website/design/test-bench/`; the maintained instructions are on the
[Test Bench](../developer-notes/test-bench.md) topic pages.
