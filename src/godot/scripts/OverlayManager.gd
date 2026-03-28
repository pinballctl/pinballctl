extends Control

var layer_nodes: Array = []
var layer_slots: Dictionary = {}
var mounted_packs: Dictionary = {}
var text_values: Dictionary = {}
var scene_layers: Array = []
var playback_state: Dictionary = {
    "status": "stopped",
    "mediaKey": "",
    "loop": false,
    "positionMs": 0,
}
var last_viewport_size: Vector2 = Vector2.ZERO
var font_cache: Dictionary = {}
const TEXT_SLOT_PADDING: float = 5.0


func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_IGNORE
    set_anchors_preset(Control.PRESET_FULL_RECT)
    last_viewport_size = get_viewport_rect().size


func _process(_delta: float) -> void:
    var current_size := get_viewport_rect().size
    if current_size != last_viewport_size:
        last_viewport_size = current_size
        _rerender()


func update_text(key: String, value: Variant) -> Dictionary:
    text_values[key] = value
    var updated: bool = _refresh_text_layers_for_key(key)
    if not updated:
        _rerender()
    return {"ok": true, "text": {"key": key, "value": value}, "overlayValues": text_values.duplicate(true)}


func status() -> Dictionary:
    return {
        "overlayValues": text_values.duplicate(true),
        "playback": playback_state.duplicate(true),
    }


func apply_state(layers: Array, values: Dictionary, playback: Dictionary = {}) -> Dictionary:
    scene_layers = []
    for entry in layers:
        if entry is Dictionary:
            scene_layers.append(entry)
    text_values = values.duplicate(true)
    playback_state = {
        "status": str(playback.get("status", "stopped")),
        "mediaKey": str(playback.get("mediaKey", "")),
        "loop": bool(playback.get("loop", false)),
        "positionMs": int(playback.get("positionMs", 0)),
    }
    _rerender()
    return {"ok": true, "overlayValues": text_values, "playback": playback_state}


func _rerender() -> void:
    for node in layer_nodes:
        if is_instance_valid(node):
            node.queue_free()
    layer_nodes.clear()
    layer_slots.clear()

    var viewport_size := get_viewport_rect().size
    var ordered_layers: Array = scene_layers.duplicate(true)
    ordered_layers.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
        return int(a.get("zIndex", 0)) < int(b.get("zIndex", 0))
    )

    for layer in ordered_layers:
        if not (layer is Dictionary):
            continue
        var layer_type := str(layer.get("type", "text")).to_lower()
        match layer_type:
            "image":
                _render_image_layer(layer, viewport_size)
            "video":
                _render_video_layer(layer, viewport_size)
            "godot_scene":
                _render_godot_scene_layer(layer, viewport_size)
            _:
                _render_text_layer(layer, viewport_size)


func _render_text_layer(layer: Dictionary, viewport_size: Vector2) -> void:
    var slot := _make_slot(layer, viewport_size)
    slot.clip_contents = true
    slot.set_meta("layer_data", layer.duplicate(true))
    _populate_text_slot(slot, layer)
    add_child(slot)
    layer_nodes.append(slot)
    layer_slots[str(layer.get("id", ""))] = slot


func _render_image_layer(layer: Dictionary, viewport_size: Vector2) -> void:
    var asset_path := str(layer.get("assetPath", ""))
    if asset_path.is_empty():
        return
    var image := Image.new()
    if image.load(asset_path) != OK:
        return
    var texture := ImageTexture.create_from_image(image)
    var slot := _make_slot(layer, viewport_size)
    var rect := TextureRect.new()
    rect.name = str(layer.get("id", "scene_image"))
    rect.texture = texture
    rect.set_anchors_preset(Control.PRESET_FULL_RECT)
    rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
    rect.modulate = Color(1, 1, 1, _layer_opacity(layer))
    rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    rect.stretch_mode = TextureRect.STRETCH_SCALE
    slot.add_child(rect)
    add_child(slot)
    layer_nodes.append(slot)
    layer_slots[str(layer.get("id", ""))] = slot


