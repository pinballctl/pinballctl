extends Control

var overlay_nodes: Array = []
var overlay_values: Dictionary = {}
var overlay_layers: Array = []
var overlay_visibility: Dictionary = {}
var last_viewport_size: Vector2 = Vector2.ZERO


func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_IGNORE
    last_viewport_size = get_viewport_rect().size


func _process(_delta: float) -> void:
    var current_size := get_viewport_rect().size
    if current_size != last_viewport_size:
        last_viewport_size = current_size
        _rerender()


func show_overlay(overlay_id: String, position: Dictionary = {}) -> Dictionary:
    overlay_visibility[str(overlay_id)] = true
    if position.has("x") or position.has("y"):
        for layer in overlay_layers:
            if layer is Dictionary and str(layer.get("overlayId", "")) == str(overlay_id):
                if position.has("x"):
                    layer["xPct"] = max(0.0, min(100.0, float(position.get("x", 0))))
                if position.has("y"):
                    layer["yPct"] = max(0.0, min(100.0, float(position.get("y", 0))))
    _rerender()
    return {"ok": true, "overlay": {"id": overlay_id, "visible": true}}


func hide_overlay(overlay_id: String) -> Dictionary:
    overlay_visibility[str(overlay_id)] = false
    _rerender()
    return {"ok": true, "overlay": {"id": overlay_id, "visible": false}}


func update_text(key: String, value: Variant) -> Dictionary:
    overlay_values[key] = value
    if not overlay_visibility.has(str(key)):
        overlay_visibility[str(key)] = true
    _rerender()
    return {"ok": true, "text": {"key": key, "value": value}}


func status() -> Dictionary:
    return {
        "overlayValues": overlay_values,
    }


func apply_state(layers: Array, values: Dictionary, visibility: Dictionary = {}) -> Dictionary:
    overlay_layers = []
    for entry in layers:
        if entry is Dictionary:
            overlay_layers.append(entry)
    overlay_values = values.duplicate(true)
    overlay_visibility = {}
    for key in visibility.keys():
        overlay_visibility[str(key)] = bool(visibility.get(key, true))
    _rerender()
    return {"ok": true, "overlayValues": overlay_values}


func _rerender() -> void:
    for node in overlay_nodes:
        if is_instance_valid(node):
            node.queue_free()
    overlay_nodes.clear()
    var viewport_size := get_viewport_rect().size
    for layer in overlay_layers:
        if not (layer is Dictionary):
            continue
        var overlay_id := str(layer.get("overlayId", layer.get("id", "")))
        if overlay_visibility.has(overlay_id) and not bool(overlay_visibility.get(overlay_id, true)):
            continue
        var layer_type := str(layer.get("type", "text")).to_lower()
        if layer_type == "image":
            _render_image_layer(layer, viewport_size)
        else:
            _render_text_layer(layer, viewport_size)


func _render_text_layer(layer: Dictionary, viewport_size: Vector2) -> void:
    var slot := _make_slot(layer, viewport_size)
    var background := ColorRect.new()
    background.set_anchors_preset(Control.PRESET_FULL_RECT)
    background.mouse_filter = Control.MOUSE_FILTER_IGNORE
    background.color = _color_with_alpha(str(layer.get("bgColor", "transparent")), float(layer.get("opacity", 1.0)))
    slot.add_child(background)

    var label := Label.new()
    label.name = str(layer.get("id", "overlay_text"))
    label.visible = true
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
    overlay_nodes.append(slot)


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
    rect.name = str(layer.get("id", "overlay_image"))
    rect.texture = texture
    rect.set_anchors_preset(Control.PRESET_FULL_RECT)
    rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
    rect.modulate = Color(1, 1, 1, max(0.0, min(1.0, float(layer.get("opacity", 1.0)))))
    rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    rect.stretch_mode = _texture_stretch_mode(str(layer.get("fit", "contain")))
    slot.add_child(rect)
    add_child(slot)
    overlay_nodes.append(slot)


func _make_slot(layer: Dictionary, viewport_size: Vector2) -> Control:
    var slot := Control.new()
    slot.name = str(layer.get("id", "overlay_slot"))
    slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
    slot.position = Vector2(viewport_size.x * float(layer.get("xPct", 0.0)) / 100.0, viewport_size.y * float(layer.get("yPct", 0.0)) / 100.0)
    slot.size = Vector2(
        max(1.0, viewport_size.x * float(layer.get("wPct", 20.0)) / 100.0),
        max(1.0, viewport_size.y * float(layer.get("hPct", 8.0)) / 100.0)
    )
    slot.rotation_degrees = float(layer.get("rotateDeg", 0.0))
    slot.scale = Vector2.ONE * max(0.1, float(layer.get("scale", 1.0)))
    return slot


func _text_for_layer(layer: Dictionary) -> String:
    var value_key := str(layer.get("valueKey", ""))
    if not value_key.is_empty() and overlay_values.has(value_key):
        return str(overlay_values.get(value_key, ""))
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
