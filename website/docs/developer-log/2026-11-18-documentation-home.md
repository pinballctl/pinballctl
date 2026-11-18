# One home for project documentation

## Decision

Keep the authored website manual and developer documentation in `website/docs/`.
Separate current instructions, dated decisions, release notes and physical build
notes so readers can tell what kind of information they are looking at.

The Developer Guide brings together setup, testing, releases, website maintenance,
firmware checks and Godot/backglass development. The Developer Log gives decisions
a date and topic tags. Tags collect connected notes across time; explicit related
entries connect follow-ups without requiring a full discussion transcript.

## Why this changed

The repository contained both the current website and an older generated manual,
plus instructions spread across the root README and component folders. Some
instructions still described the period before GitHub Pages publication moved to
this repository. Generated HTML and Python bytecode obscured the authored sources.

## What the layout now means

- `website/docs/` is the website documentation source. Reading order is configured separately from filenames.
- Component READMEs point to the relevant guides; the root README remains an introduction and quick start.
- `website/utils/` owns the website build, Markdown rendering and screenshot capture.
- Generated HTML stays under ignored `dist/`; old public URLs and source bookmarks retain compatibility mappings.
- The old-domain holding artifact remains in use. Temporary homepage review snapshots do not belong in the source tree.
- Test-bench engineering files and CAD preview paths remain intact. They are design work, not disposable website output.

## Publication and limits

GitHub Pages publishes the checked `dist/site/` artifact on pushes to `main`.
The workflow also produces the separate old-domain holding artifact. This cleanup
does not change device firmware, machine configuration, hardware validation or DNS.

The initial log entries are reconstructed from repository records and this layout
decision. Private task briefs and discussions are not automatically published.
Current instructions and the check commands live in the
[website development guide](../developer-guide/website.md).
