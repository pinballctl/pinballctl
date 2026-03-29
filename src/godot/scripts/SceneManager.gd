extends Node

var registry: Dictionary = {}
var loaded_packs: Dictionary = {}
var current_scene_key: String = ""
var current_scene_node: Node = null
var scene_stack_nodes: Array = []
var text_values: Dictionary = {}
var runtime_event_sink: Node = null
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


func configure_runtime_event_sink(sink: Node) -> void:
    runtime_event_sink = sink


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


func set_scene(scene_key: String, scene_path: String = "", scene_title: String = "", pack_path: String = "") -> Dictionary:
    _clear_scene_stack()
    var instantiated := _instantiate_scene_node(scene_key, scene_path, pack_path, scene_title)
    if not instantiated.get("ok", false):
        return instantiated
    var next_scene_node: Node = instantiated.get("node")
    current_scene_key = scene_key
    current_scene_node = next_scene_node
    _bind_scene_runtime_events(current_scene_node)
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
        var pack_path := str(entry.get("packPath", "")).strip_edges()
        var instantiated := _instantiate_scene_node(scene_key, scene_path, pack_path, scene_title)
        if not instantiated.get("ok", false):
            continue
        var node: Node = instantiated.get("node")
        _bind_scene_runtime_events(node)
        add_child(node)
        move_child(node, 0)
        _apply_stack_entry_state(node, entry)
        _apply_imported_scene_tokens(node)
        added_nodes.append(node)
    scene_stack_nodes = added_nodes
    if added_nodes.size() > 0:
        current_scene_node = added_nodes[-1]
        current_scene_key = str(scene_stack[-1].get("key", active_scene_key))
        return {"ok": true, "scene": {"current": current_scene_key, "loaded": true, "stackDepth": added_nodes.size()}}
    return set_scene(active_scene_key, "", active_scene_title)


func _instantiate_scene_node(scene_key: String, scene_path: String = "", pack_path: String = "", scene_title: String = "") -> Dictionary:
    if not scene_path.is_empty():
        registry[scene_key] = scene_path
    var path := str(registry.get(scene_key, ""))
    if path.is_empty():
        if builtin_scene_titles.has(scene_key):
            return {"ok": true, "node": _create_builtin_scene(scene_key), "path": "", "builtin": true}
        return {"ok": true, "node": _create_placeholder_scene(scene_key, scene_title), "path": "", "builtin": false, "placeholder": true}
    if not pack_path.is_empty() and not loaded_packs.has(pack_path):
        var pack_loaded := ProjectSettings.load_resource_pack(pack_path)
        if not pack_loaded:
            return {"ok": false, "error": "pack_load_failed", "path": path, "packPath": pack_path}
        loaded_packs[pack_path] = true
    var packed_scene: PackedScene = load(path)
    if packed_scene == null:
        return {"ok": false, "error": "scene_load_failed", "path": path}
    var node := packed_scene.instantiate()
    if node is Control:
        node = _make_fullscreen_scene_host(node)
    _apply_imported_scene_tokens(node)
    return {"ok": true, "node": node, "path": path}


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


func dispatch_input_action(action: String, phase: String = "tap") -> Dictionary:
    return dispatch_runtime_input("action", action, phase)


func dispatch_runtime_input(input_kind: String, input_value: String, phase: String = "tap") -> Dictionary:
    var normalized_kind := String(input_kind).strip_edges().to_lower()
    var normalized_value := String(input_value).strip_edges()
    var normalized_phase := String(phase).strip_edges().to_lower()
    if normalized_value.is_empty():
        return {"ok": false, "error": "missing_input_value"}
    if normalized_phase.is_empty():
        normalized_phase = "tap"
    if normalized_phase not in ["tap", "press", "release"]:
        normalized_phase = "tap"
    if normalized_kind == "key":
        var key_delivered := false
        if current_scene_node and is_instance_valid(current_scene_node):
            key_delivered = _dispatch_key_to_node(current_scene_node, normalized_value, normalized_phase)
        if key_delivered:
            return {"ok": true, "inputKind": normalized_kind, "inputValue": normalized_value, "phase": normalized_phase, "delivered": true, "mode": "scene_api"}
        return _inject_input_key(normalized_value, normalized_phase)
    normalized_kind = "action"
    var delivered := false
    if current_scene_node and is_instance_valid(current_scene_node):
        delivered = _dispatch_action_to_node(current_scene_node, normalized_value, normalized_phase)
    if delivered:
        return {"ok": true, "inputKind": normalized_kind, "inputValue": normalized_value, "phase": normalized_phase, "delivered": true, "mode": "scene_api"}
    return _inject_input_action(normalized_value, normalized_phase)