func _render_video_layer(layer: Dictionary, viewport_size: Vector2) -> void:
    var asset_path := str(layer.get("assetPath", ""))
    if asset_path.is_empty():
        return
    var ext := asset_path.get_extension().to_lower()
    if ext not in ["ogv", "ogg"]:
        return
    var slot := _make_slot(layer, viewport_size)
    slot.clip_contents = true
    var player := VideoStreamPlayer.new()
    player.name = str(layer.get("id", "scene_video"))
    player.expand = true
    player.autoplay = false
    player.loop = bool(layer.get("sceneLoop", playback_state.get("loop", false)))
    player.mouse_filter = Control.MOUSE_FILTER_IGNORE
    player.modulate = Color(1, 1, 1, _layer_opacity(layer))
    var stream := VideoStreamTheora.new()
    stream.file = asset_path
    player.stream = stream
    player.set_anchors_preset(Control.PRESET_FULL_RECT)
    slot.add_child(player)
    add_child(slot)
    layer_nodes.append(slot)
    layer_slots[str(layer.get("id", ""))] = slot

    if str(layer.get("state", playback_state.get("status", "playing"))).to_lower() == "paused":
        player.paused = true
    else:
        player.play()


func _render_godot_scene_layer(layer: Dictionary, viewport_size: Vector2) -> void:
    var slot := _make_slot(layer, viewport_size)
    slot.clip_contents = true
    slot.set_meta("layer_data", layer.duplicate(true))

    var scene_node := _instantiate_packed_layer_scene(layer)
    if scene_node == null:
        var background := ColorRect.new()
        background.set_anchors_preset(Control.PRESET_FULL_RECT)
        background.mouse_filter = Control.MOUSE_FILTER_IGNORE
        background.color = _color_with_alpha(str(layer.get("bgColor", "#13243a")), max(0.18, _layer_opacity(layer)))
        slot.add_child(background)
        slot.add_child(_make_imported_scene_placeholder(layer))
    elif scene_node is Control:
        var control_node: Control = scene_node
        control_node.mouse_filter = Control.MOUSE_FILTER_IGNORE
        slot.add_child(_make_embedded_scene_host(control_node, slot.size))
        _apply_imported_scene_tokens(control_node)
    else:
        var fallback_background := ColorRect.new()
        fallback_background.set_anchors_preset(Control.PRESET_FULL_RECT)
        fallback_background.mouse_filter = Control.MOUSE_FILTER_IGNORE
        fallback_background.color = _color_with_alpha(str(layer.get("bgColor", "#13243a")), max(0.18, _layer_opacity(layer)))
        slot.add_child(fallback_background)
        slot.add_child(_make_imported_scene_placeholder(layer, "Control root required"))

    add_child(slot)
    layer_nodes.append(slot)
    layer_slots[str(layer.get("id", ""))] = slot


