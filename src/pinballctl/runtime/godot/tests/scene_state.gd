extends SceneTree
const Manager = preload("res://scripts/SceneManager.gd")
class Receiver:
	extends Node
	var received: Dictionary = {}
	func pinballctl_text_values(values: Dictionary) -> void:
		received = values.duplicate(true)
		values["mutated"] = true

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var manager = Manager.new()
	root.add_child(manager)
	var wrapper := Control.new()
	var receiver := Receiver.new()
	var label := Label.new()
	label.text = "Score {{SCORE}}"
	wrapper.add_child(receiver)
	wrapper.add_child(label)
	manager.add_child(wrapper)
	manager.scene_stack_nodes = [wrapper]
	manager.apply_text_values({"score": 10, "BACKGLASS_STATE": '{"screen":"bonus"}'})
	assert(receiver.received.score == 10)
	assert(not manager.text_values.has("mutated"))
	assert(label.text == "Score 10")
	manager.update_text("score", 20)
	assert(receiver.received.score == 20)
	assert(label.text == "Score 20")
	manager.update_text("BACKGLASS_STATE", '{"screen":"gameplay","score":20}')
	assert(receiver.received.BACKGLASS_STATE.contains('"gameplay"'))
	print("Scene state hook: passed (nested receiver, copied values, existing labels)")
	var pack := OS.get_environment("BACKGLASS_TEST_PACK")
	if not pack.is_empty():
		var result: Dictionary = manager.set_scene("hyrule", "res://zelda/main.tscn", "Hyrule", pack)
		assert(result.ok)
		await process_frame
		manager.update_text("BACKGLASS_STATE", '{"screen":"gameplay","score":12345}')
		var presentation = manager.current_scene_node.get_child(0)
		assert(presentation.state.score == 12345)
		assert(presentation.backgrounds.size() == 5)
		manager.dispatch_input_action("backglass_multiball")
		assert(presentation.screen_id == "multiball")
		manager.dispatch_input_action("backglass_preview")
		assert(presentation.preview)
		print("Exported backglass pack: passed (loaded by host, state and input delivered)")
		manager.update_text("BACKGLASS_STATE", "{}")
		var ids: Array = ["menu", "quests", "instructions", "settings", "preview"]
		for entry in load("res://zelda/catalog.gd").SCREENS: ids.append(entry[0])
		for id in ids:
			var loaded: Dictionary = manager.set_scene("hyrule_" + id, "res://zelda/entries/" + id + ".tscn", "Hyrule", pack)
			assert(loaded.ok)
			await process_frame
			var view = manager.current_scene_node.get_child(0)
			assert(view.gallery if id == "preview" else view.screen_id == id)
		print("Exported scene entries: all 25 loaded at their intended screen")
	quit()
