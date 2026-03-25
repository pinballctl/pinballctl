extends Node

var registry: Dictionary = {}
var loaded_packs: Dictionary = {}
var current_scene_key: String = ""
var current_scene_node: Node = null
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
    if not scene_path.is_empty():
        registry[scene_key] = scene_path
    var next_scene_node: Node = null
    var path := str(registry.get(scene_key, ""))
    if path.is_empty():
        if builtin_scene_titles.has(scene_key):
            next_scene_node = _create_builtin_scene(scene_key)
            if current_scene_node:
                current_scene_node.queue_free()
            current_scene_key = scene_key
            current_scene_node = next_scene_node
            add_child(current_scene_node)
            move_child(current_scene_node, 0)
            return {"ok": true, "scene": {"current": scene_key, "path": "", "loaded": true, "builtin": true}}
        next_scene_node = _create_placeholder_scene(scene_key, scene_title)
        if current_scene_node:
            current_scene_node.queue_free()
        current_scene_key = scene_key
        current_scene_node = next_scene_node
        add_child(current_scene_node)
        move_child(current_scene_node, 0)
        return {"ok": true, "scene": {"current": scene_key, "path": "", "loaded": true, "builtin": false, "placeholder": true}}
    var packed_scene: PackedScene = load(path)
    if packed_scene == null:
        return {"ok": false, "error": "scene_load_failed", "path": path}
    next_scene_node = packed_scene.instantiate()
    if current_scene_node:
        current_scene_node.queue_free()
    current_scene_key = scene_key
    current_scene_node = next_scene_node
    add_child(current_scene_node)
    move_child(current_scene_node, 0)
    return {"ok": true, "scene": {"current": scene_key, "path": path, "loaded": true}}


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
