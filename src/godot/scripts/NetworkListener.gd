extends Node

var scene_manager: Node
var media_controller: Node
var overlay_manager: Control
var debug_panel: Control
var ws_port: int = 17342
var tcp_server: TCPServer = TCPServer.new()
var peers: Dictionary = {}
var runtime_state: String = "booting"
var last_command_summary: String = "Waiting for commands"
var debug_visible: bool = true
var current_scene_name: String = "No scene loaded"
var display_state: Dictionary = {
    "displayId": "display_1",
    "name": "Display 1",
    "mode": "fullscreen",
    "monitor": 1,
    "fullscreen": true,
    "borderless": true,
    "width": 1920,
    "height": 1080,
    "x": 0,
    "y": 0,
    "scale": 1.0,
}
var initial_scene_key: String = "no_scene"
var applied_state: Dictionary = {}


func configure(scene_mgr: Node, media_ctrl: Node, overlay_mgr: Control, debug_ui: Control = null) -> void:
    scene_manager = scene_mgr
    media_controller = media_ctrl
    overlay_manager = overlay_mgr
    debug_panel = debug_ui
    if debug_panel and debug_panel.has_method("set_debug_enabled"):
        debug_panel.set_debug_enabled(debug_visible)


func _ready() -> void:
    var args := OS.get_cmdline_user_args()
    for i in range(args.size()):
        if args[i] == "--ws-port" and i + 1 < args.size():
            ws_port = int(args[i + 1])
        elif args[i] == "--scene-id" and i + 1 < args.size():
            initial_scene_key = str(args[i + 1]).strip_edges()
        elif args[i] == "--scene-name" and i + 1 < args.size():
            current_scene_name = str(args[i + 1]).strip_edges()
        elif args[i] == "--display-id" and i + 1 < args.size():
            display_state["displayId"] = str(args[i + 1]).strip_edges()
        elif args[i] == "--display-name" and i + 1 < args.size():
            display_state["name"] = str(args[i + 1]).strip_edges()
        elif args[i] == "--window-mode" and i + 1 < args.size():
            display_state["mode"] = str(args[i + 1]).strip_edges().to_lower()
        elif args[i] == "--debug-visible" and i + 1 < args.size():
            debug_visible = str(args[i + 1]).strip_edges() != "0"
        elif args[i] == "--window-width" and i + 1 < args.size():
            display_state["width"] = int(args[i + 1])
        elif args[i] == "--window-height" and i + 1 < args.size():
            display_state["height"] = int(args[i + 1])
        elif args[i] == "--window-x" and i + 1 < args.size():
            display_state["x"] = int(args[i + 1])
        elif args[i] == "--window-y" and i + 1 < args.size():
            display_state["y"] = int(args[i + 1])
        elif args[i] == "--monitor" and i + 1 < args.size():
            display_state["monitor"] = int(args[i + 1])
    var err: int = tcp_server.listen(ws_port, "127.0.0.1")
    if err != OK:
        push_error("Unable to start WebSocket listener on port %d" % ws_port)
        set_process(false)
    else:
        runtime_state = "running"


func _process(_delta: float) -> void:
    while tcp_server.is_connection_available():
        var stream: StreamPeerTCP = tcp_server.take_connection()
        var peer := WebSocketPeer.new()
        var accept_err: int = peer.accept_stream(stream)
        if accept_err == OK:
            peers[str(Time.get_ticks_usec())] = peer
    var to_remove: Array[String] = []
    for peer_id in peers.keys():
        var socket: WebSocketPeer = peers[peer_id]
        socket.poll()
        var state: int = socket.get_ready_state()
        if state == WebSocketPeer.STATE_OPEN:
            while socket.get_available_packet_count() > 0:
                var payload: String = socket.get_packet().get_string_from_utf8()
                var response: Dictionary = _handle_command(payload)
                socket.send_text(JSON.stringify(response))
        elif state == WebSocketPeer.STATE_CLOSING:
            continue
        elif state == WebSocketPeer.STATE_CLOSED:
            to_remove.append(peer_id)
    for peer_id in to_remove:
        peers.erase(peer_id)


func _dict_value(value: Variant) -> Dictionary:
    return value if value is Dictionary else {}


