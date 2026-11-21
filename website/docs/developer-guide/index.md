# Developer Guide

Use this guide to work on Pinball CTL from a checkout. The [user guide](../user-guide/getting-started.md)
covers installing and operating a machine; [Advanced Reference](../technical-notes/readme.md)
covers architecture and runtime contracts.

## Working on the project

- [Development and testing](development.md): source layout, Python setup, tests and firmware builds.
- [Releases](releases.md): versions, packages and publication.
- [Firmware regression checks](firmware-checks.md): physical input/output checks after firmware changes.
- [Godot media runtime](godot-runtime.md): host responsibilities and command examples.
- [Backglass development](backglass.md): presentation integration, preview and export.
- [Backglass asset provenance](backglass-assets.md): how the bundled art and audio were made.

Read repository `AGENTS.md` before using an assistant to change the project. Keep
changes focused and preserve unrelated staged work. Contribution permissions and
publishing decisions belong to the project owner.

## Where information belongs

Current instructions live in this guide. Runtime contracts live in Advanced
Reference. The Developer Notes menu groups topic pages such as
[Test Bench](../developer-notes/test-bench.md) and
[Website](../developer-notes/website-and-search.md), including design decisions,
evidence, validation limits and next steps.
Build notes describe the physical development platform.

All authored website documentation, including test-bench notes, lives under
`website/docs/`. Component READMEs are short signposts. Documentation images live
in `website/assets/docs/` and are copied into the generated site during the build.
Current test-bench engineering sources and drawing generators live in
`website/design/test-bench/`; the maintained instructions are on the
[Test Bench](../developer-notes/test-bench.md) topic pages.
