extends Control
## Presentation only: scores and awards always belong to the controller.
signal pinballctl_custom_event(event_name: String, event_params: Dictionary)
signal mode_selected(mode_name: String, mode_index: int)
const Attract = preload("res://zelda/attract.gd")
const Catalog = preload("res://zelda/catalog.gd")
const GOLD = Color("e2c786")
const CREAM = Color("f5edd6")
const MUTED = Color("9aafa5")
const INK = Color("071a18")
const SAVE_PATH = "user://hyrule_backglass_v1.json"
const QUICK = ["skill_success", "skill_missed", "jackpot", "super_jackpot", "ball_saved", "extra_ball", "quest_complete", "ball_lost", "tilt_warning"]
const MENU = ["Begin adventure", "The chronicles", "How to play", "Settings", "Preview theatre", "Return to attract"]
const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
@export var initial_screen := "attract"
@export var start_in_preview := false
var screen_id := "attract"
var elapsed := 0.0
var clock_time := 0.0
var selection := 0
var quest := 0
var preview := false
var gallery := false
var preview_index := 0
var autoplay := false
var paused := false
var reduced_motion := false
var volume := 0.6
var status_message := ""
var initials := [0, 0, 0]
var initial_cursor := 0
var initials_submitted := false
var records: Array = []
var state: Dictionary = {"score": 0, "player": 1, "ball": 1, "multiplier": 1, "rupees": 0, "bonus": 0, "award": 0, "progress": 0, "multiball": false, "quest": 0}
var saved_live_state: Dictionary = {}
var saved_live_screen := "attract"
var last_event_id := ""
var last_state_json := ""
var title_font: Font
var body_font: Font
var backgrounds: Dictionary = {}
var cue := AudioStreamPlayer.new()
var ambience := AudioStreamPlayer.new()
var cues: Dictionary = {}
var test_mode := false

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	test_mode = "--test" in OS.get_cmdline_user_args()
	body_font = ThemeDB.fallback_font
	var serif := SystemFont.new()
	serif.font_names = PackedStringArray(["Georgia", "Noto Serif", "DejaVu Serif"])
	title_font = serif
	for key in ["hyrule", "map", "temple", "dark", "sword"]:
		var path := "res://zelda/assets/%s.png" % key
		if ResourceLoader.exists(path):
			backgrounds[key] = load(path)
	for key in ["move", "confirm", "award", "dark", "ambient", "attract"]:
		var path := "res://zelda/assets/%s.wav" % key
		if ResourceLoader.exists(path):
			cues[key] = load(path)
	add_child(cue)
	add_child(ambience)
	ambience.finished.connect(_restart_ambience)
	if not test_mode:
		_load_preferences()
	show_screen(initial_screen)
	_restart_ambience()
	if start_in_preview or "--preview" in OS.get_cmdline_user_args():
		enter_preview()
	queue_redraw()

func _restart_ambience() -> void:
	if cues.has("ambient") and not test_mode:
		ambience.stream = cues.attract if screen_id == "attract" and not gallery and cues.has("attract") else cues.ambient
		ambience.volume_db = linear_to_db(maxf(0.0001, volume * (0.4 if screen_id == "attract" and not gallery else 0.18)))
		ambience.play()

func _process(delta: float) -> void:
	if not paused:
		clock_time += delta
		elapsed += delta
		var entry := Catalog.screen(screen_id)
		if not gallery and not entry.is_empty():
			var duration: float = entry[5]
			if screen_id == "attract" and elapsed >= Attract.DURATION and not (preview and autoplay):
				elapsed = fposmod(elapsed, Attract.DURATION)
				if not test_mode: ambience.seek(elapsed)
			elif preview and autoplay and elapsed >= (duration if duration > 0 else 7.0):
				preview_index = (preview_index + 1) % Catalog.SCREENS.size()
				_play_preview()
			elif not preview and duration > 0 and elapsed >= duration and screen_id != "attract":
				if screen_id == "game_over":
					var qualifies: bool = int(state.score) > 0 and (records.size() < 5 or int(state.score) > int(records[-1].score))
					show_screen("initials" if qualifies else "attract")
				else:
					show_screen("gameplay")
	queue_redraw()

func show_screen(id: String) -> bool:
	if Catalog.screen(id).is_empty() and id not in ["menu", "quests", "instructions", "settings"]:
		return false
	if id != "quests": quest = mini(quest, Catalog.QUESTS.size() - 1)
	var previous_screen := screen_id
	cue.stop()
	screen_id = id
	if id == "attract" or previous_screen == "attract": _restart_ambience()
	elapsed = 0.0
	selection = 0
	status_message = ""
	if id == "initials":
		initials = [0, 0, 0]
		initial_cursor = 0
		initials_submitted = false
	if id in ["jackpot", "super_jackpot", "quest_complete", "extra_ball", "victory"]:
		_sound("award")
	elif id in ["wizard", "tilt"]:
		_sound("dark")
	queue_redraw()
	return true

func enter_preview() -> void:
	if not preview:
		saved_live_state = state.duplicate(true)
		saved_live_screen = screen_id
	preview = true
	preview_index = mini(preview_index, Catalog.SCREENS.size() - 1)
	gallery = true
	_restart_ambience()
	paused = false
	cue.stream_paused = false
	ambience.stream_paused = false
	autoplay = false
	queue_redraw()

