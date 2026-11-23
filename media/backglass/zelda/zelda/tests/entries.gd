extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var failures := 0
	var dir := DirAccess.open("res://zelda/entries")
	for file in dir.get_files():
		if not file.ends_with(".tscn"): continue
		var scene = load("res://zelda/entries/" + file).instantiate()
		root.add_child(scene)
		var id := file.get_basename()
		if (id == "preview" and not scene.gallery) or (id != "preview" and scene.screen_id != id):
			push_error("Wrong initial screen: " + id)
			failures += 1
		scene.pinballctl_input_key("enter")
		scene.pinballctl_input_key("escape")
		if id != "preview" and scene.screen_id != id: failures += 1
		scene.queue_free()
		await process_frame
	print("Scene entries: %d failure(s)" % failures)
	quit(1 if failures else 0)
