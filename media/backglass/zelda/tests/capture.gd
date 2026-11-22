extends SceneTree
## Render actual Godot output, never a separate mockup. Outputs are not source assets.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var output := OS.get_environment("BACKGLASS_CAPTURE_DIR")
	if output.is_empty():
		push_error("Set BACKGLASS_CAPTURE_DIR to an absolute output directory")
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(output)
	var capture_size := OS.get_environment("BACKGLASS_CAPTURE_SIZE").split("x")
	root.size = Vector2i(int(capture_size[0]), int(capture_size[1])) if capture_size.size() == 2 else Vector2i(1920, 1080)
	var only := OS.get_environment("BACKGLASS_CAPTURE_ONLY").split(",")
	var scene = load("res://zelda/main.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	scene.set_process(false)
	scene.enter_preview()
	for i in scene.Catalog.SCREENS.size():
		if not only[0].is_empty() and scene.Catalog.SCREENS[i][0] not in only: continue
		scene.preview_index = i
		scene._play_preview()
		var duration: float = scene.Catalog.SCREENS[i][5]
		scene.elapsed = minf(6, duration * 0.5) if duration > 0 else 6
		scene.clock_time = scene.elapsed
		scene.queue_redraw()
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(output.path_join(scene.screen_id + ".png"))
	scene.leave_preview()
	for id in ["menu", "quests", "settings", "instructions"]:
		if not only[0].is_empty() and id not in only: continue
		scene.show_screen(id)
		scene.elapsed = 6
		scene.queue_redraw()
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(output.path_join(id + ".png"))
	scene.enter_preview()
	scene.queue_redraw()
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join("preview.png"))
	quit()
