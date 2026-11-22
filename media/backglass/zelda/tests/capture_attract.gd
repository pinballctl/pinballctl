extends SceneTree
## Storyboard captures: each shot and both sides of every edit.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var output := OS.get_environment("BACKGLASS_CAPTURE_DIR")
	if output.is_empty():
		push_error("Set BACKGLASS_CAPTURE_DIR")
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(output)
	root.size = Vector2i(1280,720)
	var scene = load("res://zelda/main.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	scene.set_process(false)
	var times := [0.1, 3.5, 6.8, 7.3, 10.0, 13.3, 16.5, 20.3, 23.0, 26.3, 28.5, 31.3, 35.0, 39.3, 41.5, 43.8]
	for time in times:
		scene.elapsed = time
		scene.clock_time = time
		for settle in 3:
			scene.queue_redraw()
			await process_frame
			await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(output.path_join("attract-%04d.png" % roundi(time * 10)))
	# Reduced motion remains readable throughout every shot.
	scene.reduced_motion = true
	for time in [3.5,16.5,28.5,35.0]:
		scene.elapsed = time
		for settle in 3:
			scene.queue_redraw()
			await process_frame
			await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(output.path_join("still-%04d.png" % roundi(time * 10)))
	quit()
