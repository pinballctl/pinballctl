extends Node

var registry: Dictionary = {}
var loaded_packs: Dictionary = {}
var current_scene_key: String = ""
var current_scene_node: Node = null
var scene_stack_nodes: Array = []
var builtin_scene_titles: Dictionary = {
    "no_scene": "No scene loaded",
    "attract": "Attract Mode",
    "gameplay": "Gameplay",
    "results": "Results",
}
var builtin_scene_subtitles: Dictionary = {
    "no_scene": "Waiting for pinballctl commands",
    "attract": "Waiting for pinballctl commands",
    "gameplay": "Runtime is ready for live scoring updates",
    "results": "Results scene loaded",
}
var builtin_scene_colors: Dictionary = {
    "no_scene": Color("000000"),
    "attract": Color("1f3d2d"),
    "gameplay": Color("1d3557"),
    "results": Color("5a189a"),
}


func register_builtin_scenes() -> void:
    registry["no_scene"] = ""
    registry["attract"] = ""
    registry["gameplay"] = ""
    registry["results"] = ""


func _ready() -> void:
    register_builtin_scenes()


func list_scenes() -> Array:
    return registry.keys()


func load_scene_entry(scene_key: String, scene_path: String, scene_type: String = "") -> Dictionary:
    if scene_path.is_empty():
        return {"ok": false, "error": "missing_scene_path"}
    var normalized_type := scene_type.strip_edges().to_lower()
    if normalized_type == "pck":
        var packed := ProjectSettings.load_resource_pack(scene_path)
        if not packed:
            return {"ok": false, "error": "pack_load_failed"}
        loaded_packs[scene_key] = scene_path
        registry[scene_key] = "res://dynamic/" + scene_key + ".tscn"
        return {"ok": true, "scene": {"key": scene_key, "path": registry[scene_key], "type": "pck"}}
    registry[scene_key] = scene_path
    return {"ok": true, "scene": {"key": scene_key, "path": scene_path, "type": "tscn"}}


func set_scene(scene_key: String, scene_path: String = "", scene_title: String = "") -> Dictionary:
    _clear_scene_stack()
    var instantiated := _instantiate_scene_node(scene_key, scene_path, scene_title)
    if not instantiated.get("ok", false):
        return instantiated
    var next_scene_node: Node = instantiated.get("node")
    current_scene_key = scene_key
    current_scene_node = next_scene_node
    add_child(current_scene_node)
    move_child(current_scene_node, 0)
    scene_stack_nodes = [current_scene_node]
    return {"ok": true, "scene": {"current": scene_key, "path": str(instantiated.get("path", "")), "loaded": true}}


func apply_stack(scene_stack: Array, active_scene_key: String = "no_scene", active_scene_title: String = "") -> Dictionary:
    _clear_scene_stack()
    if scene_stack.is_empty():
        return set_scene(active_scene_key, "", active_scene_title)
    var added_nodes: Array = []
    for entry in scene_stack:
        if not (entry is Dictionary):
            continue
        var scene_key := str(entry.get("key", "")).strip_edges()
        if scene_key.is_empty():
            scene_key = str(entry.get("sceneId", "no_scene")).strip_edges()
        var scene_title := str(entry.get("name", active_scene_title)).strip_edges()
        var scene_path := str(entry.get("path", "")).strip_edges()
        var instantiated := _instantiate_scene_node(scene_key, scene_path, scene_title)
        if not instantiated.get("ok", false):
            continue
        var node: Node = instantiated.get("node")
        add_child(node)
        move_child(node, 0)
        _apply_stack_entry_state(node, entry)
        added_nodes.append(node)
    scene_stack_nodes = added_nodes
    if added_nodes.size() > 0:
        current_scene_node = added_nodes[-1]
        current_scene_key = str(scene_stack[-1].get("key", active_scene_key))
        return {"ok": true, "scene": {"current": current_scene_key, "loaded": true, "stackDepth": added_nodes.size()}}
    return set_scene(active_scene_key, "", active_scene_title)


