# Godot Media Runtime

`src/pinballctl/runtime/godot/` contains the Godot 4 runtime scaffold used by `pinballctl` as an externally controlled media renderer.

Current responsibilities:

- Accept runtime commands from `pinballctl`
- Switch scenes and load uploaded scene content
- Play video assets
- Manage text/image overlays
- Apply display/window settings at runtime

The Python integration layer lives in `src/pinballctl/runtime/media/godot_runtime.py`.

The Godot supervisor starts displays configured for autoplay. It gives its player
processes an authenticated endpoint bound to loopback for scene events and high
scores. Scene packs still emit the same signals. The runtime submits those events
through the shared ingress used by the webapp and handles leaderboard state,
initials submission and skipping through the same scoring store. These functions
work with Gunicorn stopped.

## Runtime commands

The `pinballctl` Godot runtime currently accepts JSON commands with a `cmd` field.

Examples:

```json
{"cmd":"GET_STATUS"}
{"cmd":"SET_SCENE","scene":{"key":"gameplay"}}
{"cmd":"LOAD_SCENE","scene":{"key":"custom_bonus_mode","path":"/abs/path/custom_bonus_mode.tscn","type":"tscn"}}
{"cmd":"PLAY_VIDEO","media":{"key":"attract_intro","path":"/abs/path/attract_intro.mp4","loop":true}}
{"cmd":"STOP_VIDEO"}
{"cmd":"PAUSE_VIDEO"}
{"cmd":"UPDATE_TEXT","text":{"key":"score","value":"12345"}}
{"cmd":"SET_DISPLAY","display":{"displayId":"display_2","mode":"fullscreen","monitor":2,"borderless":true,"width":1920,"height":1080,"x":0,"y":0,"scale":1.0}}
{"cmd":"SHUTDOWN"}
```

These are Godot host commands, separate from the framed Pi/ESP serial protocol.
The receiver is `src/pinballctl/runtime/godot/scripts/NetworkListener.gd`. See [Backglass development](backglass.md) for scene integration and export.