func update_text(key: String, value: Variant) -> Dictionary:
    text_values[key] = value
    for node in scene_stack_nodes:
        if is_instance_valid(node):
            _refresh_imported_scene_tokens(node, key)
    return {"ok": true, "text": {"key": key, "value": value}}


func apply_text_values(values: Dictionary) -> Dictionary:
    text_values = values.duplicate(true)
    for node in scene_stack_nodes:
        if is_instance_valid(node):
            _apply_imported_scene_tokens(node)
    return {"ok": true, "overlayValues": text_values.duplicate(true)}


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


func _make_fullscreen_scene_host(control_node: Control) -> Control:
    var viewport_size := get_viewport().get_visible_rect().size
    var host := Control.new()
    host.set_anchors_preset(Control.PRESET_FULL_RECT)
    host.mouse_filter = Control.MOUSE_FILTER_IGNORE
    host.clip_contents = true
    var authored_bounds := _estimated_control_scene_bounds(control_node)
    var base_size := authored_bounds.size

    if _is_full_rect_control_root(control_node):
        var fills_target := (
            base_size.x >= viewport_size.x * 0.9
            and base_size.y >= viewport_size.y * 0.9
        )
        if fills_target or _has_full_rect_control_children(control_node):
            control_node.set_anchors_preset(Control.PRESET_FULL_RECT)
            control_node.offset_left = 0
            control_node.offset_top = 0
            control_node.offset_right = 0
            control_node.offset_bottom = 0
            control_node.position = Vector2.ZERO
            control_node.scale = Vector2.ONE
            host.add_child(control_node)
            return host

    if base_size.x <= 1.0 or base_size.y <= 1.0:
        base_size = viewport_size
        authored_bounds = Rect2(Vector2.ZERO, viewport_size)

    control_node.set_anchors_preset(Control.PRESET_TOP_LEFT)
    control_node.offset_left = 0
    control_node.offset_top = 0
    control_node.offset_right = 0
    control_node.offset_bottom = 0
    control_node.size = base_size

    var scale_factor: float = min(viewport_size.x / max(1.0, base_size.x), viewport_size.y / max(1.0, base_size.y))
    control_node.scale = Vector2.ONE * scale_factor
    control_node.position = Vector2(
        ((viewport_size.x - (base_size.x * scale_factor)) * 0.5) - (authored_bounds.position.x * scale_factor),
        ((viewport_size.y - (base_size.y * scale_factor)) * 0.5) - (authored_bounds.position.y * scale_factor)
    )

    host.add_child(control_node)
    return host


func _is_full_rect_control_root(control: Control) -> bool:
    return (
        is_equal_approx(control.anchor_left, 0.0)
        and is_equal_approx(control.anchor_top, 0.0)
        and is_equal_approx(control.anchor_right, 1.0)
        and is_equal_approx(control.anchor_bottom, 1.0)
    )


func _has_full_rect_control_children(control: Control) -> bool:
    for child in control.get_children():
        if child is Control and _is_full_rect_control_root(child):
            return true
    return false


func _estimated_control_scene_bounds(root: Control) -> Rect2:
    if root.size.x <= 1.0 or root.size.y <= 1.0:
        var inferred_root_size := _infer_control_root_size(root)
        if inferred_root_size.x > 1.0 and inferred_root_size.y > 1.0:
            root.size = inferred_root_size
    var bounds := Rect2(Vector2.ZERO, Vector2.ZERO)
    var have_bounds := false
    if root.size.x > 1.0 and root.size.y > 1.0:
        bounds = Rect2(Vector2.ZERO, root.size)
        have_bounds = true
    var accumulated: Array = _accumulate_canvas_bounds(root, Vector2.ZERO, bounds, have_bounds)
    bounds = accumulated[0]
    have_bounds = accumulated[1]
    if not have_bounds:
        return Rect2(Vector2.ZERO, Vector2(1, 1))
    return bounds


