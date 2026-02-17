# MAINTAINER GUIDE — pinballctl

This document is for project maintainers. It covers versioning, building, and publishing releases using the **maintainer-only** script: `utils/build-release.sh`.

---

## Prerequisites

- **GitHub CLI**: `gh` installed and authenticated
  ```bash
  gh auth login    # or export GH_TOKEN/GITHUB_TOKEN
  ```
- **Python**: 3.11+ recommended (for `tomllib` parsing in the script)
- **Build tooling**:
  ```bash
  python -m pip install --upgrade build
  ```

> The public CLI (`pinballctl`) intentionally contains **no** release/publish commands. Release operations are **maintainer-only** via the script.

---

## Versioning & Changelog

- Follow **Semantic Versioning**: `MAJOR.MINOR.PATCH` (e.g., `0.1.1`).
- Bump the version in `pyproject.toml`:
  ```toml
  [project]
  version = "0.1.1"
  ```
- Update **`CHANGELOG.md`** with a new section at the top:
  ```markdown
  ## [v0.1.1] - 2025-11-02
  ### Added
  - New feature...

  ### Changed
  - Behavior change...

  ### Fixed
  - Bug fix...
  ```

> The release script extracts the section matching the **exact version** (`## 0.1.1`, `## v0.1.1`, or `## [0.1.1]`). If not found, it can use `--generate 1` or fallback `--notes`/`--notes-file`.

---

## Building & Releasing

The maintainer script builds **sdist + wheel**, tags using `vX.Y.Z`, and creates a GitHub release.

### Normal Release (Latest by default)

```bash
./utils/build-release.sh
```

- Uses `CHANGELOG.md` to populate notes.
- Creates tag `v<version>` if needed and pushes it.
- Creates a GitHub release and uploads artifacts.
- Marks as **latest**, unless you specify otherwise with `--latest 0`.

### Pre-release

GitHub does **not** allow a prerelease to be marked as latest. The script auto-disables `--latest` when `--prerelease 1` is set.

```bash
./utils/build-release.sh --prerelease 1
# (implicitly behaves as --latest 0)
```

### Replace Existing Release (Overwrite Assets)

If a release already exists for this tag, the default behavior is to **fail** safely.
Pass `--replace 1` to overwrite (clobber) the assets in-place:

```bash
./utils/build-release.sh --replace 1
```

> Notes are not regenerated on replace by default. You can manually edit notes on GitHub or run with `--notes`, `--notes-file`, or `--generate 1` as needed.

### Select Branch / Custom Repo

```bash
./utils/build-release.sh --branch main
./utils/build-release.sh --repo yourname/pinballctl
```

### Use Generated Notes

```bash
./utils/build-release.sh --generate 1
```

### Override Notes Manually

```bash
./utils/build-release.sh --notes "Maintenance release with fixes"
# or
./utils/build-release.sh --notes-file docs/release-notes-0.1.1.md
```

---

## Script Options (Reference)

```
--repo <owner/repo>      GitHub repository (default: auto-detect from git remote)
--branch <name>          Branch to checkout before building (default: current)
--generate <0|1>         Use GitHub's --generate-notes instead of CHANGELOG (default: 0)
--notes "<text>"         Inline release notes (overrides CHANGELOG/generate)
--notes-file <path>      File for release notes (overrides CHANGELOG/generate)
--changelog <path>       Changelog file to read (default: CHANGELOG.md)
--latest <0|1>           Mark as latest release (default: 1)
--prerelease <0|1>       Mark as prerelease (default: 1)
--replace <0|1>          Overwrite existing release if it already exists (default: 0)
```

---

## Recommended Release Workflow

1. **Branch is clean** and CI is green.
2. **Bump version** in `pyproject.toml`.
3. **Update `CHANGELOG.md`** with the new section.
4. Commit:
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "chore(release): vX.Y.Z"
   ```
5. **Run the script**:
   ```bash
   ./utils/build-release.sh              # normal release
   # or
   ./utils/build-release.sh --prerelease 1  # pre-release
   ```
6. Verify the **GitHub Release** page shows correct notes and assets.

---

## Optional: GitHub Actions (Auto on Tag)

If you want CI to re-build and upload assets on tag push, add a workflow like:

```yaml
name: Build & Release on Tag

on:
  push:
    tags:
      - "v*"

jobs:
  build-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install --upgrade pip build
      - run: python -m build
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/*.whl
            dist/*.tar.gz
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

> This complements (but doesn’t replace) the local maintainer script.

---

## Licensing Note (Setuptools Deprecation)

Setuptools warns that TOML table form for `project.license` is deprecated.
Prefer SPDX string + license files:

```toml
[project]
license = "MIT"  # SPDX identifier

[tool.setuptools]
license-files = ["LICENSE", "COPYING", "LICENSE.*"]
```

Deadline per warning: **2026-02-18**.

---

## Troubleshooting

- **Release exists**  
  - Default: script fails.  
  - Use `--replace 1` to overwrite assets (uses `gh release upload --clobber`).

- **422: Latest release cannot be draft or prerelease**  
  - GitHub rule. Use `--prerelease 1` and the script will auto-disable `--latest`.

- **`gh` not authenticated**  
  - Run `gh auth login` or export `GH_TOKEN` / `GITHUB_TOKEN`.

- **Version parse failed**  
  - Ensure `pyproject.toml` has `[project].version = "X.Y.Z"`.
  - Python < 3.11? The script falls back to `grep+sed`, but 3.11+ is recommended.

- **Missing assets in release**  
  - Verify `dist/` contains `.whl` and `.tar.gz` after `python -m build`.
  - Re-run with `--replace 1` to upload artifacts again.

---

## Future: PyPI Publishing (Optional)

When ready to push public releases to PyPI, add to your workflow or a separate script:

```bash
python -m pip install --upgrade twine
python -m twine upload dist/*  # requires a PYPI token
```

Store secrets in GitHub as `PYPI_TOKEN` and use it in CI with `twine`.

---

**Maintainer contact:** (add your details here)
