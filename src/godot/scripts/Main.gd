extends Node

@onready var scene_manager: Node = $SceneManager
@onready var media_controller: Node = $MediaController
@onready var overlay_manager: Control = $OverlayLayer/OverlayManager
@onready var debug_panel: Control = $DebugLayer/DebugPanel
@onready var network_listener: Node = $NetworkListener
var _main_window: Window
var _quitting: bool = false
var _initial_scene_key: String = "no_scene"
var _debug_visible: bool = true


func _enter_tree() -> void:
    _apply_initial_display_from_args()


func _ready() -> void:
    _main_window = get_window()
    if _main_window:
        var close_callable := Callable(self, "_on_close_requested")
        if _main_window.close_requested.is_connected(close_callable) == false:
            _main_window.close_requested.connect(close_callable)
        var visibility_callable := Callable(self, "_on_window_visibility_changed")
        if _main_window.visibility_changed.is_connected(visibility_callable) == false:
            _main_window.visibility_changed.connect(visibility_callable)
    _initial_scene_key = _initial_scene_from_args()
    _debug_visible = _debug_visible_from_args()
    if debug_panel and debug_panel.has_method("set_debug_enabled"):
        debug_panel.set_debug_enabled(_debug_visible)
    if scene_manager.has_method("set_scene"):
        scene_manager.set_scene(_initial_scene_key)
    if network_listener.has_method("configure"):
        network_listener.configure(scene_manager, media_controller, overlay_manager, debug_panel)


func _process(_delta: float) -> void:
    if _main_window and _quitting == false:
        if _main_window.visible == false:
            _on_close_requested()
            return
        if DisplayServer.get_window_list().has(_main_window.get_window_id()) == false:
            _on_close_requested()
            return
    if not debug_panel or not debug_panel.has_method("set_snapshot"):
        return
    var scene_status: Dictionary = {}
    if scene_manager and scene_manager.has_method("status"):
        scene_status = scene_manager.status()
    var playback_status: Dictionary = {}
    if media_controller and media_controller.has_method("status"):
        playback_status = media_controller.status()
    var overlay_status: Dictionary = {}
    if overlay_manager and overlay_manager.has_method("status"):
        overlay_status = overlay_manager.status()
    var listener_status: Dictionary = {}
    if network_listener and network_listener.has_method("status_payload"):
        listener_status = network_listener.status_payload()
    var display_status: Dictionary = listener_status.get("display", {})
    var overlay_values: Dictionary = overlay_status.get("overlayValues", {})
    var overlay_parts: Array[String] = []
    for key in overlay_values.keys():
        overlay_parts.append("%s=%s" % [str(key), str(overlay_values.get(key, ""))])
    overlay_parts.sort()
    var scene_label: String = str(scene_status.get("current", ""))
    if not str(listener_status.get("sceneName", "")).is_empty():
        scene_label = str(listener_status.get("sceneName", ""))
    var playback_label: String = str(playback_status.get("status", "stopped"))
    var playback_media_key: String = str(playback_status.get("mediaKey", ""))
    if not playback_media_key.is_empty():
        playback_label += " / " + playback_media_key
    var overlay_label: String = "none"
    if overlay_parts.size() > 0:
        overlay_label = ", ".join(overlay_parts)
    debug_panel.set_snapshot({
        "title": "PinballCTL Godot Runtime",
        "state": str(listener_status.get("state", "running")),
        "health": str(listener_status.get("health", "ok")),
        "scene": scene_label,
        "playback": playback_label,
        "display": "%s / %s" % [str(display_status.get("name", display_status.get("displayId", "display_1"))), str(display_status.get("mode", "fullscreen"))],
        "overlays": overlay_label,
        "command": str(listener_status.get("lastCommandSummary", "Waiting for commands")),
    })


func _on_close_requested() -> void:
    if _quitting:
        return
    _quitting = true
    if network_listener:
        network_listener.runtime_state = "stopping"
    get_tree().quit()


func _on_window_visibility_changed() -> void:
    if _main_window and _main_window.visible == false:
        _on_close_requested()


func _notification(what: int) -> void:
    if what == NOTIFICATION_WM_CLOSE_REQUEST:
        _on_close_requested()


func _cmd_args_map() -> Dictionary:
    var args: PackedStringArray = OS.get_cmdline_user_args()
    var out: Dictionary = {}
    var i: int = 0
    while i < args.size():
        var key: String = str(args[i])
        if key.begins_with("--") and i + 1 < args.size():
            out[key] = args[i + 1]
            i += 2
            continue
        i += 1
    return out


func _initial_scene_from_args() -> String:
    var args := _cmd_args_map()
    var scene_key: String = str(args.get("--scene-id", "no_scene")).strip_edges()
    if scene_key.is_empty():
        return "no_scene"
    return scene_key


func _debug_visible_from_args() -> bool:
    var args := _cmd_args_map()
    var raw_value: String = str(args.get("--debug-visible", "1")).strip_edges()
    return raw_value != "0"


func _apply_initial_display_from_args() -> void:
    var args := _cmd_args_map()
    var mode: String = str(args.get("--window-mode", "fullscreen")).to_lower()
    var monitor: int = max(0, int(str(args.get("--monitor", "1")).to_int()) - 1)
    var screen_count: int = max(1, DisplayServer.get_screen_count())
    if monitor >= screen_count:
        monitor = screen_count - 1
    var window_width: int = max(320, int(str(args.get("--window-width", "1600")).to_int()))
    var window_height: int = max(240, int(str(args.get("--window-height", "900")).to_int()))
    var window_x: int = int(str(args.get("--window-x", "80")).to_int())
    var window_y: int = int(str(args.get("--window-y", "80")).to_int())
    if mode == "windowed":
        var screen_origin: Vector2i = DisplayServer.screen_get_position(monitor)
        var window_pos: Vector2i = Vector2i(window_x, window_y)
        if window_x == 0 and window_y == 0:
            window_pos = screen_origin + Vector2i(80, 80)
        DisplayServer.window_set_current_screen(monitor)
        DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true)
        DisplayServer.window_set_size(Vector2i(window_width, window_height))
        DisplayServer.window_set_position(window_pos)
    else:
        DisplayServer.window_set_current_screen(monitor)
        DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
        DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, false)
