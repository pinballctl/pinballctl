# Developer Guide

Use this guide to work on Pinball CTL from a checkout. The [user guide](../user-guide/getting-started.md)
covers installing and operating a machine; [Advanced Reference](../technical-notes/readme.md)
covers architecture and runtime contracts.

## Working on the project

- [Development and testing](development.md): source layout, Python setup, tests and firmware builds.
- [Website and documentation](website.md): one source tree, preview, screenshots and GitHub Pages.
- [Releases](releases.md): versions, packages and publication.
- [Firmware regression checks](firmware-checks.md): physical input/output checks after firmware changes.
- [Godot media runtime](godot-runtime.md): host responsibilities and command examples.
- [Backglass development](backglass.md): presentation integration, preview and export.
- [Backglass asset provenance](backglass-assets.md): how the bundled art and audio were made.
- [Writing the Developer Log](writing-the-log.md): dated decisions, tags and related entries.

Read repository `AGENTS.md` before using an assistant to change the project. Keep
changes focused and preserve unrelated staged work. Contribution permissions and
publishing decisions belong to the project owner.

## Where information belongs

Current instructions live in this guide. Runtime contracts live in Advanced
Reference. Release changes live in the [Changelog](../changelog.md). Dated decisions
and the reasons behind them live in the [Developer Log](../developer-log/index.md).
Build notes describe physical project work and its validation status.

All authored website documentation lives under `website/docs/`. Component READMEs
are short signposts. The test-bench CAD workspace remains at `docs/design/test-bench/`,
with its local engineering READMEs and preview images preserved so existing CAD
scripts and work in progress continue to work. It is not a second documentation site.
