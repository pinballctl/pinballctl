# Pinball CTL website

Static GitHub Pages source. All website documentation is in [docs/](docs/index.md).
See [Website](docs/developer-notes/website-and-search.md) for setup,
builds and publishing; [Developer Notes](docs/developer-notes/index.md)
collects the current position on key project topics.

From the repository root:

```sh
.venv/bin/python website/utils/build-site.py
.venv/bin/python website/utils/check-site.py
.venv/bin/python -m http.server 8090 --directory dist/site
```

Pushes to `main` deploy the validated `dist/site/` artifact through GitHub Actions.

The builder validates in a temporary `build/website-*` directory, cleans that
workspace and retains the successful result in `dist/site/` for preview/upload.
