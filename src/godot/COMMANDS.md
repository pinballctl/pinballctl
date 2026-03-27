# Command Set

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
