# Pinball CTL

A browser-based control platform for homebrew pinball machines. Author hardware,
rules, scoring, lighting and media on a Raspberry Pi; an ESP32-S3 handles supported
real-time I/O and enforces output safety limits over framed USB serial.

- [Website](https://www.pinballctl.com/)
- [Getting started](https://www.pinballctl.com/docs/user-guide/getting-started/)
- [Developer Guide](media/website/docs/developer-guide/index.md)
- [Test Bench](media/website/docs/developer-notes/test-bench.md)

## Quick start

Use Python 3.11 or later and a virtual environment. For a development checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/pinballctl start
```

Open `http://localhost:8888` (or the Pi's hostname). Follow the getting-started guide
for machine setup, default credentials and your first input. Keep coils and other
high-current loads disconnected during initial setup; software checks cannot
validate electrical wiring.

## Repository

| Directory | Contents |
| --- | --- |
| `src/pinballctl/webapp/` | Flask application and admin UI |
| `src/pinballctl/runtime/` | USB bridge, rules, game, lighting and other machine services |
| `src/firmware/` | ESP32-S3 firmware |
| `src/pinballctl/runtime/godot/`, `media/backglass/` | Godot display host and sample presentation |
| `media/website/` | GitHub Pages source, all website guides and build tools |
| `tests/`, `utils/` | Tests and project utilities |

Website guides are authored in `media/website/docs/`, with documentation images in
`media/website/assets/docs/`. Current test-bench engineering sources live in
`media/website/design/test-bench/`. Website builds use temporary directories under `build/`.
The Pages workflow uploads `build/site/`, removes it and deploys pushes to `main`.
See [Website](media/website/docs/developer-notes/website-and-search.md#build-output) for previewing,
editing and deployment. Runtime data in `src/instance/` and local backups are not
source files.

## Licence

See [LICENSE](LICENSE) for the Pinball CTL Community Licence and commercial-use terms.