func _accumulate_canvas_bounds(node: Node, origin: Vector2, bounds: Rect2, have_bounds: bool) -> Array:
    var current_bounds := bounds
    var current_have_bounds := have_bounds
    for child in node.get_children():
        var child_origin := origin
        var child_rect := Rect2()
        var child_has_rect := false
        if child is Control:
            var control: Control = child
            var parent_size := Vector2.ZERO
            if node is Control:
                parent_size = (node as Control).size
            var control_rect := _control_authored_rect(control, parent_size)
            child_origin += control_rect.position
            var control_size := control_rect.size
            if control_size.x <= 1.0 or control_size.y <= 1.0:
                control_size = control.get_combined_minimum_size()
            if control_size.x > 0.0 and control_size.y > 0.0:
                child_rect = Rect2(child_origin, control_size)
                child_has_rect = true
        elif child is Sprite2D:
            var sprite: Sprite2D = child
            child_origin += sprite.position
            if sprite.texture != null:
                var texture_size := sprite.texture.get_size() * sprite.scale.abs()
                var top_left := child_origin
                if sprite.centered:
                    top_left -= texture_size * 0.5
                child_rect = Rect2(top_left, texture_size)
                child_has_rect = true
        elif child is Node2D:
            var node_2d: Node2D = child
            child_origin += node_2d.position

        if child_has_rect:
            if current_have_bounds:
                current_bounds = current_bounds.merge(child_rect)
            else:
                current_bounds = child_rect
                current_have_bounds = true

        if child.get_child_count() > 0:
            var nested := _accumulate_canvas_bounds(child, child_origin, current_bounds, current_have_bounds)
            current_bounds = nested[0]
            current_have_bounds = nested[1]

    return [current_bounds, current_have_bounds]


func _infer_control_root_size(root: Control) -> Vector2:
    var inferred := Vector2.ZERO
    for child in root.get_children():
        if child is Sprite2D:
            var sprite: Sprite2D = child
            if sprite.texture != null:
                var sprite_size := sprite.texture.get_size() * sprite.scale.abs()
                inferred.x = max(inferred.x, sprite_size.x)
                inferred.y = max(inferred.y, sprite_size.y)
        elif child is Control:
            var control: Control = child
            inferred.x = max(inferred.x, control.get_combined_minimum_size().x)
            inferred.y = max(inferred.y, control.get_combined_minimum_size().y)
    return inferred


func _control_authored_rect(control: Control, parent_size: Vector2) -> Rect2:
    var left := parent_size.x * control.anchor_left + control.offset_left
    var top := parent_size.y * control.anchor_top + control.offset_top
    var right := parent_size.x * control.anchor_right + control.offset_right
    var bottom := parent_size.y * control.anchor_bottom + control.offset_bottom
    var width := right - left
    var height := bottom - top
    if width <= 1.0 or height <= 1.0:
        var min_size := control.get_combined_minimum_size()
        width = max(width, min_size.x)
        height = max(height, min_size.y)
    return Rect2(Vector2(left, top), Vector2(max(0.0, width), max(0.0, height)))


func _apply_imported_scene_tokens(root_node: Node) -> void:
    var nodes: Array = []
    _collect_imported_scene_token_nodes(root_node, nodes)
    for node in nodes:
        _apply_token_text_to_node(node)


func _refresh_imported_scene_tokens(root_node: Node, key: String) -> void:
    var nodes: Array = []
    _collect_imported_scene_token_nodes(root_node, nodes)
    for node in nodes:
        var template_text := str(node.get_meta("pinballctl_template_text", ""))
        if template_text.find("{{%s}}" % key.to_upper()) >= 0 or template_text.find("{{%s}}" % str(key)) >= 0:
            _apply_token_text_to_node(node)


func _collect_imported_scene_token_nodes(root_node: Node, out: Array) -> void:
    for child in root_node.get_children():
        if child is Label:
            var label: Label = child
            if not label.has_meta("pinballctl_template_text"):
                var initial_text := str(label.text)
                if initial_text.find("{{") >= 0 and initial_text.find("}}") >= 0:
                    label.set_meta("pinballctl_template_text", initial_text)
            if label.has_meta("pinballctl_template_text"):
                out.append(label)
        _collect_imported_scene_token_nodes(child, out)


func _apply_token_text_to_node(node: Node) -> void:
    if not (node is Label):
        return
    var label: Label = node
    var template_text := str(label.get_meta("pinballctl_template_text", ""))
    if template_text.is_empty():
        return
    var resolved := template_text
    for token_key in text_values.keys():
        resolved = resolved.replace("{{%s}}" % str(token_key).to_upper(), str(text_values.get(token_key, "")))
        resolved = resolved.replace("{{%s}}" % str(token_key), str(text_values.get(token_key, "")))
    label.text = resolved


func _dispatch_action_to_node(root_node: Node, action: String, phase: String) -> bool:
    if root_node.has_method("pinballctl_input_action") and phase != "release":
        root_node.call("pinballctl_input_action", action)
        return true
    for child in root_node.get_children():
        if _dispatch_action_to_node(child, action, phase):
            return true
    return false


func _bind_scene_runtime_events(root_node: Node) -> void:
    if not root_node or not is_instance_valid(root_node):
        return
    _bind_scene_runtime_events_recursive(root_node)


