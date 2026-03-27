extends Control

var layer_nodes: Array = []
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
    _rerender()
    return {"ok": true, "text": {"key": key, "value": value}}


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
            _:
                _render_text_layer(layer, viewport_size)


func _render_text_layer(layer: Dictionary, viewport_size: Vector2) -> void:
    var slot := _make_slot(layer, viewport_size)
    slot.clip_contents = true

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

    add_child(slot)
    layer_nodes.append(slot)


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
    rect.stretch_mode = _texture_stretch_mode(str(layer.get("fit", "contain")))
    slot.add_child(rect)
    add_child(slot)
    layer_nodes.append(slot)


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
    player.expand = false
    player.autoplay = false
    player.loop = bool(layer.get("sceneLoop", playback_state.get("loop", false)))
    player.mouse_filter = Control.MOUSE_FILTER_IGNORE
    player.modulate = Color(1, 1, 1, _layer_opacity(layer))
    var stream := VideoStreamTheora.new()
    stream.file = asset_path
    player.stream = stream
    _apply_video_fit(slot, player, layer)
    slot.add_child(player)
    add_child(slot)
    layer_nodes.append(slot)

    if str(layer.get("state", playback_state.get("status", "playing"))).to_lower() == "paused":
        player.paused = true
    else:
        player.play()


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
    var rich := RichTextLabel.new()
    rich.name = str(layer.get("id", "scene_text"))
    rich.position = Vector2(TEXT_SLOT_PADDING, TEXT_SLOT_PADDING) + offset
    rich.size = Vector2(
        max(1.0, slot_size.x - (TEXT_SLOT_PADDING * 2.0)),
        max(1.0, slot_size.y - (TEXT_SLOT_PADDING * 2.0))
    )
    rich.mouse_filter = Control.MOUSE_FILTER_IGNORE
    rich.scroll_active = false
    rich.fit_content = false
    rich.clip_contents = true
    rich.bbcode_enabled = true
    rich.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    rich.text = _text_bbcode_for_layer(layer, apply_inline_effects)
    rich.modulate = color
    rich.add_theme_constant_override("line_separation", 0)
    var font_res: Variant = _font_resource_for_layer(layer)
    if font_res != null:
        rich.add_theme_font_override("normal_font", font_res)
    var fitted_size: int = _effective_text_font_size(layer, slot_size)
    rich.add_theme_font_size_override("normal_font_size", fitted_size)
    return rich


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


func _text_bbcode_for_layer(layer: Dictionary, apply_inline_effects: bool) -> String:
    var text := _text_for_layer(layer)
    var effects: Array = layer.get("textEffects", []) if layer.get("textEffects", []) is Array else []
    var effect_keys: Dictionary = {}
    for entry in effects:
        effect_keys[str(entry).to_lower()] = true
    if effect_keys.has("uppercase"):
        text = text.to_upper()
    if effect_keys.has("tracking"):
        text = _apply_tracking(text)
    text = text.replace("[", "\\[").replace("]", "\\]")
    if apply_inline_effects:
        if effect_keys.has("b") or effect_keys.has("bold"):
            text = "[b]%s[/b]" % text
        if effect_keys.has("i") or effect_keys.has("italic"):
            text = "[i]%s[/i]" % text
        if effect_keys.has("underline"):
            text = "[u]%s[/u]" % text
        if effect_keys.has("strike"):
            text = "[s]%s[/s]" % text
    var align := str(layer.get("textAlign", "center")).to_lower()
    if align == "left":
        return "[left]%s[/left]" % text
    if align == "right":
        return "[right]%s[/right]" % text
    return "[center]%s[/center]" % text


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


func _apply_video_fit(slot: Control, player: VideoStreamPlayer, layer: Dictionary) -> void:
    var fit := str(layer.get("fit", "contain")).to_lower()
    var asset: Dictionary = layer.get("asset", {}) if layer.get("asset", {}) is Dictionary else {}
    var asset_width: float = max(0.0, float(asset.get("width", 0)))
    var asset_height: float = max(0.0, float(asset.get("height", 0)))
    var frame_size := slot.size
    if frame_size.x <= 0 or frame_size.y <= 0:
        player.set_anchors_preset(Control.PRESET_FULL_RECT)
        return
    if asset_width <= 0 or asset_height <= 0 or fit == "fill":
        player.set_anchors_preset(Control.PRESET_FULL_RECT)
        return
    var scale_factor := 1.0
    var contain_scale: float = min(frame_size.x / asset_width, frame_size.y / asset_height)
    var cover_scale: float = max(frame_size.x / asset_width, frame_size.y / asset_height)
    match fit:
        "cover":
            scale_factor = cover_scale
        "none":
            scale_factor = 1.0
        "scale-down":
            scale_factor = min(1.0, contain_scale)
        _:
            scale_factor = contain_scale
    var target_size := Vector2(asset_width * scale_factor, asset_height * scale_factor)
    player.position = (frame_size - target_size) / 2.0
    player.size = target_size


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


func _texture_stretch_mode(value: String) -> int:
    match value.to_lower():
        "cover":
            return TextureRect.STRETCH_KEEP_ASPECT_COVERED
        "fill":
            return TextureRect.STRETCH_SCALE
        "none":
            return TextureRect.STRETCH_KEEP
        "scale-down":
            return TextureRect.STRETCH_KEEP_ASPECT_CENTERED
        _:
            return TextureRect.STRETCH_KEEP_ASPECT_CENTERED


func _color_with_alpha(raw: String, alpha: float) -> Color:
    if str(raw).strip_edges().to_lower() == "transparent":
        return Color(1, 1, 1, 0)
    var color := Color.WHITE
    if Color.html_is_valid(raw):
        color = Color(raw)
    color.a = max(0.0, min(1.0, alpha))
    return color
