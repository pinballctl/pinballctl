# Website

## Current setup

[www.pinballctl.com](https://www.pinballctl.com/) is a static GitHub Pages site
containing the project website and documentation. Sources live in this repository;
the published site is generated from them.

- `website/docs/`: user guides, technical references, Developer Guide and Developer Notes.
- `website/content/`: navigation, feature content and documentation URL mappings.
- `website/templates/`: shared page content and illustrations.
- `website/assets/`: styles, browser scripts, screenshots and documentation images.
- `website/utils/`: site builder, Markdown renderer, link checker and screenshot tools.
- `.github/workflows/website.yml`: GitHub Actions build and Pages deployment.

Edit source files rather than generated HTML. Update navigation and links when
pages change, and review text and images before publication to exclude personal
information, credentials and private machine data.

## Build output

Run commands from the repository root. Use the project's `.venv` with Python 3.12
or later; see [Development and testing](../developer-guide/development.md) for the
checkout setup. Install the website dependencies if needed:

```sh
.venv/bin/python -m pip install Markdown==3.7 Pillow==12.0.0
```

Build, check and preview the site:

```sh
.venv/bin/python website/utils/build-site.py
.venv/bin/python website/utils/check-site.py
.venv/bin/python -m http.server 8090 --directory dist/site
```

Open `http://localhost:8090`. Check changed pages, navigation and images at desktop
and mobile widths. The checker validates local page, image and section links,
redirects and site metadata; it does not verify external websites or the technical
accuracy of the prose.

The builder renders into a temporary `build/website-*` workspace and validates it
before replacing `dist/site/`. It cleans temporary files and the previous generated
site after a successful replacement. Rendering or validation failures preserve the
last successful site. Keep `dist/site/` for preview and upload; it is ignored by
Git. Unrelated package, firmware and engineering output is left alone.

For a separate preview, use `--output dist/site-preview` with the builder and
`--site dist/site-preview` with the checker.

## Publishing

Commit the intended source changes and push `main`. The **Build website and docs**
workflow then:

1. Sets up Python 3.12 and installs the website dependencies.
2. Builds and checks the site.
3. Uploads `dist/site/` as the GitHub Pages artifact.
4. Deploys the checked artifact to [www.pinballctl.com](https://www.pinballctl.com/).

The workflow also supports a manual run from GitHub Actions. Leave **deploy**
unchecked to build and validate only, or enable it to publish the result.

After publishing, check that both the build and deploy jobs succeeded. Open the
live homepage and changed documentation pages, check their links and images, and
verify any redirects for moved or removed pages. A local build or commit alone
does not update the live site.
