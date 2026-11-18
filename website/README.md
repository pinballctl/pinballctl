# Pinball CTL website

Static GitHub Pages source. All website documentation is in [docs/](docs/index.md).
See [Website and documentation](docs/developer-guide/website.md) for editing,
preview, screenshots and deployment; [Developer Log](docs/developer-log/index.md)
records dated decisions.

From the repository root:

```sh
.venv/bin/python website/utils/build-site.py
.venv/bin/python website/utils/check-site.py
.venv/bin/python -m http.server 8090 --directory dist/site
```

Pushes to `main` deploy the validated `dist/site/` artifact through GitHub Actions.
