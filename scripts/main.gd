extends Control

# Sample backglass menu scene for pinballctl.
#
# This file demonstrates three separate concerns:
# 1. Local menu behaviour in plain Godot.
# 2. Optional pinballctl input hooks (`pinballctl_input_action` / `pinballctl_input_key`).
# 3. Optional custom events emitted back to pinballctl when focus changes.
#
# Keep this scene keyboard-friendly during development. pinballctl should mirror
# the same actions/keys at runtime rather than replacing them with scene-specific
# logic.

const ORB_SCENE: PackedScene = preload("res://scenes/mode_orb.tscn")
const MODE_NAMES := [
	"CLASSIC",
	"MULTIBALL",
	"TIME ATTACK",
	"WIZARD",
	"PRACTICE",
	"CHALLENGE",
]

# Layout tuning for the simple horizontal carousel.
const DEFAULT_FOCUSED_INDEX := 2
const ORB_BASE_SIZE := 220.0
const ORB_MAX_SPACING := 280.0
const ORB_SPACING_RATIO := 0.17
const ORB_MAX_SCALE := 1.24
const ORB_SCALE_STEP := 0.26
const ORB_MIN_SCALE := 0.22
const ORB_Y_STEP := 18.0
const ORB_MAX_ALPHA := 0.92
const ORB_ALPHA_STEP := 0.14
const ORB_MIN_ALPHA := 0.28
const SETTLE_SPEED := 9.0

# Emitted when the user activates the current item.
signal mode_selected(mode_name: String, mode_index: int)

# Convenience signal for projects that want a focused-mode callback directly.
signal pinballctl_focus_changed(mode_name: String, mode_index: int)

# Generic event hook for pinballctl.
# The host runtime listens for this and forwards it into `/api/events/fire`.
signal pinballctl_custom_event(event_name: String, event_params: Dictionary)

@onready var carousel: Control = $Carousel

var focused_index := DEFAULT_FOCUSED_INDEX
var selected_index := -1
var last_reported_focus_index := -1

# We keep the orb nodes and their target transforms in parallel arrays because
# the animation is deliberately lightweight and easy to follow.
var orbs: Array[Control] = []
var orb_target_positions: Array[Vector2] = []
var orb_target_scales: Array[Vector2] = []


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_create_orbs()
	_update_orb_targets(true)
	_emit_focus_event(true)


func _process(delta: float) -> void:
	# Smooth movement keeps the sample visually pleasing without adding Tween
	# bookkeeping that would make the example harder to copy.
	var settle_speed := clampf(delta * SETTLE_SPEED, 0.0, 1.0)
	for i in orbs.size():
		var orb := orbs[i]
		orb.position = orb.position.lerp(orb_target_positions[i], settle_speed)
		orb.scale = orb.scale.lerp(orb_target_scales[i], settle_speed)


func _unhandled_input(event: InputEvent) -> void:
	# Standard Godot input path for standalone development.
	#
	# Keep authoring scenes against actions like `ui_left`, `ui_right`, and
	# `ui_accept`. pinballctl can inject those same actions later.
	if not event.is_pressed():
		return
	if event is InputEventKey and event.is_echo():
		return

	if event.is_action_pressed("ui_left"):
		focus_left()
		accept_event()
	elif event.is_action_pressed("ui_right"):
		focus_right()
		accept_event()
	elif event.is_action_pressed("ui_accept"):
		activate_focused()
		accept_event()


func _notification(what: int) -> void:
	# Recompute the layout when the viewport changes.
	if what == NOTIFICATION_RESIZED and not orbs.is_empty():
		_update_orb_targets(true)


func _create_orbs() -> void:
	# Build one reusable orb scene per mode label.
	for mode_name in MODE_NAMES:
		var orb: Control = ORB_SCENE.instantiate()
		orb.custom_minimum_size = Vector2.ONE * ORB_BASE_SIZE
		orb.size = orb.custom_minimum_size
		orb.call("set_label_text", mode_name)
		carousel.add_child(orb)
		orbs.append(orb)
		orb_target_positions.append(Vector2.ZERO)
		orb_target_scales.append(Vector2.ONE)


func focus_left() -> void:
	_move_focus(-1)


func focus_right() -> void:
	_move_focus(1)


func activate_focused() -> void:
	# This is the "button activated" state, separate from focus.
	selected_index = focused_index
	_update_orb_targets(false)
	mode_selected.emit(MODE_NAMES[focused_index], focused_index)


func pinballctl_input_action(action: String) -> void:
	# pinballctl calls this when it wants to inject Godot-style actions directly.
	match String(action).strip_edges():
		"ui_left":
			focus_left()
		"ui_right":
			focus_right()
		"ui_accept":
			activate_focused()


func pinballctl_input_key(key_name: String, phase: String = "tap") -> void:
	# Optional fallback for runtimes that inject keys instead of Godot actions.
	#
	# Ignore releases so a press/release pair does not move or activate twice.
	if String(phase).strip_edges().to_lower() == "release":
		return

	match String(key_name).strip_edges().to_lower():
		"left", "arrowleft", "leftarrow":
			focus_left()
		"right", "arrowright", "rightarrow":
			focus_right()
		"up", "arrowup", "uparrow", "enter", "return", "kp_enter":
			activate_focused()


func _move_focus(direction: int) -> void:
	var next_index := clampi(focused_index + direction, 0, MODE_NAMES.size() - 1)
	if next_index == focused_index:
		return

	focused_index = next_index
	selected_index = -1
	_update_orb_targets(false)
	_emit_focus_event()


func _update_orb_targets(snap: bool) -> void:
	# Recalculate where each orb should sit for the current focus index.
	var center := size * 0.5
	var spacing := minf(size.x * ORB_SPACING_RATIO, ORB_MAX_SPACING)

	for i in orbs.size():
		var distance := i - focused_index
		var abs_distance := absi(distance)
		var scale_value := clampf(ORB_MAX_SCALE - abs_distance * ORB_SCALE_STEP, ORB_MIN_SCALE, ORB_MAX_SCALE)
		var x_offset := float(distance) * spacing
		var y_offset := float(abs_distance) * ORB_Y_STEP
		var orb_size := Vector2.ONE * ORB_BASE_SIZE
		var target_scale := Vector2.ONE * scale_value
		var target_position := center + Vector2(x_offset, y_offset) - (orb_size * scale_value * 0.5)

		orb_target_positions[i] = target_position
		orb_target_scales[i] = target_scale

		var orb := orbs[i]
		orb.modulate.a = clampf(ORB_MAX_ALPHA - abs_distance * ORB_ALPHA_STEP, ORB_MIN_ALPHA, ORB_MAX_ALPHA)
		orb.z_index = 20 - abs_distance
		orb.call("set_visual_state", i == focused_index, i == selected_index)

		if snap:
			orb.position = target_position
			orb.scale = target_scale


func _emit_focus_event(force: bool = false) -> void:
	# Emit a custom pinballctl event when the highlighted button changes.
	#
	# This lets the author create Rules entries such as:
	# `BACKGLASS_MENU_FOCUS_CHANGED` -> emit another event / play sound / light lamp.
	if not force and last_reported_focus_index == focused_index:
		return

	last_reported_focus_index = focused_index
	var mode_name := MODE_NAMES[focused_index]
	var payload := {
		"modeName": mode_name,
		"modeIndex": focused_index,
		"selectedIndex": selected_index,
	}
	pinballctl_focus_changed.emit(mode_name, focused_index)
	pinballctl_custom_event.emit("BACKGLASS_MENU_FOCUS_CHANGED", payload)
