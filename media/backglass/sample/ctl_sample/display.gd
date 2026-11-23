extends Control

signal pinballctl_custom_event(event_name: String, event_params: Dictionary)
signal pinballctl_focus_changed(mode_name: String, mode_index: int)
signal pinballctl_scene_finished

const Art = preload("res://ctl_sample/art.gd")
const AttractLoop = preload("res://ctl_sample/attract_loop.gd")
const SCREENS := ["attract", "menu", "high_scores", "tilt", "bonus", "game_over", "mode"]
const DURATIONS := {"tilt": 1.20, "bonus": 2.12, "game_over": 2.75}
const MENU := ["Start game", "Mode", "High scores", "Return to attract"]
const MODES := ["Easy", "Hard"]
const BOARDS := {"all-time": "All time", "year": "This year", "month": "This month", "latest": "Latest"}
const NUMBER_FIELDS := ["score", "bonus", "multiplier", "player", "ball"]
const DEMO_SCORES := {
	"all-time": [{"initials": "ACE", "score": 8246000}, {"initials": "RAY", "score": 6910250},
		{"initials": "MAX", "score": 5284700}, {"initials": "DOT", "score": 4735000}, {"initials": "KIT", "score": 3660240}],
	"year": [{"initials": "ACE", "score": 8246000}, {"initials": "RAY", "score": 6910250}],
	"month": [{"initials": "DOT", "score": 4735000}, {"initials": "KIT", "score": 3660240}],
	"latest": [{"initials": "KIT", "score": 3660240}],
}
const MAX_SCORE := 999999999999

@export_enum("attract", "menu", "high_scores", "tilt", "bonus", "game_over", "mode") var initial_screen: String = "attract"
var screen := "attract"
var elapsed := 0.0
var focus_elapsed := 1.0
var focus_index := 0
var focus_direction := 0
var selected_mode := 0
var mode_focus := 0
var board_index := 0
var demo := false
var hosted := false
var complete := false
var start_requested := false
var refresh_after := 0.0
var state: Dictionary = {"score": 0, "bonus": 0, "multiplier": 1, "player": 1, "ball": 1, "player_name": ""}
var boards: Dictionary = {}
var competition := ""
var title_font := SystemFont.new()
var ui_font := SystemFont.new()
var mono_font := SystemFont.new()
var pending_tokens: Dictionary = {}
var art_transform := Transform2D.IDENTITY
var previous_tokens: Dictionary = {}
var previous_state: Variant = null
var previous_leaderboard: Variant = null
var last_event_id := ""

func _ready() -> void:
	title_font.font_names = PackedStringArray(["Arial Black", "DejaVu Sans", "Liberation Sans"])
	title_font.font_weight = 900
	ui_font.font_names = PackedStringArray(["Inter", "DejaVu Sans", "Arial"])
	ui_font.font_weight = 600
	mono_font.font_names = PackedStringArray(["DejaVu Sans Mono", "Menlo", "Liberation Mono"])
	demo = ProjectSettings.get_setting("application/config/name") == "Pinball CTL Backglass Sample"
	if demo:
		state.merge({"score": 1248500, "bonus": 126000, "multiplier": 3, "player": 1, "ball": 2}, true)
		boards = DEMO_SCORES
	show_screen(initial_screen)
	pinballctl_text_values(pending_tokens)
	pending_tokens = {}

func show_screen(next: String, menu_focus := 0) -> void:
	if next not in SCREENS:
		return
	screen = next
	elapsed = 0.0
	focus_elapsed = 1.0
	focus_direction = 0
	complete = false
	if screen == "menu":
		focus_index = clampi(menu_focus, 0, MENU.size() - 1)
		start_requested = false
	elif screen == "mode":
		mode_focus = selected_mode
	elif screen == "high_scores":
		board_index = 0
	refresh_after = 0.0
	queue_redraw()

func pinballctl_scene_session(active: bool) -> void:
	hosted = active

func _process(delta: float) -> void:
	if complete:
		return
	elapsed += delta
	if screen == "attract":
		elapsed = fposmod(elapsed, AttractLoop.DURATION)
	focus_elapsed += delta
	if screen == "high_scores" and not demo:
		refresh_after -= delta
		if refresh_after <= 0.0:
			refresh_after = 2.0
			pinballctl_custom_event.emit("BACKGLASS_HIGH_SCORES_REQUESTED", {})
	if DURATIONS.has(screen) and elapsed >= DURATIONS[screen]:
		complete = true
		pinballctl_scene_finished.emit()
		if not hosted:
			show_screen("attract")
	queue_redraw()

func _number_field(key: String, value: Variant) -> void:
	var number: float
	if value is int or value is float:
		number = float(value)
	elif value is String and value.strip_edges().is_valid_int():
		number = value.strip_edges().to_float()
	else:
		return
	if not is_finite(number):
		return
	var maximum := MAX_SCORE if key in ["score", "bonus"] else 99
	var minimum := 0 if key in ["score", "bonus"] else 1
	state[key] = int(clampf(number, minimum, maximum))

