# Releases

Run commands from the repository root. Website publication is described in [Website](../developer-notes/website-and-search.md#publishing).

For published versions and release notes, see [GitHub Releases](https://github.com/pinballctl/pinballctl/releases).

## Versioning and validation

Keep `pyproject.toml` and `src/pinballctl/__init__.py` versions aligned. Summarise
release changes in the GitHub release notes when preparing a release. Firmware has its own version in
`src/firmware/src/version.h`, updated by the firmware build utility.

Before a release, run relevant Python, UI and native firmware tests. Build a wheel
and source distribution and check that application templates/static files are
included, while instance data, caches and companion projects are excluded.
Review the diff and make the release commit before creating its tag.

## Building and publishing

Required tools: Python 3.11+, the `build` package, Git and an authenticated GitHub
CLI (`gh auth login`). Release operations are separate from the public CLI.

Build packages without deleting firmware artifacts:

```sh
python -m build --outdir dist/releases/vX.Y.Z
```

For reproducible releases, build in a clean checkout or an isolated export of the
reviewed commit. Do not package machine-local configuration or generated caches.

The legacy publishing helper is `utils/create-release.sh` (not
`utils/build-release.sh`). Run `--help` for its supported options. It builds,
creates/pushes tags and publishes to GitHub; it defaults to a **prerelease**.
For a stable release its flags are `--prerelease 0 --latest 1`.

**The current helper deletes the entire `dist/` directory before building.**
Do not use it when preserving local firmware/release artifacts. The separate
build/tag/upload flow below avoids that deletion:

1. Bump versions and write release notes, then validate and commit.
2. Build the packages from that exact commit into `dist/releases/vX.Y.Z/`.
3. Add the matching firmware artifacts and SHA256 checksums if applicable.
4. Create an annotated `vX.Y.Z` tag on the reviewed commit and push the intended
   branch and tag when publishing is authorized.
5. Use `gh release create vX.Y.Z <explicit-asset-paths> --verify-tag
   --notes-file <release-notes-file> --latest` for a stable release. Use
   `--prerelease` instead of `--latest` for a prerelease.
6. Verify the published tag target, notes and downloaded asset checksums.

Prefer explicit asset paths to `dist/*`, which also contains firmware and release
subdirectories. Existing releases should not be overwritten without an explicit
request. The helper's `--replace 1` uploads assets with `--clobber`; it does not
regenerate release notes. Custom notes can be supplied with `--notes-file`,
`--notes`, or `--generate 1`.

Troubleshooting:

- Authentication errors: check `gh auth status` before publishing.
- Existing release: inspect it before deciding whether to replace assets.
- Missing UI: inspect the wheel and ensure package-data/MANIFEST rules include
  the current `src/pinballctl/app/` layout.
- Version mismatch: check package metadata, `__version__`, release notes and tag.
- Godot runtime: currently requires a checkout containing `src/godot` and a local
  Godot installation; the Python wheel does not bundle that project.

Website deployment uses the separate GitHub Pages workflow. PyPI publishing is not part of the current application release flow.
