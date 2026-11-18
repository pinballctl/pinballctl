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

Build and validate the site:

```sh
.venv/bin/python website/utils/build-site.py
```

The builder renders into a temporary `build/website-*` workspace, runs the site
checker and removes the generated files when finished. Failed builds also clean
their temporary output. No final website directory is retained by this command.
The checker validates local page, image and section links, redirects and metadata;
it does not verify external websites or the technical accuracy of the prose.

To preview locally:

```sh
.venv/bin/python website/utils/build-site.py --preview
```

Open `http://localhost:8090`. Check changed pages, navigation and images at desktop
and mobile widths. Stop with **Ctrl+C** to close the server and remove the preview
files. Use `--preview 8091` if another port is needed.

Documentation pages stay within the viewport. Wide tables scroll inside their
own frame, with a dashed edge while columns remain off-screen; horizontal gestures
at a table edge must not move the whole page sideways. Only six-column shopping
tables receive the wide parts layout, not every table containing a thumbnail.

Automation that needs files for upload can use `--output build/site`, followed by
`website/utils/check-site.py --site build/site`. This explicitly retains a checked
artifact; the caller must remove it after use. Outputs must stay inside `build/`,
and existing nonempty directories need the website build marker before replacement.
Unrelated package and firmware output is left alone.

## Publishing

Commit the intended source changes and push `main`. The **Build website and docs**
workflow then:

1. Sets up Python 3.12 and installs the website dependencies.
2. Builds and checks the site.
3. Uploads `build/site/` as the GitHub Pages artifact.
4. Removes `build/site/` in an unconditional cleanup step, including after a failed upload.
5. Deploys the checked artifact to [www.pinballctl.com](https://www.pinballctl.com/).

The workflow also supports a manual run from GitHub Actions. Leave **deploy**
unchecked to build and validate only, or enable it to publish the result.

After publishing, check that both the build and deploy jobs succeeded. Open the
live homepage and changed documentation pages, check their links and images, and
verify any redirects for moved or removed pages. A local build or commit alone
does not update the live site.