func _populate_text_slot(slot: Control, layer: Dictionary) -> void:
    for child in slot.get_children():
        child.queue_free()

    var background := ColorRect.new()
    background.set_anchors_preset(Control.PRESET_FULL_RECT)
    background.mouse_filter = Control.MOUSE_FILTER_IGNORE
    background.color = _color_with_alpha(str(layer.get("bgColor", "transparent")), _layer_opacity(layer))
    slot.add_child(background)

    var effects: Array = layer.get("textEffects", []) if layer.get("textEffects", []) is Array else []
    var effect_keys: Dictionary = {}
    for entry in effects:
        effect_keys[str(entry).to_lower()] = true

    if effect_keys.has("shadow"):
        slot.add_child(_make_text_node(layer, _effect_text_color(layer, 0.72), Vector2(2, 2), false, slot.size))
    if effect_keys.has("glow"):
        for offset in [Vector2(-2, 0), Vector2(2, 0), Vector2(0, -2), Vector2(0, 2)]:
            slot.add_child(_make_text_node(layer, _effect_text_color(layer, 0.22), offset, false, slot.size))
    if effect_keys.has("outline"):
        for offset in [Vector2(-1, 0), Vector2(1, 0), Vector2(0, -1), Vector2(0, 1), Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
            slot.add_child(_make_text_node(layer, _effect_text_color(layer, 0.9), offset, false, slot.size))
    if effect_keys.has("bold"):
        slot.add_child(_make_text_node(layer, _main_text_color(layer), Vector2(1, 0), false, slot.size))

    slot.add_child(_make_text_node(layer, _main_text_color(layer), Vector2.ZERO, true, slot.size))
    if effect_keys.has("underline"):
        slot.add_child(_make_decoration_line(layer, 0.84))
    if effect_keys.has("strike"):
        slot.add_child(_make_decoration_line(layer, 0.5))


func _refresh_text_layers_for_key(key: String) -> bool:
    var updated: bool = false
    for layer in scene_layers:
        if not (layer is Dictionary):
            continue
        var layer_type := str(layer.get("type", "text")).to_lower()
        if layer_type == "text":
            if str(layer.get("valueKey", "")).strip_edges() != key:
                continue
        elif layer_type != "godot_scene":
            continue
        var layer_id := str(layer.get("id", "")).strip_edges()
        if layer_id.is_empty():
            continue
        var slot: Variant = layer_slots.get(layer_id, null)
        if not (slot is Control and is_instance_valid(slot)):
            continue
        if layer_type == "text":
            slot.set_meta("layer_data", layer.duplicate(true))
            _populate_text_slot(slot, layer)
            updated = true
        elif _refresh_imported_scene_layer(slot, key):
            updated = true
    return updated


func _instantiate_packed_layer_scene(layer: Dictionary) -> Node:
    var pack_path := str(layer.get("assetPath", "")).strip_edges()
    var scene_path := str(layer.get("sceneEntryPath", "")).strip_edges()
    if pack_path.is_empty() or scene_path.is_empty():
        return null
    if not mounted_packs.has(pack_path):
        mounted_packs[pack_path] = ProjectSettings.load_resource_pack(pack_path)
    if not bool(mounted_packs.get(pack_path, false)):
        return null
    var packed_scene: PackedScene = load(scene_path)
    if packed_scene == null:
        return null
    return packed_scene.instantiate()


func _make_embedded_scene_host(control_node: Control, slot_size: Vector2) -> Control:
    var host := Control.new()
    host.set_anchors_preset(Control.PRESET_FULL_RECT)
    host.mouse_filter = Control.MOUSE_FILTER_IGNORE
    host.clip_contents = true

    var authored_bounds := _estimated_control_scene_bounds(control_node)
    var base_size := authored_bounds.size
    if base_size.x <= 1.0 or base_size.y <= 1.0:
        base_size = slot_size
        authored_bounds = Rect2(Vector2.ZERO, slot_size)

    control_node.set_anchors_preset(Control.PRESET_TOP_LEFT)
    control_node.offset_left = 0
    control_node.offset_top = 0
    control_node.offset_right = 0
    control_node.offset_bottom = 0
    control_node.size = base_size

    var scale_x: float = slot_size.x / max(1.0, base_size.x)
    var scale_y: float = slot_size.y / max(1.0, base_size.y)
    control_node.scale = Vector2(scale_x, scale_y)
    control_node.position = Vector2(
        -authored_bounds.position.x * scale_x,
        -authored_bounds.position.y * scale_y
    )

    host.add_child(control_node)
    return host


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


func _make_imported_scene_placeholder(layer: Dictionary, subtitle: String = "") -> Control:
    var wrap := Control.new()
    wrap.set_anchors_preset(Control.PRESET_FULL_RECT)
    wrap.mouse_filter = Control.MOUSE_FILTER_IGNORE
    var label := Label.new()
    label.set_anchors_preset(Control.PRESET_FULL_RECT)
    label.mouse_filter = Control.MOUSE_FILTER_IGNORE
    label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    label.add_theme_font_size_override("font_size", 22)
    label.modulate = Color(0.9, 0.95, 1.0, 0.92)
    var title := str(layer.get("asset", {}).get("displayName", "Godot Scene")).strip_edges()
    var entry := str(layer.get("sceneEntryPath", "")).strip_edges()
    var parts: Array[String] = [title]
    if not entry.is_empty():
        parts.append(entry)
    if not subtitle.is_empty():
        parts.append(subtitle)
    label.text = "\n".join(parts)
    wrap.add_child(label)
    return wrap


func _refresh_imported_scene_layer(slot: Control, key: String) -> bool:
    var nodes: Array = []
    _collect_imported_scene_token_nodes(slot, nodes)
    if nodes.is_empty():
        return false
    var updated: bool = false
    for node in nodes:
        var template_text := str(node.get_meta("pinballctl_template_text", ""))
        if template_text.find("{{%s}}" % key.to_upper()) >= 0 or template_text.find("{{%s}}" % str(key)) >= 0:
            _apply_token_text_to_node(node)
            updated = true
    return updated


func _apply_imported_scene_tokens(root_node: Node) -> void:
    var nodes: Array = []
    _collect_imported_scene_token_nodes(root_node, nodes)
    for node in nodes:
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


func _make_slot(layer: Dictionary, viewport_size: Vector2) -> Control:
    var slot := Control.new()
    slot.name = str(layer.get("id", "scene_layer"))
    slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
    slot.position = Vector2(
        viewport_size.x * float(layer.get("xPct", 0.0)) / 100.0,
        viewport_size.y * float(layer.get("yPct", 0.0)) / 100.0
    )
    slot.size = Vector2(
        max(1.0, viewport_size.x * float(layer.get("wPct", 20.0)) / 100.0),
        max(1.0, viewport_size.y * float(layer.get("hPct", 8.0)) / 100.0)
    )
    slot.rotation_degrees = float(layer.get("rotateDeg", 0.0))
    slot.scale = Vector2.ONE * max(0.1, float(layer.get("scale", 1.0)) * _transition_scale(layer))
    slot.z_index = int(layer.get("zIndex", 0))
    return slot


func _make_text_node(layer: Dictionary, color: Color, offset: Vector2, apply_inline_effects: bool, slot_size: Vector2) -> Control:
    var label := Label.new()
    label.name = str(layer.get("id", "scene_text"))
    label.position = Vector2(TEXT_SLOT_PADDING, TEXT_SLOT_PADDING) + offset
    label.size = Vector2(
        max(1.0, slot_size.x - (TEXT_SLOT_PADDING * 2.0)),
        max(1.0, slot_size.y - (TEXT_SLOT_PADDING * 2.0))
    )
    label.mouse_filter = Control.MOUSE_FILTER_IGNORE
    label.clip_text = false
    label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    label.horizontal_alignment = _text_alignment(str(layer.get("textAlign", "center")))
    label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    label.text = _text_display_for_layer(layer, apply_inline_effects)
    label.modulate = color
    var fitted_size: int = _effective_text_font_size(layer, slot_size)
    label.add_theme_font_size_override("font_size", fitted_size)
    var font_res: Variant = _font_resource_for_layer(layer)
    if font_res != null:
        label.add_theme_font_override("font", font_res)
    return label


func _effective_text_font_size(layer: Dictionary, slot_size: Vector2) -> int:
    var requested: int = max(8, int(layer.get("fontSizePx", 28)))
    var text: String = _text_for_layer(layer)
    var estimated_chars: int = max(1, text.length())
    if "tracking" in (layer.get("textEffects", []) if layer.get("textEffects", []) is Array else []):
        estimated_chars = int(estimated_chars * 1.35)
    var max_width: float = max(1.0, slot_size.x - (TEXT_SLOT_PADDING * 2.0))
    var max_height: float = max(1.0, slot_size.y - (TEXT_SLOT_PADDING * 2.0))
    var height_cap: int = max(8, int(max_height * 0.72))
    var width_cap: int = max(8, int(max_width / max(1.0, min(12.0, float(estimated_chars) * 0.62))))
    return max(8, min(height_cap, max(requested, width_cap)))


func _make_decoration_line(layer: Dictionary, y_ratio: float) -> ColorRect:
    var line := ColorRect.new()
    line.anchor_left = 0.15
    line.anchor_right = 0.85
    line.anchor_top = y_ratio
    line.anchor_bottom = y_ratio
    line.offset_top = -1
    line.offset_bottom = 1
    line.mouse_filter = Control.MOUSE_FILTER_IGNORE
    line.color = _main_text_color(layer)
    return line


func _text_display_for_layer(layer: Dictionary, apply_inline_effects: bool) -> String:
    var text := _text_for_layer(layer)
    var effects: Array = layer.get("textEffects", []) if layer.get("textEffects", []) is Array else []
    var effect_keys: Dictionary = {}
    for entry in effects:
        effect_keys[str(entry).to_lower()] = true
    if effect_keys.has("uppercase"):
        text = text.to_upper()
    if effect_keys.has("tracking"):
        text = _apply_tracking(text)
    if apply_inline_effects and (effect_keys.has("i") or effect_keys.has("italic")):
        text = "/%s/" % text
    return text


func _apply_tracking(text: String) -> String:
    var chars := text.split("")
    if chars.size() <= 1:
        return text
    return " ".join(chars)


func _font_resource_for_layer(layer: Dictionary) -> Variant:
    var font_data: Dictionary = layer.get("font", {}) if layer.get("font", {}) is Dictionary else {}
    var font_path := str(font_data.get("path", "")).strip_edges()
    var font_family := str(font_data.get("family", layer.get("fontFamily", ""))).strip_edges()
    var cache_key := "%s|%s" % [font_path, font_family]
    if font_cache.has(cache_key):
        return font_cache.get(cache_key)
    var font_res: Variant = null
    if not font_path.is_empty():
        var file_font := FontFile.new()
        if file_font.load_dynamic_font(font_path) == OK:
            font_res = file_font
    if font_res == null and not font_family.is_empty():
        var system_font := SystemFont.new()
        system_font.font_names = PackedStringArray([font_family])
        font_res = system_font
    font_cache[cache_key] = font_res
    return font_res


func _main_text_color(layer: Dictionary) -> Color:
    return _color_with_alpha(str(layer.get("color", "#ffffff")), _layer_opacity(layer))


func _effect_text_color(layer: Dictionary, alpha_scale: float) -> Color:
    var base := _main_text_color(layer)
    var luminance := (base.r * 0.2126) + (base.g * 0.7152) + (base.b * 0.0722)
    var target := Color.BLACK if luminance >= 0.56 else Color.WHITE
    target.a = clamp(base.a * alpha_scale, 0.0, 1.0)
    return target


func _layer_opacity(layer: Dictionary) -> float:
    return clamp(float(layer.get("opacity", 1.0)) * _transition_alpha(layer), 0.0, 1.0)


func _transition_alpha(layer: Dictionary) -> float:
    var transition: Dictionary = layer.get("transition", {}) if layer.get("transition", {}) is Dictionary else {}
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


func _transition_scale(layer: Dictionary) -> float:
    var transition: Dictionary = layer.get("transition", {}) if layer.get("transition", {}) is Dictionary else {}
    var duration_ms: int = max(0, int(transition.get("durationMs", 0)))
    var phase := str(transition.get("phase", "")).to_lower()
    var transition_type := str(transition.get("type", "CUT")).to_upper()
    var anchor_ms := int(transition.get("anchorMs", 0))
    if duration_ms <= 0 or phase.is_empty() or transition_type != "ZOOM" or anchor_ms <= 0:
        return 1.0
    var now_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
    var progress: float = clamp(float(now_ms - anchor_ms) / float(duration_ms), 0.0, 1.0)
    if phase == "out":
        return lerp(1.0, 1.08, progress)
    return lerp(0.92, 1.0, progress)


func _text_for_layer(layer: Dictionary) -> String:
    var value_key := str(layer.get("valueKey", ""))
    if not value_key.is_empty() and text_values.has(value_key):
        return str(text_values.get(value_key, ""))
    return str(layer.get("text", ""))


func _text_alignment(value: String) -> HorizontalAlignment:
    match value.to_lower():
        "left":
            return HORIZONTAL_ALIGNMENT_LEFT
        "right":
            return HORIZONTAL_ALIGNMENT_RIGHT
        _:
            return HORIZONTAL_ALIGNMENT_CENTER


func _color_with_alpha(raw: String, alpha: float) -> Color:
    if str(raw).strip_edges().to_lower() == "transparent":
        return Color(1, 1, 1, 0)
    var color := Color.WHITE
    if Color.html_is_valid(raw):
        color = Color(raw)
    color.a = max(0.0, min(1.0, alpha))
    return color