func leave_preview() -> void:
	preview = false
	gallery = false
	paused = false
	cue.stream_paused = false
	ambience.stream_paused = false
	autoplay = false
	state = saved_live_state.duplicate(true)
	quest = int(state.get("quest", 0))
	show_screen(saved_live_screen)

func _play_preview() -> void:
	preview_index = preview_index % Catalog.SCREENS.size()
	gallery = false
	paused = false
	cue.stream_paused = false
	ambience.stream_paused = false
	state = {"score": 1248500, "player": 1, "ball": 2, "multiplier": 3, "rupees": 42, "bonus": 126000, "award": 250000, "progress": 2, "multiball": false, "quest": quest}
	show_screen(Catalog.SCREENS[preview_index][0])
	state.multiball = screen_id in ["multiball", "jackpot", "super_jackpot"]

func _sound(key: String) -> void:
	if cues.has(key) and not test_mode:
		cue.stream = cues[key]
		cue.volume_db = linear_to_db(maxf(0.0001, volume))
		cue.play()

func _emit(name_: String, params: Dictionary = {}) -> void:
	if not preview:
		pinballctl_custom_event.emit(name_, params)

func pinballctl_text_values(values: Dictionary) -> void:
	# Host UPDATE_TEXT uses a JSON string so the existing string-based service works.
	var raw: Variant = values.get("BACKGLASS_STATE", values.get("backglass_state", ""))
	var json_text := str(raw)
	if json_text.is_empty() or json_text == last_state_json:
		return
	var parser := JSON.new()
	if not raw is Dictionary and parser.parse(json_text) != OK:
		return
	var parsed: Variant = raw if raw is Dictionary else parser.data
	if parsed is Dictionary:
		last_state_json = json_text
		pinballctl_state(parsed)

func pinballctl_state(update: Dictionary) -> void:
	if preview:
		leave_preview()
	for key in ["score", "rupees", "bonus", "award", "progress"]:
		if update.has(key) and (update[key] is int or update[key] is float):
			state[key] = clampi(int(update[key]), 0, 999999999999)
	for key in ["player", "ball", "multiplier"]:
		if update.has(key) and (update[key] is int or update[key] is float):
			state[key] = clampi(int(update[key]), 1, 99)
	if update.has("quest") and (update.quest is int or update.quest is float):
		quest = clampi(int(update.quest), 0, Catalog.QUESTS.size() - 1)
		state.quest = quest
	if update.has("multiball") and update.multiball is bool:
		state.multiball = update.multiball
	if update.has("screen"):
		var event_id := str(update.get("event_id", ""))
		if event_id.is_empty():
			if str(update.screen) != screen_id:
				show_screen(str(update.screen))
		elif event_id != last_event_id:
			if show_screen(str(update.screen)):
				last_event_id = event_id

func pinballctl_input_action(action: String) -> void:
	if action == "backglass_preview":
		if preview: leave_preview()
		else: enter_preview()
		return
	if action.begins_with("backglass_"):
		var requested := action.trim_prefix("backglass_")
		if not Catalog.screen(requested).is_empty():
			if preview: leave_preview()
			show_screen(requested)
		return
	if action == "ui_cancel":
		if preview:
			if gallery: leave_preview()
			else:
				gallery = true
				_restart_ambience()
				paused = false
				cue.stream_paused = false
				ambience.stream_paused = false
				autoplay = false
		else:
			show_screen("menu" if screen_id != "menu" else "attract")
		return
	if preview:
		if not gallery and screen_id == "initials" and action in ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"]:
			if action == "ui_accept": _accept()
			else: initials[initial_cursor] = posmod(initials[initial_cursor] + (1 if action in ["ui_down", "ui_right"] else -1), LETTERS.length())
			return
		if action in ["ui_left", "ui_right", "ui_up", "ui_down"]:
			var step := -1 if action in ["ui_left", "ui_up"] else 1
			preview_index = posmod(preview_index + step, Catalog.SCREENS.size() + (1 if gallery else 0))
			if not gallery: _play_preview()
			_sound("move")
		elif action == "ui_accept":
			if not gallery:
				pinballctl_input_action("ui_cancel")
			elif preview_index == Catalog.SCREENS.size():
				leave_preview()
				show_screen("menu")
			else:
				_play_preview()
		return
	if action in ["ui_left", "ui_right", "ui_up", "ui_down"]:
		var direction := -1 if action in ["ui_left", "ui_up"] else 1
		if screen_id == "quests":
			quest = posmod(quest + direction, Catalog.QUESTS.size() + 1)
		elif screen_id == "initials" and not initials_submitted:
			initials[initial_cursor] = posmod(initials[initial_cursor] + direction, LETTERS.length())
		elif screen_id == "settings":
			selection = posmod(selection + direction, 3)
		elif screen_id == "menu":
			selection = posmod(selection + direction, MENU.size())
		_sound("move")
	elif action == "ui_accept":
		_accept()

