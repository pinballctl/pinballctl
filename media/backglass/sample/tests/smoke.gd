extends SceneTree

var failures := 0

func _initialize() -> void:
	run.call_deferred()

func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)

func run() -> void:
	var view = load("res://ctl_sample/entries/attract.tscn").instantiate()
	root.add_child(view)
	view.set_process(false)
	var events: Array = []
	view.pinballctl_custom_event.connect(func(event, params): events.append([event, params]))
	view.demo = false
	var replay = view.AttractLoop
	check(replay.phase(0.0) == "opening" and replay.phase(7.0) == "build", "Attract opens and builds the table")
	check(replay.phase(20.0) == "play" and replay.phase(36.0) == "outro", "Attract plays and closes the replay")
	check(replay.part_index(8.0) == replay.PART_NAMES.size() - 1, "Ball arrives after the table parts")
	check(replay.replay(replay.replay_time(25.0)).ball == 2
		and replay.replay(replay.replay_time(36.0)).score > replay.replay(replay.replay_time(25.0)).score,
		"Attract launches three balls and keeps a separate cumulative score")
	var target: Dictionary = replay.replay(2.42)
	check(target.targets_down == [true, false, false] and target.points == 3000 and target.impact > 0.0
		and target.reaction == "proud",
		"The first target drops and awards points on contact")
	var following_hit: Dictionary = replay.replay(2.69)
	check(following_hit.points == 2500 and following_hit.reaction == target.reaction
		and following_hit.reaction_weight < target.reaction_weight,
		"An unmarked hit does not restart or replace Relay's gesture")
	var authored_poses := {}
	for route in replay.PLAYS:
		for step in route:
			if step.size() > 5:
				var pose: String = step[5]
				check(not authored_poses.has(pose), "Relay's action plays once: " + pose)
				authored_poses[pose] = true
	check(replay.replay(replay.BALL_LENGTH + 0.30).plunger > 0.0
		and replay.replay(replay.BALL_LENGTH + 0.30).targets_down == [false, false, false],
		"The plunger pulls and the target bank resets for the next ball")
	var live_score: int = view.state.score
	view._process(21.0)
	check(view.state.score == live_score and events.is_empty(), "Attract does not write game state or emit events")
	view._process(replay.DURATION - 21.0 + 0.25)
	check(is_equal_approx(view.elapsed, 0.25), "Attract loops at 38 seconds")
	view._process(24.0)
	view.pinballctl_input_action("ui_accept")
	check(view.screen == "menu" and view.focus_index == 0, "Start opens cabinet menu")
	view.pinballctl_input_key("left", "release")
	check(view.focus_index == 0, "A release does not move the menu")
	view.pinballctl_input_key("left")
	check(view.focus_index == view.MENU.size() - 1, "Flipper wraps menu to its last choice")
	view.pinballctl_input_action("ui_right")
	view.pinballctl_input_action("ui_accept")
	view.pinballctl_input_action("ui_accept")
	check(events == [["BACKGLASS_SAMPLE_START_REQUESTED", {}]], "Start requests a game once")
	view.pinballctl_input_action("ui_right")
	view.pinballctl_input_action("ui_accept")
	check(view.screen == "mode" and view.mode_focus == 0, "The Mode menu opens with Easy selected")
	view.pinballctl_input_action("ui_left")
	check(view.mode_focus == 1 and events.size() == 1, "Flippers wrap the mode selector without emitting a choice")
	view.pinballctl_input_action("ui_accept")
	check(view.screen == "menu" and view.selected_mode == 1, "Start confirms Hard and returns to the menu")
	check(events[-1] == ["BACKGLASS_SAMPLE_MODE_HARD_SELECTED", {}], "Rules receive the Hard selection")
	view.pinballctl_input_action("ui_accept")
	check(view.mode_focus == 1, "Reopening Mode highlights the saved choice")
	view.pinballctl_input_action("ui_right")
	view.pinballctl_input_action("ui_cancel")
	check(view.screen == "menu" and view.selected_mode == 1 and events.size() == 2, "Back discards a tentative choice")
	view.pinballctl_text_values({"MODE": "unknown"})
	check(view.selected_mode == 1, "Invalid mode tokens leave the selection alone")
	view.pinballctl_text_values({"BACKGLASS_STATE": '{"mode":"easy"}'})
	check(view.selected_mode == 0, "Controller state restores a valid mode")
	view.pinballctl_input_action("ui_accept")
	view.pinballctl_input_action("ui_accept")
	check(events[-1] == ["BACKGLASS_SAMPLE_MODE_EASY_SELECTED", {}], "Rules receive the Easy selection")
	view.pinballctl_input_action("ui_right")
	view.pinballctl_input_action("ui_accept")
	check(view.screen == "high_scores", "Flipper and Start open high scores")
	view._process(0.1)
	check(events[-1][0] == "BACKGLASS_HIGH_SCORES_REQUESTED", "High scores refresh from host")
	view.pinballctl_text_values({"PINBALLCTL_HIGH_SCORES": {
		"boards": {"competition": [{"score": 7100, "initials": "TST"}]},
		"competition": {"active": true, "title": "Test competition"},
		"game": {"player": 2, "ball": 3, "score": 7100},
	}})
	check(view.board_keys()[view.board_index] == "competition", "Active competition heads boards")
	check(view.state.score == 7100 and view.state.ball == 3, "Game snapshot supplies dynamic values")
	view.show_screen("game_started")
	view.pinballctl_scene_session(true)
	var first_actions: Array[String] = view.game_started_actions
	check(first_actions.size() == view.RelayActions.ACTIONS_PER_LOOP and first_actions.all(func(action): return first_actions.count(action) == 1),
		"Game Started schedules eight distinct Relay actions per loop")
	view._process(30.2)
	check(view.screen == "game_started" and is_equal_approx(view.elapsed, 0.2) and not view.complete,
		"Game Started stays active across its thirty-second loop")
	check(view.game_started_actions[0] != first_actions[-1], "Relay never repeats an action across the wrap")
	check(view.game_started_actions.all(func(action): return not first_actions.has(action)),
		"The next loop uses the remaining Relay actions before reshuffling")
	check(events[-1][0] == "BACKGLASS_HIGH_SCORES_REQUESTED" and view.state.score == 7100 and view.state.ball == 3,
		"Game Started refreshes live values without changing the score")
	var update := {"SCORE": "00007120", "player_name": "Test Player", "BACKGLASS_STATE":
		'{"screen":"bonus","bonus":37000,"multiplier":2,"event_id":"bonus-test"}'}
	view.pinballctl_text_values(update)
	view._process(0.45)
	update.SCORE = "00007121"
	view.pinballctl_text_values(update)
	check(view.screen == "bonus" and is_equal_approx(view.elapsed, 0.45), "Token updates never restart a bonus")
	check(view.state.score == 7121 and view.state.bonus == 37000 and view.state.multiplier == 2, "Score token and structured bonus are independent")
	check(is_equal_approx(view.DURATIONS["game_over"], 10.0), "Game Over gives the final score a ten-second cue")
	for id in ["bonus", "tilt", "game_over"]:
		view.show_screen(id)
		var completions: Array = []
		var record := func(): completions.append(id)
		view.pinballctl_scene_finished.connect(record)
		view.pinballctl_scene_session(true)
		view._process(view.DURATIONS[id] - 0.02)
		check(completions.is_empty(), "%s plays its full cue" % id)
		view._process(0.03)
		view._process(3.0)
		check(completions == [id] and view.complete, "%s requests completion exactly once" % id)
		view.pinballctl_scene_finished.disconnect(record)
	view.pinballctl_scene_session(false)
	view.show_screen("tilt")
	view._process(2.0)
	check(view.screen == "attract", "Standalone cue returns to attract")
	view.queue_free()
	await process_frame
	for id in ["attract", "menu", "high_scores", "tilt", "bonus", "game_over", "mode", "game_started"]:
		var entry = load("res://ctl_sample/entries/%s.tscn" % id).instantiate()
		root.add_child(entry)
		check(entry.screen == id, "Entry resolves " + id)
		entry.queue_free()
		await process_frame
	print("Sample backglass smoke: %d failure(s)" % failures)
	quit(1 if failures else 0)
