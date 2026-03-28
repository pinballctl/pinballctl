extends Control

const ORB_SCENE: PackedScene = preload("res://scenes/mode_orb.tscn")
const MODE_NAMES := [
	"CLASSIC",
	"MULTIBALL",
	"TIME ATTACK",
	"WIZARD",
	"PRACTICE",
	"CHALLENGE",
]

signal mode_selected(mode_name: String, mode_index: int)

@onready var carousel: Control = $Carousel

var focused_index := 2
var selected_index := -1
var orbs: Array[Control] = []
var orb_positions: Array[Vector2] = []
var orb_scales: Array[Vector2] = []


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_create_orbs()
	_refresh_targets(true)


func _process(delta: float) -> void:
	var settle_speed: float = clampf(delta * 9.0, 0.0, 1.0)

	for i in orbs.size():
		var orb: Control = orbs[i]
		orb.position = orb.position.lerp(orb_positions[i], settle_speed)
		orb.scale = orb.scale.lerp(orb_scales[i], settle_speed)


func _unhandled_input(event: InputEvent) -> void:
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
	if what == NOTIFICATION_RESIZED and not orbs.is_empty():
		_refresh_targets(true)


func _create_orbs() -> void:
	for mode_name in MODE_NAMES:
		var orb: Control = ORB_SCENE.instantiate()
		orb.custom_minimum_size = Vector2(220.0, 220.0)
		orb.size = orb.custom_minimum_size
		orb.call("set_label_text", mode_name)
		carousel.add_child(orb)
		orbs.append(orb)
		orb_positions.append(Vector2.ZERO)
		orb_scales.append(Vector2.ONE)


func _move_focus(direction: int) -> void:
	var next_index: int = clampi(focused_index + direction, 0, MODE_NAMES.size() - 1)
	if next_index == focused_index:
		return

	focused_index = next_index
	selected_index = -1
	_refresh_targets(false)


func _refresh_targets(snap: bool) -> void:
	var viewport_size: Vector2 = size
	var center: Vector2 = Vector2(viewport_size.x * 0.5, viewport_size.y * 0.5)
	var spacing: float = minf(viewport_size.x * 0.17, 280.0)
	var base_size: float = 220.0

	for i in orbs.size():
		var distance: int = i - focused_index
		var abs_distance: int = absi(distance)
		var scale_value: float = clampf(1.24 - abs_distance * 0.26, 0.22, 1.24)
		var y_offset: float = float(abs_distance) * 18.0
		var x_offset: float = float(distance) * spacing
		var orb_size: Vector2 = Vector2.ONE * base_size
		var target_scale: Vector2 = Vector2.ONE * scale_value
		var target_position: Vector2 = center + Vector2(x_offset, y_offset) - (orb_size * scale_value * 0.5)

		orb_positions[i] = target_position
		orb_scales[i] = target_scale

		var orb: Control = orbs[i]
		orb.modulate.a = clampf(0.92 - abs_distance * 0.14, 0.28, 0.92)
		orb.z_index = 20 - abs_distance
		orb.call("set_visual_state", i == focused_index, i == selected_index)

		if snap:
			orb.position = target_position
			orb.scale = target_scale


func focus_left() -> void:
	_move_focus(-1)


func focus_right() -> void:
	_move_focus(1)


func activate_focused() -> void:
	selected_index = focused_index
	_refresh_targets(false)
	mode_selected.emit(MODE_NAMES[focused_index], focused_index)


func pinballctl_input_action(action: String) -> void:
	match String(action).strip_edges():
		"ui_left":
			focus_left()
		"ui_right":
			focus_right()
		"ui_accept":
			activate_focused()