func _handle_command(raw: String) -> Dictionary:
    var parsed: Variant = JSON.parse_string(raw)
    if typeof(parsed) != TYPE_DICTIONARY:
        return {"ok": false, "error": "invalid_json"}
    var message: Dictionary = parsed
    var cmd: String = str(message.get("cmd", "")).strip_edges().to_upper()
    last_command_summary = cmd
    match cmd:
        "GET_STATUS":
            last_command_summary = "GET_STATUS"
            return {"ok": true, "status": status_payload()}
        "PRELOAD_MEDIA":
            var preload_media_rows: Array = message.get("media", [])
            last_command_summary = "PRELOAD_MEDIA (%d item(s))" % preload_media_rows.size()
            return media_controller.preload_media(preload_media_rows)
        "PLAY_VIDEO":
            var media: Dictionary = _dict_value(message.get("media", {}))
            last_command_summary = "PLAY_VIDEO %s" % str(media.get("key", ""))
            return media_controller.play_video(str(media.get("key", "")), str(media.get("path", "")), bool(media.get("loop", false)))
        "STOP_VIDEO":
            last_command_summary = "STOP_VIDEO"
            return media_controller.stop_video()
        "PAUSE_VIDEO":
            last_command_summary = "PAUSE_VIDEO"
            return media_controller.pause_video()
        "SET_SCENE":
            var scene: Dictionary = _dict_value(message.get("scene", {}))
            var scene_name: String = str(scene.get("name", "")).strip_edges()
            current_scene_name = scene_name if scene_name else str(scene.get("key", ""))
            last_command_summary = "SET_SCENE %s" % str(scene.get("key", ""))
            return scene_manager.set_scene(str(scene.get("key", "")), str(scene.get("path", "")), current_scene_name)
        "LOAD_SCENE":
            var entry: Dictionary = _dict_value(message.get("scene", {}))
            last_command_summary = "LOAD_SCENE %s" % str(entry.get("key", ""))
            return scene_manager.load_scene_entry(str(entry.get("key", "")), str(entry.get("path", "")), str(entry.get("type", "")))
        "SHOW_OVERLAY":
            var overlay: Dictionary = _dict_value(message.get("overlay", {}))
            last_command_summary = "SHOW_OVERLAY %s" % str(overlay.get("id", ""))
            return overlay_manager.show_overlay(str(overlay.get("id", "")), overlay.get("position", {}))
        "HIDE_OVERLAY":
            var hidden: Dictionary = _dict_value(message.get("overlay", {}))
            last_command_summary = "HIDE_OVERLAY %s" % str(hidden.get("id", ""))
            return overlay_manager.hide_overlay(str(hidden.get("id", "")))
        "UPDATE_TEXT":
            var text: Dictionary = _dict_value(message.get("text", {}))
            last_command_summary = "UPDATE_TEXT %s=%s" % [str(text.get("key", "")), str(text.get("value", ""))]
            return overlay_manager.update_text(str(text.get("key", "")), text.get("value", ""))
        "APPLY_STATE":
            var render_state: Dictionary = _dict_value(message.get("state", {}))
            return _apply_runtime_state(render_state)
        "SET_DISPLAY":
            var display: Dictionary = _dict_value(message.get("display", {}))
            display_state.merge(display, true)
            _apply_display(display_state)
            last_command_summary = "SET_DISPLAY %s / %s" % [str(display_state.get("displayId", "display_1")), str(display_state.get("mode", "fullscreen"))]
            return {"ok": true, "display": display_state}
        "SET_DEBUG":
            debug_visible = bool(message.get("enabled", true))
            if debug_panel and debug_panel.has_method("set_debug_enabled"):
                debug_panel.set_debug_enabled(debug_visible)
            last_command_summary = "SET_DEBUG %s" % ("on" if debug_visible else "off")
            return {"ok": true, "debugVisible": debug_visible}
        "SHUTDOWN":
            runtime_state = "stopping"
            last_command_summary = "SHUTDOWN"
            get_tree().quit()
            return {"ok": true}
        _:
            last_command_summary = "UNKNOWN %s" % cmd
            return {"ok": false, "error": "unknown_command", "cmd": cmd}


