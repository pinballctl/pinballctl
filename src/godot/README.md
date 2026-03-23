# Godot Media Runtime

This directory contains the Godot 4 runtime scaffold used by `pinballctl` as an externally controlled media renderer.

Current responsibilities:

- Accept runtime commands from `pinballctl`
- Switch scenes and load uploaded scene content
- Play video assets
- Manage text/image overlays
- Apply display/window settings at runtime

The Python integration layer lives in `src/pinballctl/media/godot_runtime.py`.

