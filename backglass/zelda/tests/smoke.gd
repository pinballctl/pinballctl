extends SceneTree

var failures := 0
var emitted: Array = []

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var scene = load("res://zelda/main.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	scene.set_process(false)
	scene.pinballctl_custom_event.connect(func(name_, params): emitted.append([name_, params]))
	check(scene.backgrounds.size() == 5, "All generated backgrounds load")
	check(scene.cues.size() == 6, "All generated audio cues load")
	for entry in scene.Catalog.SCREENS:
		check(scene.show_screen(entry[0]), "Catalog screen resolves: " + entry[0])
		await process_frame
	scene.show_screen("settings")
	var original_motion: bool = scene.reduced_motion
	scene.selection = 1
	scene.pinballctl_input_action("ui_accept")
	check(scene.reduced_motion != original_motion, "Reduced motion setting toggles")
	scene.show_screen("menu")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	var factor := minf(scene.size.x / 1920.0, scene.size.y / 1080.0)
	click.position = (scene.size - Vector2(1920, 1080) * factor) * 0.5 + Vector2(350, 365) * factor
	scene._gui_input(click)
	check(scene.screen_id == "quests", "Mouse selects main menu entry")
	scene.show_screen("attract")
	scene.pinballctl_input_key("space")
	check(scene.screen_id == "menu", "Start opens menu")
	scene.pinballctl_input_action("ui_accept")
	check(scene.screen_id == "quests", "Begin opens map")
	scene.pinballctl_input_action("ui_left")
	check(scene.quest == 6, "Flippers reach Back on quest map")
	scene.pinballctl_input_action("ui_accept")
	check(scene.screen_id == "menu", "Select returns from map")
	scene.show_screen("quests")
	scene.quest = 5
	scene.pinballctl_input_action("ui_accept")
	check(emitted.size() == 1 and emitted[0][0] == "BACKGLASS_START_REQUESTED", "Start request emitted")
	check(scene.screen_id == "quests", "Live start awaits controller")
	scene.pinballctl_state({"screen": "gameplay", "score": 1234, "ball": 2, "quest": 2})
	check(scene.screen_id == "gameplay" and scene.state.score == 1234 and scene.quest == 2, "Controller state applies")
	scene.pinballctl_state({"score": -1, "ball": 0, "quest": 999, "award": "bad"})
	check(scene.state.score == 0 and scene.state.ball == 1 and scene.quest == 5 and scene.state.award == 0, "Invalid values bounded")
	scene.pinballctl_state({"screen": "bonus", "event_id": "bonus-1", "bonus": 2500})
	scene.elapsed = 4
	scene.pinballctl_state({"screen": "bonus", "event_id": "bonus-1"})
	check(scene.elapsed == 4, "Duplicate event cannot restart animation")
	scene.pinballctl_state({"screen": "bonus", "event_id": "bonus-2"})
	check(scene.elapsed == 0, "New event replays animation")
	scene.pinballctl_input_action("ui_accept")
	check(scene.elapsed == 2.35 and scene.state.score == 0, "Bonus skip changes presentation only")
	scene.pinballctl_state({"screen": "tilt"})
	scene._process(30)
	check(scene.screen_id == "tilt", "Tilt persists until controller or navigation")
	scene.pinballctl_state({"screen": "gameplay", "score": 4321})
	var record_count: int = scene.records.size()
	scene.enter_preview()
	for i in scene.Catalog.SCREENS.size():
		scene.preview_index = i
		scene._play_preview()
		check(scene.preview and not scene.gallery, "Preview isolated")
		scene._process(1.0)
		await process_frame
	check(emitted.size() == 1, "Preview emits no machine events")
	scene.preview_index = 18
	scene._play_preview()
	for i in 3: scene.pinballctl_input_action("ui_accept")
	check(scene.screen_id == "records" and scene.records.size() == record_count, "Preview initials do not save demo record")
	scene.leave_preview()
	check(scene.screen_id == "gameplay" and scene.state.score == 4321, "Preview restores live state")
	scene.enter_preview()
	scene.pinballctl_state({"screen": "jackpot", "award": 10000})
	check(not scene.preview and scene.screen_id == "jackpot", "Controller event interrupts preview")
	scene.pinballctl_state({"screen": "game_over", "score": 98765})
	scene._process(11)
	check(scene.screen_id == "initials", "Qualifying game over enters initials")
	for i in 3: scene.pinballctl_input_action("ui_accept")
	check(scene.records.size() == record_count + 1, "Live initials create record")
	check(emitted[-1][0] == "BACKGLASS_INITIALS_SUBMITTED", "Initials emitted to controller")
	scene.pinballctl_text_values({"BACKGLASS_STATE": '{"score":700,"screen":"gameplay"}'})
	check(scene.state.score == 700 and scene.screen_id == "gameplay", "Text hook parses structured state")
	scene.pinballctl_text_values({"BACKGLASS_STATE": '{broken'})
	check(scene.state.score == 700, "Malformed state ignored")
	scene.enter_preview()
	scene._play_preview()
	scene.paused = true
	var old_elapsed: float = scene.elapsed
	scene._process(4)
	check(scene.elapsed == old_elapsed, "Pause freezes timeline")
	scene.paused = false
	scene.autoplay = true
	scene._process(30)
	check(scene.preview_index == 19, "Autoplay advances one scene")
	# Every quick event completes promptly without awarding points or emitting events.
	scene.leave_preview()
	for id in scene.QUICK + ["bonus"]:
		scene.show_screen(id)
		var duration: float = scene.Catalog.screen(id)[5]
		var score_before: int = scene.state.score
		check(duration <= 3.0, "Quick event duration: " + id)
		scene._process(duration + 0.01)
		check(scene.screen_id == "gameplay", "Quick event returns to game: " + id)
		check(scene.state.score == score_before, "Animation does not award score: " + id)
	scene.enter_preview()
	scene.preview_index = 0
	scene._play_preview()
	scene.autoplay = true
	scene._process(scene.Attract.DURATION + 0.1)
	check(scene.preview_index == 1, "Autoplay leaves attract rather than looping forever")
	scene.leave_preview()
	var total := 0.0
	for i in scene.Attract.SHOTS.size():
		check(scene.Attract.shot_at(total + 0.1).index == i, "Film shot boundary %d" % i)
		scene.show_screen("attract")
		scene.elapsed = total + 1
		scene.pinballctl_input_key("space")
		check(scene.screen_id == "menu", "Start interrupts film shot %d" % i)
		total += float(scene.Attract.SHOTS[i][1])
	check(total == scene.Attract.DURATION, "Film duration equals all edits")
	scene.show_screen("attract")
	scene._process(total + 0.2)
	check(scene.screen_id == "attract" and scene.elapsed < 1, "Film loops at end")
	scene.pinballctl_state({"screen":"gameplay"})
	check(scene.screen_id == "gameplay", "Controller interrupts attract film")
	print("Backglass smoke: %d failure(s)" % failures)
	scene.queue_free()
	await process_frame
	quit(1 if failures else 0)