func _accept() -> void:
	_sound("confirm")
	match screen_id:
		"attract": show_screen("menu")
		"menu":
			match selection:
				0: show_screen("quests")
				1: show_screen("records")
				2: show_screen("instructions")
				3: show_screen("settings")
				4: enter_preview()
				5: show_screen("attract")
		"quests":
			if quest == Catalog.QUESTS.size():
				show_screen("menu")
				return
			state.quest = quest
			mode_selected.emit(Catalog.QUESTS[quest].name, quest)
			_emit("BACKGLASS_START_REQUESTED", {"quest": quest, "quest_name": Catalog.QUESTS[quest].name})
			status_message = "Adventure requested • waiting for the controller"
		"settings":
			if selection == 0:
				volume = fmod(snappedf(volume + 0.2, 0.2), 1.2)
				_restart_ambience()
			elif selection == 1:
				reduced_motion = not reduced_motion
			else:
				show_screen("menu")
			_save_preferences()
		"initials":
			if initials_submitted: return
			if initial_cursor < 2:
				initial_cursor += 1
			else:
				var name_ := ""
				for value in initials: name_ += LETTERS[value]
				initials_submitted = true
				if not preview:
					records.append({"name": name_, "score": state.score})
					records.sort_custom(func(a, b): return a.score > b.score)
					records = records.slice(0, 5)
					_save_preferences()
				_emit("BACKGLASS_INITIALS_SUBMITTED", {"initials": name_, "score": state.score})
				show_screen("records")
		"bonus": elapsed = maxf(elapsed, 2.35)
		"records", "instructions": show_screen("menu")

func pinballctl_input_key(key_name: String, phase: String = "tap") -> void:
	if phase == "release": return
	var key := key_name.to_lower()
	var actions := {"left": "ui_left", "right": "ui_right", "up": "ui_up", "down": "ui_down", "space": "ui_accept", "f1": "backglass_preview"}
	if actions.has(key):
		pinballctl_input_action(actions[key])
	elif preview:
		match key:
			"p":
				paused = not paused
				cue.stream_paused = paused
				ambience.stream_paused = paused
			"r": _play_preview()
			"a":
				autoplay = not autoplay
				if gallery: _play_preview()

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		pinballctl_input_key(OS.get_keycode_string(event.keycode))
		accept_event()

func _save_preferences() -> void:
	if test_mode or preview: return
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify({"version": 1, "volume": volume, "reduced_motion": reduced_motion, "records": records}))
	else:
		push_warning("Could not save backglass preferences: %s" % FileAccess.get_open_error())

func _load_preferences() -> void:
	if not FileAccess.file_exists(SAVE_PATH): return
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(SAVE_PATH)) != OK: return
	var parsed: Variant = parser.data
	if not parsed is Dictionary: return
	if parsed.get("volume") is float or parsed.get("volume") is int:
		volume = clampf(float(parsed.volume), 0.0, 1.0)
	reduced_motion = parsed.get("reduced_motion", false) == true
	if parsed.get("records") is Array:
		for row in parsed.records:
			if row is Dictionary and row.get("name") is String and (row.get("score") is int or row.get("score") is float):
				records.append({"name": row.name.left(3), "score": clampi(int(row.score), 0, 999999999999)})
		records.sort_custom(func(a, b): return a.score > b.score)
		records = records.slice(0, 5)

func _number(value: int) -> String:
	var source := str(value)
	var result := ""
	for i in source.length():
		if i > 0 and (source.length() - i) % 3 == 0: result += ","
		result += source[i]
	return result

func _text(text_: String, point: Vector2, font_size: int, color: Color = CREAM, centered: bool = false, serif: bool = false) -> void:
	var font := title_font if serif else body_font
	if font == null: return
	var width := font.get_string_size(text_, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	if centered: point.x -= width * 0.5
	draw_string(font, point + Vector2(0, 2), text_, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0, 0, 0, 0.6 * color.a))
	draw_string(font, point, text_, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)

func _panel(rect: Rect2, selected: bool = false) -> void:
	draw_style_box(_box(Color("163b32") if selected else Color(0.025, 0.08, 0.07, 0.9), GOLD if selected else Color("365348")), rect)

