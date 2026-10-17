# Maintainer guide

Run commands below from the repository root unless stated otherwise. Public user
documentation lives in `docs/pages/`; this guide is for repository maintenance and
is not included in the current generated documentation site.

## Layout and development

- `src/pinballctl/`: application, bridge and web UI.
- `src/firmware/`: ESP firmware; build with `utils/build-firmware.sh` so artifacts
  are registered in the application UI.
- `src/godot/`: host media runtime; `backglass/`: separate Godot scene project.
- `website/` and `docs/`: imported public-site sources; see the import record below.
- `tests/` and `utils/`: verification and development/release tools.
- `dist/`: ignored release and firmware artifacts; preserve files you still need.
- `build/`: disposable Python packaging output.
- `.local/`: ignored private notes. Environments, caches and `gunicorn.ctl` are
  local runtime/development files, not source. Do not delete an active socket.

## Versioning and validation

Keep `pyproject.toml` and `src/pinballctl/__init__.py` versions aligned, and add a
matching section to `CHANGELOG.md`. Firmware has its own version in
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
- Version mismatch: check package metadata, `__version__`, changelog and tag.
- Godot runtime: currently requires a checkout containing `src/godot` and a local
  Godot installation; the Python wheel does not bundle that project.

No automatic release/Pages workflow is installed by the repository import.
PyPI publishing is not part of the current release flow.

## Repository import — 2026-10-17

The controller keeps its existing source layout. Three companion projects are
imported into dedicated folders, with their original commits preserved as merge
parents rather than squashed or rewritten.

| Folder | Original repository | Imported `main` commit |
| --- | --- | --- |
| `backglass/` | https://github.com/pinballctl/pinballctl-backglass | `c1892168d6d3ea92e2fcd24f65da05de405115f6` |
| `website/` | https://github.com/pinballctl/pinballctl-website | `c36821dc5360493825e70e6bb2f8f2db086faa4b` |
| `docs/` | https://github.com/pinballctl/pinballctl-docs | `3bdc75c5f48bff4543d6c3499ca58ed038c64be0` |

Each source repository had only `main` and no tags at import. Local heads matched
GitHub heads and all source working trees were clean. Original commit IDs and
authorship remain intact. Before the import, paths in those histories remain
relative to their original repository roots. To inspect old history, use
`git log <imported-commit>` or `git show <imported-commit>:<original-path>`.

### Deployment stays unchanged

- `https://www.pinballctl.com/` still publishes from the root of `main` in
  `pinballctl-website`.
- `https://docs.pinballctl.com/` still publishes from the root of `main` in
  `pinballctl-docs`.
- No repositories are archived, no DNS/Pages settings change, and no deployment
  workflows are added to the controller repository.
- Imported `CNAME` files and generated site pages are retained for reference and
  local previews. Their presence here does not configure a Pages deployment.
- New work can happen here. Any urgent live-site fix must still be applied to the
  original publishing repository until deployment is explicitly migrated. Avoid
  editing the same content independently in both locations.

Website redesign, incorporating docs into the website, domain migration and old
URL redirects are deferred. Do not enable Pages from this repository's `docs/`
folder as part of this import.

### Local development

From the repository root:

```sh
## Build documentation using the imported website's shared styling.
.venv/bin/python docs/utils/build-docs.py

## Preview the existing static sites independently.
python3 -m http.server 8081 --directory website
python3 -m http.server 8082 --directory docs
```

Open `backglass/project.godot` in Godot to edit/export the backglass scene. The
controller's Godot host remains in `src/godot/`. Both retain separate project
files and can be built independently.

Docs screenshot tools can connect to a running application and write generated
images. `docs/utils/rebuild-all.py` deletes existing generated media before
rebuilding; it is not needed just to preview the imported site.

### Generated files and packaging

The backglass history contains editor caches and an exported `.pck`. They are
excluded from the new tracked tree and ignored locally; their historical commits
are deliberately preserved. No credentials were populated in the imported Godot
export-credentials settings.

Website/docs rendered pages and assets remain tracked during this transition to
preserve an exact site baseline. A later website build pipeline can separate
sources from output. Application package manifests explicitly exclude
`website/`, `docs/` and `backglass/`.

### Review and commit

The import is prepared with a pending multi-parent merge and staged files.
Complete it with a normal merge commit, not a squash, to retain all three source
histories in the main branch. The temporary local `import-*` remote-tracking refs
are inspection aids; the merge parents preserve the history after committing.