func _instantiate_scene_node(scene_key: String, scene_path: String = "", scene_title: String = "") -> Dictionary:
    if not scene_path.is_empty():
        registry[scene_key] = scene_path
    var path := str(registry.get(scene_key, ""))
    if path.is_empty():
        if builtin_scene_titles.has(scene_key):
            return {"ok": true, "node": _create_builtin_scene(scene_key), "path": "", "builtin": true}
        return {"ok": true, "node": _create_placeholder_scene(scene_key, scene_title), "path": "", "builtin": false, "placeholder": true}
    var packed_scene: PackedScene = load(path)
    if packed_scene == null:
        return {"ok": false, "error": "scene_load_failed", "path": path}
    return {"ok": true, "node": packed_scene.instantiate(), "path": path}


func _clear_scene_stack() -> void:
    if current_scene_node and is_instance_valid(current_scene_node):
        current_scene_node = null
    for node in scene_stack_nodes:
        if is_instance_valid(node):
            node.queue_free()
    scene_stack_nodes.clear()


func _apply_stack_entry_state(node: Node, entry: Dictionary) -> void:
    if not (node is CanvasItem):
        return
    var canvas_item: CanvasItem = node
    canvas_item.z_index = int(entry.get("renderOrder", 0))
    var alpha := _transition_alpha(entry)
    canvas_item.modulate = Color(1, 1, 1, alpha)
    if str(entry.get("blendMode", "")).to_upper() == "PAUSE_LOWER":
        canvas_item.process_mode = Node.PROCESS_MODE_PAUSABLE


func _transition_alpha(entry: Dictionary) -> float:
    var transition: Dictionary = entry.get("transition", {}) if entry.get("transition", {}) is Dictionary else {}
    var duration_ms: int = max(0, int(transition.get("durationMs", 0)))
    var phase := str(transition.get("phase", "")).to_lower()
    var transition_type := str(transition.get("type", "CUT")).to_upper()
    var anchor_ms := int(transition.get("anchorMs", 0))
    if duration_ms <= 0 or phase.is_empty() or transition_type == "CUT" or anchor_ms <= 0:
        return 1.0
    var now_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
    var progress: float = clamp(float(now_ms - anchor_ms) / float(duration_ms), 0.0, 1.0)
    if phase == "out":
        return 1.0 - progress
    return progress


func status() -> Dictionary:
    return {
        "current": current_scene_key,
        "available": list_scenes(),
        "loaded": current_scene_node != null,
    }


func _create_builtin_scene(scene_key: String) -> Control:
    var root := Control.new()
    root.name = "BuiltinScene_" + scene_key
    root.set_anchors_preset(Control.PRESET_FULL_RECT)
    root.mouse_filter = Control.MOUSE_FILTER_IGNORE

    var bg := ColorRect.new()
    bg.set_anchors_preset(Control.PRESET_FULL_RECT)
    bg.color = builtin_scene_colors.get(scene_key, Color("20252d"))
    root.add_child(bg)

    var center := CenterContainer.new()
    center.set_anchors_preset(Control.PRESET_FULL_RECT)
    center.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(center)

    var vbox := VBoxContainer.new()
    vbox.alignment = BoxContainer.ALIGNMENT_CENTER
    center.add_child(vbox)

    var title := Label.new()
    title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    title.add_theme_font_size_override("font_size", 56)
    title.text = str(builtin_scene_titles.get(scene_key, scene_key.capitalize()))
    vbox.add_child(title)

    var subtitle := Label.new()
    subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    subtitle.add_theme_font_size_override("font_size", 24)
    subtitle.text = str(builtin_scene_subtitles.get(scene_key, ""))
    vbox.add_child(subtitle)

    var hint := Label.new()
    hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    hint.add_theme_font_size_override("font_size", 18)
    hint.text = "Scene key: %s" % scene_key
    vbox.add_child(hint)

    return root


func _create_placeholder_scene(scene_key: String, scene_title: String = "") -> Control:
    var root := Control.new()
    root.name = "PlaceholderScene_" + scene_key
    root.set_anchors_preset(Control.PRESET_FULL_RECT)
    root.mouse_filter = Control.MOUSE_FILTER_IGNORE
    return root
