extends SceneTree
## Capture deterministic animation frames for review, without waiting in real time.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var output := OS.get_environment("BACKGLASS_CAPTURE_DIR")
	if output.is_empty():
		push_error("Set BACKGLASS_CAPTURE_DIR")
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(output)
	root.size = Vector2i(960, 540)
	var scene = load("res://zelda/main.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	scene.set_process(false)
	scene.enter_preview()
	for id in ["bonus", "jackpot", "ball_saved", "extra_ball", "quest_complete"]:
		for i in scene.Catalog.SCREENS.size():
			if scene.Catalog.SCREENS[i][0] == id: scene.preview_index = i
		scene._play_preview()
		var duration: float = scene.Catalog.screen(id)[5]
		for frame in ceili((duration + 0.35) * 20):
			scene.elapsed = frame / 20.0
			scene.clock_time = scene.elapsed
			scene.queue_redraw()
			await process_frame
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(output.path_join("%s-%03d.png" % [id, frame]))
	quit()