func _bind_scene_runtime_events_recursive(node: Node) -> void:
    if not node or not is_instance_valid(node):
        return
    if node.has_signal("pinballctl_custom_event"):
        var custom_callable := Callable(self, "_on_scene_custom_event").bind(node)
        if not node.is_connected("pinballctl_custom_event", custom_callable):
            node.connect("pinballctl_custom_event", custom_callable)
    if node.has_signal("pinballctl_focus_changed"):
        var focus_callable := Callable(self, "_on_scene_focus_changed").bind(node)
        if not node.is_connected("pinballctl_focus_changed", focus_callable):
            node.connect("pinballctl_focus_changed", focus_callable)
    for child in node.get_children():
        _bind_scene_runtime_events_recursive(child)


func _on_scene_custom_event(event_name: String, event_params: Dictionary = {}, origin_node: Node = null) -> void:
    if runtime_event_sink and runtime_event_sink.has_method("emit_scene_custom_event"):
        runtime_event_sink.call("emit_scene_custom_event", str(event_name).strip_edges(), event_params, _scene_event_meta(origin_node))


func _on_scene_focus_changed(mode_name: String, mode_index: int, origin_node: Node = null) -> void:
    if runtime_event_sink and runtime_event_sink.has_method("emit_scene_custom_event"):
        runtime_event_sink.call(
            "emit_scene_custom_event",
            "GODOT_SCENE_FOCUS_CHANGED",
            {
                "modeName": mode_name,
                "modeIndex": mode_index,
            },
            _scene_event_meta(origin_node),
        )


func _scene_event_meta(origin_node: Node = null) -> Dictionary:
    return {
        "sceneKey": current_scene_key,
        "originNode": origin_node.name if origin_node and is_instance_valid(origin_node) else "",
    }


func _inject_input_action(action: String, phase: String) -> Dictionary:
    var press_event := InputEventAction.new()
    press_event.action = action
    press_event.pressed = phase != "release"
    press_event.strength = 1.0 if press_event.pressed else 0.0
    if phase == "tap":
        Input.parse_input_event(press_event)
        var release_event := InputEventAction.new()
        release_event.action = action
        release_event.pressed = false
        release_event.strength = 0.0
        Input.parse_input_event(release_event)
    else:
        Input.parse_input_event(press_event)
    return {"ok": true, "action": action, "phase": phase, "delivered": true, "mode": "input_event"}


func _dispatch_key_to_node(root_node: Node, key_name: String, phase: String) -> bool:
    if root_node.has_method("pinballctl_input_key") and phase != "release":
        root_node.call("pinballctl_input_key", key_name)
        return true
    for child in root_node.get_children():
        if _dispatch_key_to_node(child, key_name, phase):
            return true
    return false


func _inject_input_key(key_name: String, phase: String) -> Dictionary:
    var keycode := _resolve_keycode(key_name)
    if keycode == KEY_NONE:
        return {"ok": false, "error": "invalid_key", "key": key_name}
    var press_event := InputEventKey.new()
    press_event.keycode = keycode
    press_event.pressed = phase != "release"
    if key_name.length() == 1:
        press_event.unicode = key_name.unicode_at(0)
    if phase == "tap":
        Input.parse_input_event(press_event)
        var release_event := InputEventKey.new()
        release_event.keycode = keycode
        release_event.pressed = false
        if key_name.length() == 1:
            release_event.unicode = key_name.unicode_at(0)
        Input.parse_input_event(release_event)
    else:
        Input.parse_input_event(press_event)
    return {"ok": true, "key": key_name, "phase": phase, "delivered": true, "mode": "input_event"}


func _resolve_keycode(key_name: String) -> int:
    var normalized := key_name.strip_edges()
    if normalized.is_empty():
        return KEY_NONE
    var lowered := normalized.to_lower()
    match lowered:
        "left", "arrowleft", "leftarrow":
            return KEY_LEFT
        "right", "arrowright", "rightarrow":
            return KEY_RIGHT
        "up", "arrowup", "uparrow":
            return KEY_UP
        "down", "arrowdown", "downarrow":
            return KEY_DOWN
        "enter", "return":
            return KEY_ENTER
        "escape", "esc":
            return KEY_ESCAPE
        "space", "spacebar":
            return KEY_SPACE
        "tab":
            return KEY_TAB
        "backspace":
            return KEY_BACKSPACE
        "delete", "del":
            return KEY_DELETE
        "home":
            return KEY_HOME
        "end":
            return KEY_END
        "pageup":
            return KEY_PAGEUP
        "pagedown":
            return KEY_PAGEDOWN
    var resolved := OS.find_keycode_from_string(normalized)
    if resolved != KEY_NONE:
        return resolved
    if normalized.length() == 1:
        return OS.find_keycode_from_string(normalized.to_upper())
    return KEY_NONE
