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


func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_IGNORE
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

    var background := ColorRect.new()
    background.set_anchors_preset(Control.PRESET_FULL_RECT)
    background.mouse_filter = Control.MOUSE_FILTER_IGNORE
    background.color = _color_with_alpha(str(layer.get("bgColor", "transparent")), float(layer.get("opacity", 1.0)))
    slot.add_child(background)

    var label := Label.new()
    label.name = str(layer.get("id", "scene_text"))
    label.set_anchors_preset(Control.PRESET_FULL_RECT)
    label.mouse_filter = Control.MOUSE_FILTER_IGNORE
    label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    label.clip_text = false
    label.text = _text_for_layer(layer)
    label.horizontal_alignment = _text_alignment(str(layer.get("textAlign", "center")))
    label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    label.add_theme_font_size_override("font_size", max(8, int(layer.get("fontSizePx", 28))))
    label.modulate = _color_with_alpha(str(layer.get("color", "#ffffff")), float(layer.get("opacity", 1.0)))
    slot.add_child(label)

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
    rect.modulate = Color(1, 1, 1, max(0.0, min(1.0, float(layer.get("opacity", 1.0)))))
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
    var player := VideoStreamPlayer.new()
    player.name = str(layer.get("id", "scene_video"))
    player.expand = true
    player.autoplay = false
    player.loop = bool(playback_state.get("loop", false))
    player.set_anchors_preset(Control.PRESET_FULL_RECT)
    player.mouse_filter = Control.MOUSE_FILTER_IGNORE
    player.modulate = Color(1, 1, 1, max(0.0, min(1.0, float(layer.get("opacity", 1.0)))))
    var stream := VideoStreamTheora.new()
    stream.file = asset_path
    player.stream = stream
    slot.add_child(player)
    add_child(slot)
    layer_nodes.append(slot)

    if str(playback_state.get("status", "playing")).to_lower() == "paused":
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
    slot.scale = Vector2.ONE * max(0.1, float(layer.get("scale", 1.0)))
    slot.z_index = int(layer.get("zIndex", 0))
    return slot


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
