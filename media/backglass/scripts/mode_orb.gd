extends Control

# Small reusable visual for each selectable mode in the carousel.
#
# This script intentionally has a tiny public API:
# - `set_label_text(...)`
# - `set_visual_state(focused, selected)`
#
# That keeps the parent menu script easy to read.

const LABEL_FONT_SIZE_FOCUSED := 38
const LABEL_FONT_SIZE_IDLE := 28

const COLOR_FONT_SELECTED := Color(1.0, 0.98, 0.9, 1.0)
const COLOR_FONT_IDLE := Color(0.93, 0.98, 1.0, 0.96)
const COLOR_OUTLINE := Color(0.02, 0.05, 0.09, 0.7)

const COLOR_BASE := Color(0.44, 0.86, 1.0, 0.26)
const COLOR_GLOW := Color(0.72, 0.95, 1.0, 0.18)
const COLOR_HIGHLIGHT := Color(1.0, 1.0, 1.0, 0.14)
const COLOR_SHADOW := Color(0.12, 0.24, 0.33, 0.12)
const COLOR_FOCUS_OUTLINE := Color(0.82, 0.98, 1.0, 0.92)
const COLOR_IDLE_OUTLINE := Color(0.69, 0.9, 1.0, 0.55)
const COLOR_SELECTION := Color(1.0, 0.83, 0.36, 0.95)
const COLOR_SELECTION_GLOW := Color(1.0, 0.91, 0.58, 0.34)

var label_text := "MODE"
var is_focused := false
var is_selected := false

@onready var label: Label = Label.new()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	# Build the label in code so this sample stays self-contained.
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	label.add_theme_color_override("font_outline_color", COLOR_OUTLINE)
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
	label.add_theme_font_size_override(
		"font_size",
		LABEL_FONT_SIZE_FOCUSED if is_focused else LABEL_FONT_SIZE_IDLE,
	)
	label.add_theme_color_override(
		"font_color",
		COLOR_FONT_SELECTED if is_selected else COLOR_FONT_IDLE,
	)


func _draw() -> void:
	# The orb is drawn procedurally so users can easily swap the look without
	# having to chase textures or shader files.
	var center := size * 0.5
	var radius := minf(size.x, size.y) * 0.5 - 6.0
	var outline_color := COLOR_FOCUS_OUTLINE if is_focused else COLOR_IDLE_OUTLINE

	draw_circle(center, radius, COLOR_BASE)
	draw_circle(center + Vector2(0, radius * 0.08), radius * 0.82, COLOR_GLOW)
	draw_circle(center + Vector2(-radius * 0.18, -radius * 0.22), radius * 0.45, COLOR_HIGHLIGHT)
	draw_circle(center + Vector2(radius * 0.28, radius * 0.34), radius * 0.64, COLOR_SHADOW)
	draw_arc(center, radius - 4.0, 0.0, TAU, 64, outline_color, 4.0, true)
	draw_arc(center + Vector2(-radius * 0.14, -radius * 0.18), radius * 0.72, PI * 1.08, PI * 1.72, 28, Color(1.0, 1.0, 1.0, 0.18), 6.0, true)

	if is_selected:
		draw_arc(center, radius + 8.0, 0.0, TAU, 72, COLOR_SELECTION, 8.0, true)
		draw_arc(center, radius + 18.0, PI * 0.18, PI * 0.82, 24, COLOR_SELECTION_GLOW, 5.0, true)
