# Pinball CTL website

Static GitHub Pages source. All website documentation is in [docs/](docs/index.md).
See [Website](docs/developer-notes/website-and-search.md) for setup, builds and
publishing; [Developer Notes](docs/developer-notes/index.md) collects key topics.

From the repository root:

```sh
.venv/bin/python website/utils/build-site.py
.venv/bin/python website/utils/build-site.py --preview
```

The first command builds, validates and removes its temporary output. The second
serves a preview at `http://localhost:8090` until Ctrl+C, then removes its files.
Both use temporary workspaces under `build/`.

Pushes to `main` build and check `build/site/`, upload it as the Pages artifact,
remove the local build files and deploy the artifact through GitHub Actions.