func _apply_mode(value: Variant) -> void:
	if not value is String:
		return
	var next := MODES.find(value.strip_edges().capitalize())
	if next < 0:
		return
	if screen == "mode" and mode_focus == selected_mode:
		mode_focus = next
	selected_mode = next

func pinballctl_text_values(values: Dictionary) -> void:
	if not is_node_ready():
		pending_tokens = values
		return
	var leaderboard: Variant = values.get("PINBALLCTL_HIGH_SCORES")
	if leaderboard is Dictionary and leaderboard != previous_leaderboard:
		previous_leaderboard = leaderboard
		var received_boards: Variant = leaderboard.get("boards")
		if received_boards is Dictionary:
			boards = received_boards
		var active: Variant = leaderboard.get("competition")
		var heading := str(active.get("title", "")).strip_edges() if active is Dictionary and active.get("active", false) == true else ""
		if heading != competition:
			competition = heading
			board_index = 0
		var game: Variant = leaderboard.get("game")
		if game is Dictionary and int(game.get("player", 0)) > 0:
			for field in ["score", "player", "ball"]:
				_number_field(field, game.get(field))
	var tokens := {}
	for key in values:
		tokens[str(key).to_lower()] = values[key]
	for field in NUMBER_FIELDS:
		if tokens.has(field) and previous_tokens.get(field) != tokens[field]:
			_number_field(field, tokens[field])
	if tokens.get("player_name") is String and previous_tokens.get("player_name") != tokens.player_name:
		state.player_name = tokens.player_name.strip_edges()
	if tokens.has("mode") and previous_tokens.get("mode") != tokens.mode:
		_apply_mode(tokens.mode)
	previous_tokens = tokens
	var raw: Variant = tokens.get("backglass_state")
	if raw != previous_state:
		previous_state = raw
		var update: Variant = JSON.parse_string(raw) if raw is String else raw
		if update is Dictionary:
			_apply_mode(update.get("mode"))
			for field in NUMBER_FIELDS:
				_number_field(field, update.get(field))
			if update.get("player_name") is String:
				state.player_name = update.player_name.strip_edges()
			var next := str(update.get("screen", ""))
			var event_id := str(update.get("event_id", ""))
			if next in SCREENS and ((event_id.is_empty() and next != screen) or (not event_id.is_empty() and event_id != last_event_id)):
				last_event_id = event_id
				show_screen(next)
	queue_redraw()

func board_keys() -> Array:
	var keys := BOARDS.keys()
	if not competition.is_empty():
		keys.push_front("competition")
	return keys

func pinballctl_input_action(action: String) -> void:
	match action:
		"ui_left", "ui_right":
			var direction := -1 if action == "ui_left" else 1
			if screen == "menu":
				focus_index = posmod(focus_index + direction, MENU.size())
				focus_elapsed = 0.0
				focus_direction = direction
				start_requested = false
				if not demo:
					pinballctl_focus_changed.emit(MENU[focus_index], focus_index)
			elif screen == "mode":
				mode_focus = posmod(mode_focus + direction, MODES.size())
				focus_elapsed = 0.0
			elif screen == "high_scores":
				board_index = posmod(board_index + direction, board_keys().size())
				focus_elapsed = 0.0
		"ui_accept":
			match screen:
				"attract": show_screen("menu")
				"high_scores": show_screen("menu")
				"mode":
					selected_mode = mode_focus
					if not demo:
						pinballctl_custom_event.emit("BACKGLASS_SAMPLE_MODE_%s_SELECTED" % MODES[selected_mode].to_upper(), {})
					show_screen("menu", MENU.find("Mode"))
				"menu":
					match MENU[focus_index]:
						"Start game":
							if not start_requested:
								start_requested = true
								if not demo: pinballctl_custom_event.emit("BACKGLASS_SAMPLE_START_REQUESTED", {})
						"Mode": show_screen("mode")
						"High scores": show_screen("high_scores")
						"Return to attract": show_screen("attract")
		"ui_cancel":
			if screen == "menu": show_screen("attract")
			elif screen == "mode": show_screen("menu", MENU.find("Mode"))
			elif screen == "high_scores": show_screen("menu")

func pinballctl_input_key(key_name: String, phase: String = "tap") -> void:
	if phase != "release":
		var action: String = {
			"left": "ui_left", "arrowleft": "ui_left", "right": "ui_right", "arrowright": "ui_right",
			"enter": "ui_accept", "return": "ui_accept", "kp_enter": "ui_accept", "space": "ui_accept", "escape": "ui_cancel",
		}.get(key_name.to_lower(), "")
		pinballctl_input_action(action)

func _unhandled_key_input(event: InputEvent) -> void:
	if not event.pressed or event.echo:
		return
	if demo and event.keycode >= KEY_F1 and event.keycode <= KEY_F1 + SCREENS.size() - 1:
		show_screen(SCREENS[event.keycode - KEY_F1])
		accept_event()
		return
	pinballctl_input_key(OS.get_keycode_string(event.keycode))

func _draw() -> void:
	Art.render(self)
