extends RefCounted
## Reusable recipes for Relay's gestures and expressions.
const ACTIONS := {
	"wave": {"pose": "play_wave", "duration": 1.85, "gaze": Vector2(0, -3)},
	"wink": {"pose": "play_wink", "duration": 1.40, "gaze": Vector2(0, 0)},
	"fist_pump": {"pose": "pump", "duration": 1.40, "gaze": Vector2(2, -4)},
	"double_fist": {"pose": "cheer", "duration": 1.50, "gaze": Vector2(0, -6)},
	"side_eye": {"pose": "side_eye", "duration": 1.95, "gaze": Vector2(-19, -2)},
	"squint": {"pose": "squint", "duration": 1.75, "gaze": Vector2(-13, 3)},
	"shrug": {"pose": "shrug", "duration": 1.70, "gaze": Vector2(-4, 0)},
	"open_palm": {"pose": "present", "duration": 1.80, "gaze": Vector2(-15, -1)},
	"crossed_eyes": {"pose": "crossed_eyes", "duration": 1.55, "gaze": Vector2(-2, 4)},
	"deadpan": {"pose": "unimpressed", "duration": 1.95, "gaze": Vector2(-12, 1)},
	"pout": {"pose": "play_pout", "duration": 1.55, "gaze": Vector2(7, -4)},
	"gasp": {"pose": "comic_gasp", "duration": 1.35, "gaze": Vector2(0, -4)},
	"snicker": {"pose": "snicker", "duration": 1.65, "gaze": Vector2(-10, 1)},
	"tongue_out": {"pose": "tongue_out", "duration": 1.50, "gaze": Vector2(6, -3)},
	"sheepish_grin": {"pose": "sheepish", "duration": 1.75, "gaze": Vector2(11, 4)},
	"quizzical": {"pose": "quizzical", "duration": 1.70, "gaze": Vector2(-8, -1)},
}
const ACTIONS_PER_LOOP := 8
const FIRST_ACTION := 1.5
const ACTION_INTERVAL := 3.5

static func next_lineup(bag: Array[String], previous_action: String) -> Array[String]:
	# Carry unused actions across loop boundaries so every face gets a turn.
	var lineup: Array[String] = []
	for _slot in ACTIONS_PER_LOOP:
		if bag.is_empty():
			bag.assign(shuffled(previous_action))
		for index in bag.size():
			if not lineup.has(bag[index]):
				previous_action = bag.pop_at(index)
				lineup.append(previous_action)
				break
	return lineup

static func shuffled(previous_action: String) -> Array[String]:
	var lineup: Array[String] = []
	lineup.assign(ACTIONS.keys())
	lineup.shuffle()
	if lineup[0] == previous_action:
		lineup[0] = lineup[1]
		lineup[1] = previous_action
	return lineup

static func sample(time: float, lineup: Array[String]) -> Dictionary:
	var slot := floori((time - FIRST_ACTION) / ACTION_INTERVAL)
	if slot < 0 or slot >= lineup.size():
		return {}
	var action: Dictionary = ACTIONS[lineup[slot]]
	var age := time - FIRST_ACTION - slot * ACTION_INTERVAL
	var duration: float = action.duration
	if age >= duration:
		return {}
	var strength := smoothstep(0.0, 0.24, age) * (1.0 - smoothstep(duration - 0.34, duration, age))
	return {"pose": action.pose, "gaze": action.gaze, "age": age, "strength": strength}