func _box(fill: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	return style

func _draw() -> void:
	if body_font == null: return
	# Letterbox rather than crop: every cabinet aspect retains controls and score.
	var factor := minf(size.x / 1920.0, size.y / 1080.0)
	draw_rect(Rect2(Vector2.ZERO, size), Color.BLACK)
	draw_set_transform((size - Vector2(1920, 1080) * factor) * 0.5, 0, Vector2.ONE * factor)
	if screen_id == "attract" and not gallery:
		Attract.render(self)
		_draw_controls()
		draw_set_transform(Vector2.ZERO)
		return
	var entry := Catalog.screen(screen_id)
	var bg := "map" if screen_id in ["menu", "quests"] else "temple"
	if not entry.is_empty(): bg = entry[4]
	if not entry.is_empty() and (screen_id in QUICK or screen_id == "bonus") and elapsed >= float(entry[5]): bg = "hyrule"
	if gallery: bg = "temple"
	if backgrounds.has(bg):
		var drift := 0.0 if reduced_motion else sin(clock_time * 0.08) * 12.0
		draw_texture_rect(backgrounds[bg], Rect2(-24 + drift, -18, 1968, 1116), false)
	else:
		draw_rect(Rect2(0, 0, 1920, 1080), INK)
	draw_rect(Rect2(0, 0, 1920, 1080), Color(0.015, 0.04, 0.035, 0.28))
	# Soft stepped vignettes preserve artwork and contrast behind text.
	for i in 12:
		var alpha := 0.038 * (12 - i) / 12.0
		draw_rect(Rect2(0, 0, 1920, 160 + i * 24), Color(0.01, 0.035, 0.025, alpha))
		draw_rect(Rect2(0, 740 - i * 16, 1920, 340 + i * 16), Color(0.01, 0.035, 0.025, alpha))
	_particles()
	if not gallery: _cinematic_fx()
	draw_rect(Rect2(32, 32, 1856, 1016), Color(GOLD, 0.35), false, 1.0)
	for x in [48, 1872]:
		for y in [48, 1032]:
			draw_circle(Vector2(x, y), 3, GOLD)
	_text("H Y R U L E   /   T H E   H E R O   O F   T I M E", Vector2(76, 88), 20, GOLD)
	_text("PREVIEW THEATRE" if preview else "PINBALL CHRONICLES", Vector2(1510, 88), 20, GOLD)
	if gallery:
		_draw_gallery()
	elif screen_id == "menu":
		_draw_menu()
	elif screen_id == "quests":
		_draw_quests()
	elif screen_id == "instructions":
		_draw_instructions()
	elif screen_id == "settings":
		_draw_settings()
	elif not entry.is_empty():
		_draw_screen(entry)
	_draw_controls()
	# Short fade-in has no callbacks, so interrupting a scene cannot resurrect it.
	if elapsed < 0.5 and not reduced_motion and not gallery and screen_id not in QUICK and screen_id != "bonus":
		draw_rect(Rect2(0, 116, 1920, 825), Color(0.01, 0.04, 0.03, (1.0 - elapsed / 0.5) * 0.8))
	draw_set_transform(Vector2.ZERO)

func _draw_controls() -> void:
	if preview and not gallery:
		_panel(Rect2(60, 960, 1800, 70))
		_text("%02d / %02d  •  %s" % [preview_index + 1, Catalog.SCREENS.size(), "PAUSED" if paused else ("AUTO PLAY" if autoplay else "PREVIEW")], Vector2(88, 1005), 23, GOLD)
		_text("FLIPPERS Scene    SELECT Gallery    R Replay    P Pause    A Auto", Vector2(640, 1005), 22)
	elif not gallery:
		var hint := "FLIPPERS / NAVIGATE     SELECT / CONFIRM"
		if screen_id == "quests" and not status_message.is_empty(): hint = status_message
		_text(hint, Vector2(960, 1008), 21, MUTED, true)

func _particles() -> void:
	for i in 36:
		var speed := 0.0 if reduced_motion else clock_time
		var x := fmod(i * 173.7 + sin(speed * 0.22 + i) * 26 + 1920, 1920)
		var y := fmod(i * 91.3 - speed * (7 + i % 5) + 10800, 1080)
		var tint := Color(GOLD, 0.15 + (sin(speed + i) + 1) * 0.16)
		draw_circle(Vector2(x, y), 6, Color(tint, 0.04))
		draw_circle(Vector2(x, y), 1.5 + i % 3, tint)

func _draw_menu() -> void:
	_text("YOUR ADVENTURE AWAITS", Vector2(960, 205), 58, CREAM, true, true)
	_text("Explore Hyrule. Awaken the sages. Become a legend.", Vector2(960, 260), 26, GOLD, true)
	for i in MENU.size():
		var rect := Rect2(160, 330 + i * 88, 640, 74)
		_panel(rect, selection == i)
		_text("%02d" % (i + 1), rect.position + Vector2(28, 47), 22, GOLD)
		_text(MENU[i], rect.position + Vector2(90, 49), 30)
	_motif("triforce", Vector2(1280, 510), 1.4)
	_text("POWER  •  WISDOM  •  COURAGE", Vector2(1280, 730), 23, GOLD, true)
	_text("Six destinations. One timeless journey.", Vector2(1280, 780), 25, CREAM, true)

func _draw_quests() -> void:
	_text("CHOOSE YOUR DESTINATION", Vector2(960, 205), 54, CREAM, true, true)
	for i in Catalog.QUESTS.size():
		var item: Dictionary = Catalog.QUESTS[i]
		var point: Vector2 = item.point
		var radius := 24.0 if i == quest else 13.0
		draw_circle(point, radius + 12, Color(INK, 0.85))
		draw_circle(point, radius, Color(item.color))
		if i == quest:
			draw_arc(point, 40 + (0 if reduced_motion else sin(clock_time * 2) * 3), 0, TAU, 64, GOLD, 2, true)
		_text(item.name, point + Vector2(0, 65), 25, CREAM, true)
	_panel(Rect2(230, 810, 1460, 130))
	if quest == Catalog.QUESTS.size():
		_text("BACK TO MENU", Vector2(960, 885), 32, GOLD, true)
		return
	_text(Catalog.QUESTS[quest].name.to_upper(), Vector2(270, 862), 34, GOLD, false, true)
	_text(Catalog.QUESTS[quest].goal, Vector2(270, 909), 26)
	_text("SELECT / BEGIN", Vector2(1400, 885), 23, GOLD)

func _draw_gallery() -> void:
	_text("PREVIEW THEATRE", Vector2(960, 185), 52, CREAM, true, true)
	_text("Every chapter of the adventure. No cabinet required.", Vector2(960, 233), 25, GOLD, true)
	for i in Catalog.SCREENS.size():
		var col := i / 10
		var row := i % 10
		var rect := Rect2(140 + col * 840, 275 + row * 62, 800, 52)
		_panel(rect, i == preview_index)
		_text("%02d" % (i + 1), rect.position + Vector2(20, 35), 20, GOLD)
		_text(str(Catalog.SCREENS[i][0]).replace("_", " ").to_upper(), rect.position + Vector2(80, 35), 22)
	_panel(Rect2(620, 900, 680, 44), preview_index == Catalog.SCREENS.size())
	_text("BACK TO MENU", Vector2(960, 931), 22, GOLD, true)
	_text("FLIPPERS Navigate     SELECT Play / Back     A Play all", Vector2(960, 972), 24, GOLD, true)
	_text("Preview never sends game events or saves demonstration scores.", Vector2(960, 1015), 20, MUTED, true)

func _draw_instructions() -> void:
	_text("THE PATH OF THE HERO", Vector2(960, 215), 58, CREAM, true, true)
	var rows := [
		["01", "Choose your quest", "Use the flippers to explore the map. Press Select to request an adventure."],
		["02", "Follow the light", "Read the current objective on your backglass. Your rules define the shots."],
		["03", "Gather the sacred stones", "Complete quests, build bonus multipliers and light the multiball awards."],
		["04", "Awaken the Triforce", "Keep the balls alive and collect jackpots when your game lights them."],
		["05", "Become a legend", "Face the final battle and enter your initials in the chronicles."],
	]
	for i in rows.size():
		var y := 310.0 + i * 120
		_panel(Rect2(200, y, 1520, 100))
		_text(rows[i][0], Vector2(240, y + 57), 30, GOLD)
		_text(rows[i][1], Vector2(330, y + 39), 30, GOLD, false, true)
		_text(rows[i][2], Vector2(330, y + 77), 24)

func _draw_settings() -> void:
	_text("TUNE YOUR ADVENTURE", Vector2(960, 240), 58, CREAM, true, true)
	var rows := ["Sound volume     %d%%" % roundi(volume * 100), "Reduced motion     %s" % ("ON" if reduced_motion else "OFF"), "Save & return"]
	for i in rows.size():
		_panel(Rect2(460, 360 + i * 135, 1000, 105), selection == i)
		_text(rows[i], Vector2(960, 427 + i * 135), 36, CREAM, true)
	_text("Select with flippers. Press Start to change. Saved on this display.", Vector2(960, 860), 25, GOLD, true)

func _draw_screen(entry: Array) -> void:
	if screen_id in QUICK or screen_id == "bonus":
		if elapsed >= float(entry[5]):
			_draw_gameplay()
			_text("SEQUENCE FINISHED • R TO REPLAY", Vector2(960, 180), 22, GOLD, true)
		elif screen_id == "bonus":
			_draw_bonus()
		else:
			_draw_quick(entry)
		return
	if screen_id == "gameplay":
		_draw_gameplay()
		return
	if screen_id == "records":
		_draw_records()
		return
	var title: String = entry[1]
	var subtitle: String = entry[3]
	_text(entry[2], Vector2(960, 235), 25, GOLD, true)
	_text(title, Vector2(960, 335), 68 if title.length() < 24 else 58, CREAM, true, true)
	draw_line(Vector2(780, 373), Vector2(1140, 373), Color(GOLD, 0.65), 1)
	var reveal := 1.0 if reduced_motion else clampf(elapsed / 1.7, 0.0, 1.0)
	_motif(entry[6], Vector2(960, 540), 1.15 * (0.8 + reveal * 0.2))
	if screen_id == "bonus":
		_draw_bonus()
	elif screen_id == "initials":
		for i in 3:
			_panel(Rect2(720 + i * 170, 710, 140, 125), i == initial_cursor)
			_text(LETTERS[initials[i]], Vector2(790 + i * 170, 795), 64, GOLD, true, true)
		_text("FLIPPERS Choose letter" + "     SELECT Confirm letter     Score: " + _number(state.score), Vector2(960, 901), 26, CREAM, true)
	elif screen_id == "game_over":
		_text(_number(state.score), Vector2(960, 785), 82, GOLD, true)
		_text("FINAL SCORE  /  PLAYER %d" % state.player, Vector2(960, 838), 24, CREAM, true)
	elif screen_id in ["jackpot", "super_jackpot", "skill_success"]:
		_text(_number(state.award), Vector2(960, 810), 92, GOLD, true)
	elif screen_id == "attract":
		_panel(Rect2(650, 760, 620, 88))
		_text("PRESS START TO BEGIN", Vector2(960, 816), 30, GOLD, true)
	else:
		_text(subtitle, Vector2(960, 810), 30, CREAM, true)
	if screen_id not in ["bonus", "initials"]:
		_text(subtitle if screen_id in ["attract", "game_over", "jackpot", "super_jackpot", "skill_success"] else "THE LEGEND OF ZELDA  /  PINBALL", Vector2(960, 905), 24, MUTED, true)

func _draw_gameplay() -> void:
	_text("PLAYER %d" % state.player, Vector2(960, 205), 25, GOLD, true)
	_text(_number(state.score), Vector2(960, 350), 120, CREAM, true)
	_text("BALL %d     /     BONUS ×%d     /     %d RUPEES" % [state.ball, state.multiplier, state.rupees], Vector2(960, 414), 27, GOLD, true)
	_motif("triforce" if state.multiball else "medallion", Vector2(960, 585), 0.85)
	_panel(Rect2(240, 760, 1440, 170))
	_text("TRIFORCE MULTIBALL" if state.multiball else Catalog.QUESTS[quest].name.to_upper(), Vector2(960, 812), 36, GOLD, true, true)
	_text("Shoot the lit jackpots" if state.multiball else Catalog.QUESTS[quest].goal, Vector2(960, 857), 26, CREAM, true)
	for i in 3:
		draw_circle(Vector2(910 + i * 50, 897), 8, GOLD if i < int(state.progress) else Color("3d5b4a"))

# All transforms are derived from elapsed time, so pause/replay/interruption are deterministic.
func _stage(pivot := Vector2.ZERO, angle := 0.0, zoom := 1.0) -> void:
	var factor := minf(size.x / 1920.0, size.y / 1080.0)
	var origin := (size - Vector2(1920, 1080) * factor) * 0.5
	draw_set_transform(origin + pivot * factor, angle, Vector2.ONE * factor * zoom)

func _ease_out(value: float) -> float:
	return 1.0 - pow(1.0 - clampf(value, 0, 1), 3)

func _draw_bonus() -> void:
	var enter := 1.0 if reduced_motion else _ease_out(elapsed / 0.48)
	var leave := 0.0 if reduced_motion else pow(clampf((elapsed - 2.65) / 0.35, 0, 1), 2)
	var tally := clampf((elapsed - 0.45) / 1.65, 0, 1)
	# A whole bonus plate spins into place, settles, counts rapidly, then whips out.
	_stage(Vector2(960 + leave * 1800, 530), (1.0 - enter) * -TAU + leave * 0.5, 0.12 + enter * 0.88)
	_panel(Rect2(-750, -290, 1500, 600))
	for i in 24:
		var angle := i * TAU / 24 + (0.0 if reduced_motion else elapsed * 2.8)
		draw_line(Vector2(cos(angle), sin(angle)) * 240, Vector2(cos(angle), sin(angle)) * 285, Color(GOLD, 0.3), 3)
	_text("BONUS", Vector2(0, -155), 112, GOLD, true, true)
	_text("TREASURES OF HYRULE", Vector2(0, -235), 24, CREAM, true)
	var kick := 1.0 if reduced_motion else 1.0 + sin(clampf((elapsed - 2.1) / 0.25, 0, 1) * PI) * 0.12
	_text(_number(roundi(int(state.bonus) * tally)), Vector2(0, 65), roundi(115 * kick), CREAM, true)
	_text("%d RUPEES     ×%d MULTIPLIER" % [state.rupees, state.multiplier], Vector2(0, 155), 32, GOLD, true)
	draw_rect(Rect2(-580, 205, 1160, 10), Color("284d40"))
	draw_rect(Rect2(-580, 205, 1160 * tally, 10), GOLD)
	_text("COLLECTED!" if tally >= 1 else "COUNT IT UP", Vector2(0, 260), 22, MUTED, true)
	_stage()
	if not reduced_motion:
		for i in 18:
			var t := fmod(elapsed * 1.8 + i * 0.17, 1.0)
			var angle := i * TAU / 18 + elapsed
			var point := Vector2(960, 530) + Vector2(cos(angle) * 950, sin(angle) * 430) * (1.0 - t)
			var gem := PackedVector2Array([point + Vector2(0,-18), point + Vector2(10,0), point + Vector2(0,18), point + Vector2(-10,0)])
			draw_colored_polygon(gem, Color(0.4, 0.9, 0.7, 1.0 - t))

func _draw_quick(entry: Array) -> void:
	var duration: float = entry[5]
	var enter := 1.0 if reduced_motion else _ease_out(elapsed / 0.18)
	var leave := 0.0 if reduced_motion else pow(clampf((elapsed - duration + 0.22) / 0.22, 0, 1), 2)
	var accent := GOLD
	var heading: String = entry[2]
	var detail: String = entry[3]
	var origin := Vector2(960, 520)
	var angle := 0.0
	var zoom := 1.0
	match screen_id:
		"jackpot", "super_jackpot":
			heading = entry[1]
			detail = _number(state.award)
			zoom = 0.4 + enter * 0.6 + leave * 1.2
			accent = Color("ffe39b")
		"skill_success", "skill_missed":
			heading = "BULLSEYE!" if screen_id == "skill_success" else "NEXT TIME!"
			detail = _number(state.award) if screen_id == "skill_success" else "KEEP THE QUEST ALIVE"
			origin.x += (1.0 - enter) * 1500 - leave * 1700
			accent = Color("82e3c3")
		"ball_saved":
			heading = "BALL SAVED"
			detail = "BACK INTO THE ADVENTURE"
			origin.y += (1.0 - enter) * 650 - leave * 650
			accent = Color("a0ebf4")
		"extra_ball":
			heading = "EXTRA BALL"
			detail = "ONE MORE ADVENTURE"
			zoom = enter * (1.0 - leave)
			if not reduced_motion: zoom += sin(clampf(elapsed / 0.4, 0, 1) * PI) * 0.18
			accent = Color("f3a1ad")
		"quest_complete":
			heading = "QUEST COMPLETE"
			detail = Catalog.QUESTS[quest].name.to_upper()
			angle = (1.0 - enter) * -0.35 + leave * 0.35
			origin.x += leave * 1900
		"ball_lost":
			heading = "BALL LOST"
			detail = "YOUR JOURNEY CONTINUES"
			origin.y -= (1.0 - enter) * 650 - leave * 750
			accent = Color("8fa6bb")
		"tilt_warning":
			heading = "STEADY, HERO!"
			detail = "TILT WARNING"
			accent = Color("f4ad6b")
			if not reduced_motion: origin.x += sin(elapsed * 45) * 30 * (1.0 - enter)
	# One brief impact wash, not repeated strobing; disabled by reduced motion.
	if not reduced_motion:
		draw_rect(Rect2(34, 116, 1852, 824), Color(accent, maxf(0, 1.0 - elapsed / 0.16) * 0.32))
	_stage(origin, angle, maxf(0.01, zoom))
	draw_colored_polygon(PackedVector2Array([Vector2(-920,-240), Vector2(920,-290), Vector2(920,260), Vector2(-920,310)]), Color(INK, 0.95))
	draw_line(Vector2(-920,-240), Vector2(920,-290), accent, 6)
	draw_line(Vector2(-920,310), Vector2(920,260), accent, 6)
	var size_ := 126 if heading.length() < 14 else 96
	_text(heading, Vector2(0,-25), size_, accent, true, true)
	_text(detail, Vector2(0,115), 100 if screen_id in ["jackpot", "super_jackpot", "skill_success"] else 36, CREAM, true)
	# Distinct graphic accents accompany the different movement signatures.
	if screen_id in ["skill_success", "skill_missed"]:
		for i in 3: draw_arc(Vector2(-755,50), 35 + i * 22, 0, TAU, 48, accent, 3, true)
	elif screen_id == "ball_saved":
		for i in 16:
			var t := 0.6 if reduced_motion else elapsed - i * 0.018
			var point := Vector2(-760 + fmod(t * 1400 + 1900, 1520), -170 + sin(t * 9) * 30)
			draw_circle(point, 10 - i * 0.4, Color(accent, (16 - i) / 16.0))
	elif screen_id == "extra_ball":
		_text("+1", Vector2(0,-165), 80, accent, true)
	elif screen_id == "quest_complete":
		draw_arc(Vector2(-760,40), 75, 0, TAU * enter, 64, accent, 9, true)
		draw_polyline(PackedVector2Array([Vector2(-800,40),Vector2(-770,70),Vector2(-715,-5)]), CREAM, 9, true)
	elif screen_id in ["jackpot", "super_jackpot"]:
		for i in 12:
			var t := 0.5 if reduced_motion else clampf(elapsed / 0.65, 0, 1)
			var a := i * TAU / 12
			var start := Vector2(cos(a) * 650, sin(a) * 200)
			draw_line(start, start + Vector2(cos(a), sin(a)) * 150 * t, accent, 4)
	elif screen_id == "tilt_warning":
		_text("!", Vector2(-770,90), 170, accent, true)
	_stage()

func _draw_records() -> void:
	_text("HEROES OF HYRULE", Vector2(960, 220), 24, GOLD, true)
	_text("THE CHRONICLES", Vector2(960, 315), 70, CREAM, true, true)
	var display_records := records
	if preview:
		display_records = [{"name": "LNK", "score": 9248500}, {"name": "ZEL", "score": 7812000}, {"name": "NAV", "score": 6240000}]
	if display_records.is_empty():
		_motif("medallion", Vector2(960, 540), 1.1)
		_text("The first legend is yet to be written.", Vector2(960, 800), 32, CREAM, true)
	else:
		for i in display_records.size():
			var row: Dictionary = display_records[i]
			_panel(Rect2(430, 400 + i * 95, 1060, 77), i == 0)
			_text("%02d" % (i + 1), Vector2(470, 452 + i * 95), 26, GOLD)
			_text(row.name, Vector2(600, 452 + i * 95), 34, CREAM, false, true)
			_text(_number(row.score), Vector2(1160, 452 + i * 95), 34, GOLD, true)

func _motif(kind: String, center: Vector2, scale_: float) -> void:
	var phase := 0.0 if reduced_motion else clock_time
	var breath := 1.0 + sin(phase * 1.4) * 0.025
	var radius := 125.0 * scale_ * breath
	for i in 5:
		draw_circle(center, radius * (1.15 + i * 0.17), Color(GOLD, 0.012))
	draw_arc(center, radius * 1.38, 0, TAU, 100, Color(GOLD, 0.28), 1.2, true)
	draw_arc(center, radius * 1.48, phase * 0.12, phase * 0.12 + PI * 1.3, 80, Color(GOLD, 0.6), 1, true)
	for i in 12:
		var angle := i * TAU / 12
		var a := center + Vector2(cos(angle), sin(angle)) * radius * 1.35
		var b := center + Vector2(cos(angle), sin(angle)) * radius * 1.42
		draw_line(a, b, GOLD, 2)
	match kind:
		"triforce":
			var separation := 0.0 if reduced_motion else (1.0 - clampf(elapsed / 2.0, 0, 1)) * 90
			for offset in [Vector2(0, -0.52), Vector2(-0.53, 0.40), Vector2(0.53, 0.40)]:
				var c: Vector2 = center + offset * (radius + separation)
				var points := PackedVector2Array([c + Vector2(0, -radius * 0.61), c + Vector2(radius * 0.53, radius * 0.31), c + Vector2(-radius * 0.53, radius * 0.31)])
				draw_colored_polygon(points, GOLD)
				draw_polyline(PackedVector2Array([points[0], points[1], points[2], points[0]]), CREAM, 2, true)
		"rupee":
			var points := PackedVector2Array([center + Vector2(0, -radius), center + Vector2(radius * 0.55, -radius * 0.5), center + Vector2(radius * 0.55, radius * 0.5), center + Vector2(0, radius), center + Vector2(-radius * 0.55, radius * 0.5), center + Vector2(-radius * 0.55, -radius * 0.5)])
			draw_colored_polygon(points, Color("67cbb0"))
			for point in points: draw_line(center, point, Color("baf1d7"), 2, true)
		"heart":
			var points := PackedVector2Array()
			for i in 80:
				var t := TAU * i / 80
				points.append(center + Vector2(16 * pow(sin(t), 3), -(13 * cos(t) - 5 * cos(2 * t) - 2 * cos(3 * t) - cos(4 * t))) * radius / 18)
			draw_colored_polygon(points, Color("df8c90"))
		"fairy":
			for offset in [Vector2(-0.65, -0.45), Vector2(0.65, -0.45), Vector2(-0.5, 0.35), Vector2(0.5, 0.35)]:
				_fairy_wing(center + offset * radius, radius * 0.44)
			draw_circle(center, radius * 0.42, Color("b4edec"))
			draw_circle(center, radius * 0.26, Color("edffff"))
		"target":
			for i in 3: draw_arc(center, radius * (0.35 + i * 0.3), 0, TAU, 64, GOLD, 3, true)
			var x := sin(phase * 2) * radius * 0.6
			draw_line(center + Vector2(x, -radius), center + Vector2(x, radius), CREAM, 2)
			draw_line(center + Vector2(-radius, 0), center + Vector2(radius, 0), CREAM, 2)
		_:
			draw_circle(center, radius * 0.78, Color("254f40"))
			draw_arc(center, radius * 0.8, 0, TAU, 64, GOLD, 3, true)
			for i in 6:
				var angle := i * TAU / 6 - PI / 2
				var point := center + Vector2(cos(angle), sin(angle)) * radius * 0.6
				draw_line(center, point, GOLD, 3, true)
				draw_circle(point, 7, GOLD)

func _fairy_wing(point: Vector2, radius: float) -> void:
	draw_circle(point, radius, Color(0.7, 0.95, 1.0, 0.3))


func _cinematic_fx() -> void:
	if reduced_motion or screen_id in QUICK or screen_id == "bonus": return
	var t := elapsed
	if screen_id in ["multiball", "super_jackpot", "victory"]:
		var power := clampf((t - 1.0) / 3.0, 0.0, 1.0)
		for i in 24:
			var angle := i * TAU / 24 + t * 0.025
			var a := Vector2(960, 540) + Vector2(cos(angle), sin(angle)) * 180
			var b := Vector2(960, 540) + Vector2(cos(angle + 0.018), sin(angle + 0.018)) * 1100
			var c := Vector2(960, 540) + Vector2(cos(angle - 0.018), sin(angle - 0.018)) * 1100
			draw_colored_polygon(PackedVector2Array([a, b, c]), Color(GOLD, power * 0.065))
		if screen_id == "multiball":
			for i in 3:
				var angle := t * 1.2 + i * TAU / 3
				var point := Vector2(960, 540) + Vector2(cos(angle) * 350, sin(angle) * 170)
				draw_circle(point, 24, Color(GOLD, 0.10))
				draw_circle(point, 12, GOLD)
	elif screen_id in ["bonus", "jackpot"]:
		for i in 12:
			var point := Vector2(300 + i * 120, fmod(t * 90 + i * 75, 650) + 240)
			var points := PackedVector2Array([point + Vector2(0, -13), point + Vector2(7, 0), point + Vector2(0, 13), point + Vector2(-7, 0)])
			draw_colored_polygon(points, Color(0.5, 0.9, 0.7, 0.4))
	elif screen_id == "ball_saved":
		for i in 16:
			var phase := t * 1.4 - i * 0.055
			var point := Vector2(960 + cos(phase) * 320, 535 + sin(phase * 2) * 130)
			draw_circle(point, 7 - i * 0.3, Color(0.7, 1.0, 1.0, (16 - i) / 20.0))
	elif screen_id in ["wizard", "tilt", "tilt_warning"]:
		var alpha := (sin(t * 1.1) + 1) * 0.035
		draw_rect(Rect2(0, 0, 1920, 1080), Color(0.35, 0.08, 0.3, alpha))
	elif screen_id == "game_over":
		var bar := clampf(t / 3, 0, 1) * 20
		draw_rect(Rect2(33, 115, 1854, bar), Color(INK, 0.6))
		draw_rect(Rect2(33, 945 - bar, 1854, bar), Color(INK, 0.6))


func _gui_input(event: InputEvent) -> void:
	if not event is InputEventMouseButton or not event.pressed or event.button_index != MOUSE_BUTTON_LEFT:
		return
	var factor := minf(size.x / 1920.0, size.y / 1080.0)
	if factor <= 0: return
	var point: Vector2 = (event.position - (size - Vector2(1920, 1080) * factor) * 0.5) / factor
	if gallery:
		if Rect2(620, 900, 680, 44).has_point(point):
			leave_preview()
			show_screen("menu")
			return
		for i in Catalog.SCREENS.size():
			if Rect2(140 + (i / 10) * 840, 275 + (i % 10) * 62, 800, 52).has_point(point):
				preview_index = i
				_play_preview()
				return
	elif not preview:
		if screen_id == "menu":
			for i in MENU.size():
				if Rect2(160, 330 + i * 88, 640, 74).has_point(point):
					selection = i
					_accept()
					return
		elif screen_id == "settings":
			for i in 3:
				if Rect2(460, 360 + i * 135, 1000, 105).has_point(point):
					selection = i
					_accept()
					return
		elif screen_id == "quests":
			for i in Catalog.QUESTS.size():
				if point.distance_to(Catalog.QUESTS[i].point) < 65:
					quest = i
					_sound("move")
					return
			if Rect2(230, 810, 1460, 130).has_point(point): _accept()
		elif screen_id == "attract" and Rect2(400, 910, 1120, 50).has_point(point):
			_accept()
