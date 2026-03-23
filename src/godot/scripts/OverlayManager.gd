extends Control

var overlays: Dictionary = {}
var overlay_values: Dictionary = {}


func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_IGNORE


func _ensure_label(overlay_id: String) -> Label:
    if overlays.has(overlay_id):
        return overlays[overlay_id]
    var label := Label.new()
    label.name = overlay_id
    label.visible = false
    label.position = Vector2(48, 48 + overlays.size() * 42)
    label.add_theme_font_size_override("font_size", 30)
    add_child(label)
    overlays[overlay_id] = label
    return label


func show_overlay(overlay_id: String, position: Dictionary = {}) -> Dictionary:
    var label := _ensure_label(overlay_id)
    label.visible = true
    if position.has("x"):
        label.position.x = float(position.get("x", 0))
    if position.has("y"):
        label.position.y = float(position.get("y", 0))
    return {"ok": true, "overlay": {"id": overlay_id, "visible": true}}


func hide_overlay(overlay_id: String) -> Dictionary:
    var label := _ensure_label(overlay_id)
    label.visible = false
    return {"ok": true, "overlay": {"id": overlay_id, "visible": false}}


func update_text(key: String, value: Variant) -> Dictionary:
    overlay_values[key] = value
    var label := _ensure_label(key)
    label.text = str(value)
    label.visible = true
    return {"ok": true, "text": {"key": key, "value": value}}


func status() -> Dictionary:
    return {
        "overlayValues": overlay_values,
    }