func _apply_runtime_state(render_state: Dictionary) -> Dictionary:
    applied_state = render_state
    var scene_data: Dictionary = _dict_value(render_state.get("scene", {}))
    var playback: Dictionary = _dict_value(render_state.get("playback", {}))
    var overlay_values: Dictionary = _dict_value(render_state.get("overlayValues", {}))
    var scene_layers: Array = []
    if render_state.get("layers", []) is Array:
        scene_layers = render_state.get("layers", [])
    var display_payload: Dictionary = _dict_value(render_state.get("display", {}))
    _sync_display_state_from_window()
    if not display_payload.is_empty():
        if _should_preserve_windowed_geometry(display_state, display_payload):
            display_payload["x"] = int(display_state.get("x", 0))
            display_payload["y"] = int(display_state.get("y", 0))
            display_payload["width"] = int(display_state.get("width", 1600))
            display_payload["height"] = int(display_state.get("height", 900))
        display_state.merge(display_payload, true)
    _apply_display(display_state)
    var scene_key: String = str(scene_data.get("key", "no_scene")).strip_edges()
    var scene_name: String = str(scene_data.get("name", "No scene loaded")).strip_edges()
    current_scene_name = scene_key
    if not scene_name.is_empty():
        current_scene_name = scene_name
    if scene_manager:
        var next_scene_key: String = scene_key
        if next_scene_key.is_empty():
            next_scene_key = "no_scene"
        scene_manager.set_scene(next_scene_key, str(scene_data.get("path", "")), current_scene_name)
    if overlay_manager and overlay_manager.has_method("apply_state"):
        overlay_manager.apply_state(scene_layers, overlay_values, playback)
    last_command_summary = "APPLY_STATE %s" % current_scene_name
    var playback_result: Dictionary = playback
    if playback_result.is_empty() and overlay_manager and overlay_manager.has_method("status"):
        playback_result = _dict_value(overlay_manager.status().get("playback", {}))
    var scene_result: Dictionary = {}
    if scene_manager:
        scene_result = scene_manager.status()
    return {
        "ok": true,
        "scene": scene_result,
        "playback": playback_result,
        "display": display_state,
    }


func _apply_display(display: Dictionary) -> void:
    var mode: String = str(display.get("mode", "fullscreen")).to_lower()
    var monitor: int = max(0, int(display.get("monitor", 1)) - 1)
    var screen_count: int = max(1, DisplayServer.get_screen_count())
    if monitor >= screen_count:
        monitor = screen_count - 1
    if mode == "windowed":
        var screen_origin: Vector2i = DisplayServer.screen_get_position(monitor)
        var window_x: int = int(display.get("x", 0))
        var window_y: int = int(display.get("y", 0))
        var window_pos: Vector2i = Vector2i(window_x, window_y)
        if window_x == 0 and window_y == 0:
            window_pos = screen_origin + Vector2i(80, 80)
        DisplayServer.window_set_current_screen(monitor)
        DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true)
        DisplayServer.window_set_size(Vector2i(int(display.get("width", 1600)), int(display.get("height", 900))))
        DisplayServer.window_set_position(window_pos)
    else:
        DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, bool(display.get("borderless", true)))
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, false)
        DisplayServer.window_set_current_screen(monitor)
        DisplayServer.window_set_size(Vector2i(int(display.get("width", 1920)), int(display.get("height", 1080))))
        DisplayServer.window_set_position(Vector2i(int(display.get("x", 0)), int(display.get("y", 0))))
    _sync_display_state_from_window()


func _should_preserve_windowed_geometry(current_display: Dictionary, requested_display: Dictionary) -> bool:
    if str(current_display.get("mode", "")).to_lower() != "windowed":
        return false
    if str(requested_display.get("mode", "")).to_lower() != "windowed":
        return false
    if str(current_display.get("displayId", "")).strip_edges() != str(requested_display.get("displayId", "")).strip_edges():
        return false
    if int(current_display.get("monitor", 1)) != int(requested_display.get("monitor", 1)):
        return false
    return true


func _sync_display_state_from_window() -> void:
    var main_window: Window = get_window()
    if main_window == null:
        return
    var current_mode: int = DisplayServer.window_get_mode()
    var is_windowed: bool = current_mode == DisplayServer.WINDOW_MODE_WINDOWED
    display_state["mode"] = "windowed" if is_windowed else "fullscreen"
    display_state["fullscreen"] = not is_windowed
    display_state["borderless"] = DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_BORDERLESS)
    display_state["monitor"] = DisplayServer.window_get_current_screen() + 1
    var window_size: Vector2i = main_window.size
    display_state["width"] = int(window_size.x)
    display_state["height"] = int(window_size.y)
    var window_pos: Vector2i = main_window.position
    display_state["x"] = int(window_pos.x)
    display_state["y"] = int(window_pos.y)


func status_payload() -> Dictionary:
    _sync_display_state_from_window()
    var scene_status: Dictionary = scene_manager.status() if scene_manager else {}
    var overlay_status: Dictionary = overlay_manager.status() if overlay_manager else {"overlayValues": {}, "playback": {}}
    var playback_status: Dictionary = _dict_value(overlay_status.get("playback", {}))
    var main_window: Window = get_window()
    return {
        "state": runtime_state,
        "health": "ok",
        "scene": scene_status,
        "sceneName": current_scene_name,
        "playback": playback_status,
        "display": display_state,
        "overlayValues": overlay_status.get("overlayValues", {}),
        "lastCommandSummary": last_command_summary,
        "connections": peers.size(),
        "windowVisible": bool(main_window and main_window.visible),
        "debugVisible": debug_visible,
    }
