extends Control

var label_text: String = "MODE"
var is_focused := false
var is_selected := false

@onready var label: Label = Label.new()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	label.add_theme_color_override("font_outline_color", Color(0.02, 0.05, 0.09, 0.7))
	label.add_theme_constant_override("outline_size", 6)
	add_child(label)
	_update_label()


func set_label_text(value: String) -> void:
	label_text = value
	_update_label()
	queue_redraw()


func set_visual_state(focused: bool, selected: bool) -> void:
	if is_focused == focused and is_selected == selected:
		return

	is_focused = focused
	is_selected = selected
	_update_label()
	queue_redraw()


func _update_label() -> void:
	if not is_node_ready():
		return

	label.text = label_text
	label.add_theme_font_size_override("font_size", 26 if is_focused else 20)
	label.add_theme_color_override("font_color", Color(1.0, 0.98, 0.9, 1.0) if is_selected else Color(0.93, 0.98, 1.0, 0.96))


func _draw() -> void:
	var center := size * 0.5
	var radius: float = minf(size.x, size.y) * 0.5 - 6.0
	var base_color := Color(0.44, 0.86, 1.0, 0.26)
	var glow_color := Color(0.72, 0.95, 1.0, 0.18)
	var outline_color := Color(0.82, 0.98, 1.0, 0.92) if is_focused else Color(0.69, 0.9, 1.0, 0.55)
	var selection_color := Color(1.0, 0.83, 0.36, 0.95)

	draw_circle(center, radius, base_color)
	draw_circle(center + Vector2(0, radius * 0.08), radius * 0.82, glow_color)
	draw_circle(center + Vector2(-radius * 0.18, -radius * 0.22), radius * 0.45, Color(1.0, 1.0, 1.0, 0.14))
	draw_circle(center + Vector2(radius * 0.28, radius * 0.34), radius * 0.64, Color(0.12, 0.24, 0.33, 0.12))
	draw_arc(center, radius - 4.0, 0.0, TAU, 64, outline_color, 4.0, true)
	draw_arc(center + Vector2(-radius * 0.14, -radius * 0.18), radius * 0.72, PI * 1.08, PI * 1.72, 28, Color(1.0, 1.0, 1.0, 0.18), 6.0, true)

	if is_selected:
		draw_arc(center, radius + 8.0, 0.0, TAU, 72, selection_color, 8.0, true)
		draw_arc(center, radius + 18.0, PI * 0.18, PI * 0.82, 24, Color(1.0, 0.91, 0.58, 0.34), 5.0, true)
