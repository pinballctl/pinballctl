extends RefCounted
## Rig for the Cabinet Host design. Layer poses use the scene clock so an
## interrupted cue leaves no running tweens behind.
const ART := preload("res://ctl_sample/assets/relay-parts.svg")
const SHELL := Rect2(0, 0, 512, 512)
const RAISED_GLOVE := Rect2(512, 0, 256, 256)
const RESTING_GLOVE := Rect2(768, 0, 256, 256)
const SHOE := Rect2(1024, 0, 256, 256)
const SMILE := Rect2(1280, 0, 256, 256)
const GASP := Rect2(1536, 0, 256, 256)
const FROWN := Rect2(1280, 256, 256, 256)
const SMIRK := Rect2(1536, 256, 256, 256)
const FIST := Rect2(512, 256, 256, 256)
const POINT := Rect2(768, 256, 256, 256)
const LAUGH := Rect2(1024, 256, 256, 256)
const INK := Color("080c1c")
const CLOTH := Color("152039")
const MINT := Color("7af6cd")
const RED := Color("ff766d")
const HIGHLIGHT := Color("fff1d9")

static func draw(v: Control, at: Vector2, scale: float, time: float, pose: String,
		stretch: Vector2, lean: float, gesture: float, gaze: Vector2) -> void:
	var settle := 1.0 if pose == "wink" else clampf(time / 0.28, 0.0, 1.0)
	var rise := pow(1.0 - settle, 3.0) * 161.0 - sin(settle * PI) * 25.0
	var shock := sin(clampf(time / 0.29, 0, 1) * PI) if pose == "alarm" else 0.0
	var slump := smoothstep(0.24, 0.96, time) if pose == "end" else 0.0
	var joy := smoothstep(0.26, 0.59, time) if pose == "joy" else 0.0
	var bounce := sin(joy * PI) * 37.0
	var bob := sin(time * 2.6) * 4.0 if pose in ["alarm", "joy", "easy", "hard"] else 0.0
	var score_glance := 0.0
	var wipe := 0.0
	var sigh := 0.0
	if pose == "end":
		score_glance = maxf(beat(time, 1.08, 1.68, 2.80), beat(time, 6.05, 6.84, 7.72) * 0.72)
		wipe = beat(time, 3.10, 3.66, 4.58)
		sigh = maxf(beat(time, 4.47, 5.22, 6.32), beat(time, 7.72, 8.56, 9.70) * 0.81)
	var root := at + Vector2(-14 * shock, rise + bob - 39 * shock - bounce) * scale
	var canvas: Transform2D = v.art_transform
	var rig := canvas * Transform2D(lean + shock * sin(time * 34.0) * 0.12, stretch * scale, 0, root)
	var head := Vector2(-7 * slump, 24 * slump)
	head += Vector2(-9.0 * score_glance, 13.0 * sigh - 10.0 * score_glance)
	match pose:
		"inspect": head = Vector2(5, -2) * gesture
		"build_grin": head = Vector2(3, -5) * gesture
		"ready": head = Vector2(6, 12) * gesture
		"determined": head = Vector2(11, 4) * gesture
		"invite": head = Vector2(0, 14) * gesture
		"bumper", "grin": head = Vector2(4, -8) * gesture
		"shrug": head = Vector2(0, 9) * gesture
		"present": head = Vector2(-5, 1) * gesture
		"pleased": head = Vector2(0, -10) * gesture
		"drain": head = Vector2(5, 17) * gesture
		"unimpressed": head = Vector2(-7, 6) * gesture

	v.draw_set_transform_matrix(rig)
	for side in [-1, 1]:
		var hip := head * 0.5 + Vector2(side * 46, 79)
		var knee := Vector2(side * lerpf(52, 69, slump), 119)
		var ankle := Vector2(side * 59, 147)
		var foot_angle := 0.0
		if pose == "jump":
			knee += Vector2(16, -12) * gesture
			ankle += Vector2(23, -20 + side * 13) * gesture
			foot_angle = side * 0.24 * gesture
		elif pose in ["ready", "drain"]:
			knee += Vector2(side * 17, 7) * gesture
		elif pose == "determined" and side == 1:
			knee.x += 20.0 * gesture
			ankle.x += 15.0 * gesture
		limb(v, hip, knee, ankle)
		attached_part(v, rig, SHOE, ankle, Vector2(43, 50), 0.60, foot_angle, side)
	var wipe_shoulder := Vector2.ZERO
	var wipe_elbow := Vector2.ZERO
	var wipe_wrist := Vector2.ZERO
	var wipe_angle := 0.0
	for side in [-1, 1]:
		var shoulder := head + Vector2(side * 90, 30)
		var wrist := Vector2(side * 112, 67 + side * sin(time * 4.7) * 4)
		var elbow := Vector2(side * 111, 43)
		var hand := RESTING_GLOVE
		var palm_turn := 0.0
		match pose:
			"play_wave":
				if side == 1:
					wrist = wrist.lerp(Vector2(132, -12), gesture)
					elbow = elbow.lerp(Vector2(121, 23), gesture)
					palm_turn = sin(time * 16.0) * 0.34 * gesture
					if gesture > 0.45:
						hand = RAISED_GLOVE
			"wink":
				if side == 1:
					wrist = Vector2(132, -12)
					elbow = Vector2(121, 23)
					palm_turn = sin(time * 16.0) * 0.34
					hand = RAISED_GLOVE
			"proud":
				if side == 1:
					wrist = wrist.lerp(Vector2(128, 36), gesture)
					elbow = elbow.lerp(Vector2(107, 57), gesture)
					palm_turn = 0.38
					if gesture > 0.46:
						hand = POINT
			"easy", "hard":
				var pointing_side := -1 if pose == "easy" else 1
				if side == pointing_side:
					wrist = Vector2(side * lerpf(123.0, 137.0, gesture), 22)
					elbow = Vector2(side * 108, 32)
					palm_turn = side * 0.13
					hand = POINT
				elif pose == "hard":
					wrist = Vector2(side * 108, 51)
					elbow = Vector2(side * 125, 40)
			"jump":
				wrist = wrist.lerp(Vector2(side * 127, 10 - side * 18), gesture)
				elbow = elbow.lerp(Vector2(side * 119, 42), gesture)
				if gesture > 0.45:
					hand = RAISED_GLOVE
			"ready":
				wrist = wrist.lerp(Vector2(side * 112, 52), gesture)
				elbow = elbow.lerp(Vector2(side * 126, 48), gesture)
			"determined":
				wrist = wrist.lerp(Vector2(side * 109, 56 - side * 9), gesture)
				elbow = elbow.lerp(Vector2(side * 125, 39), gesture)
			"bumper":
				wrist += Vector2(side * 5, -12) * gesture
			"drain":
				wrist += Vector2(-side * 9, 17) * gesture
			"shrug":
				wrist = wrist.lerp(Vector2(side * 126, 40), gesture)
				elbow = elbow.lerp(Vector2(side * 107, 57), gesture)
				palm_turn = side * 0.25
				if gesture > 0.40:
					hand = RAISED_GLOVE
			"present":
				if side == 1:
					wrist = wrist.lerp(Vector2(136, 49), gesture)
					elbow = elbow.lerp(Vector2(112, 59), gesture)
					palm_turn = 0.30
					if gesture > 0.45:
						hand = RAISED_GLOVE
				else:
					wrist = wrist.lerp(Vector2(-105, 58), gesture)
					elbow = elbow.lerp(Vector2(-121, 44), gesture)
			"unimpressed", "pleased":
				wrist += Vector2(-side * 9, -10) * gesture
			"alarm":
				var recoil := smoothstep(0.03, 0.16, time)
				wrist = wrist.lerp(Vector2(side * (124 + 6 * shock), -15), recoil)
				elbow = elbow.lerp(Vector2(side * 124, 27), recoil)
				palm_turn = side * 0.18
				if recoil > 0.4:
					hand = RAISED_GLOVE
			"joy", "pump", "cheer":
				var lift := joy if pose == "joy" else gesture
				if side == 1 or pose == "cheer":
					wrist = wrist.lerp(Vector2(side * (128 + sin(time * 18.0) * 4.0), -39), lift)
					elbow = elbow.lerp(Vector2(side * 119, 13), lift)
					if lift > 0.46:
						hand = FIST
			"end":
				wrist = wrist.lerp(Vector2(side * 101, 92 - side * 5), slump)
				elbow = elbow.lerp(Vector2(side * 113, 66), slump)
				wrist += Vector2(-side * 4.0, 11.0) * sigh
				if side == 1:
					var wipe_travel := smoothstep(3.48, 4.05, time)
					wrist = wrist.lerp(head + Vector2(76 + wipe_travel * 19, -6 + wipe_travel * 37), wipe)
					elbow = elbow.lerp(head + Vector2(120, 56), wipe)
		var direction := (wrist - elbow).angle()
		if side == 1 and wipe > 0.30:
			# Draw the wiping arm over the visor with the glove still attached to its cuff.
			wipe_shoulder = shoulder
			wipe_elbow = elbow
			wipe_wrist = wrist
			wipe_angle = direction - Vector2.DOWN.angle()
			continue
		limb(v, shoulder, elbow, wrist)
		var raised_angle := direction - Vector2.UP.angle() + palm_turn
		match hand:
			RAISED_GLOVE: attached_part(v, rig, hand, wrist, Vector2(53, 99), 0.66, raised_angle, side)
			FIST: attached_part(v, rig, hand, wrist, Vector2(62, 90), 0.62, raised_angle, side)
			POINT: attached_part(v, rig, hand, wrist, Vector2(64, 98), 0.56, raised_angle, side)
			_: attached_part(v, rig, hand, wrist, Vector2(58, 31), 0.61, direction - Vector2.DOWN.angle(), -side)

	var cock := 0.10 * gesture if pose == "proud" else 0.0
	if pose in ["quizzical", "snicker", "sheepish"]:
		cock = (0.14 if pose == "quizzical" else -0.09) * gesture
	v.draw_set_transform_matrix(rig * Transform2D(slump * 0.17 + cock - 0.18 * score_glance + 0.05 * sigh, head))
	part(v, SHELL, Rect2(-123, -123, 246, 246))
	if pose == "end":
		draw_disappointed_face(v, time, slump, score_glance, wipe, sigh)
		if wipe > 0.30:
			v.draw_set_transform_matrix(rig)
			limb(v, wipe_shoulder, wipe_elbow, wipe_wrist)
			attached_part(v, rig, RESTING_GLOVE, wipe_wrist, Vector2(58, 31), 0.61, wipe_angle, -1)
	else:
		draw_face(v, time, pose, joy, gaze, gesture)
	v.draw_set_transform_matrix(canvas)

static func beat(time: float, start: float, peak: float, finish: float) -> float:
	return smoothstep(start, peak, time) * (1.0 - smoothstep(peak, finish, time))

static func part(v: Control, source: Rect2, target: Rect2) -> void:
	v.draw_texture_rect_region(ART, target, source)

static func attached_part(v: Control, rig: Transform2D, source: Rect2, joint: Vector2, pivot: Vector2,
		scale: float, angle: float, side: int) -> void:
	# Pivots are measured in the SVG tile. Mirror and rotate around the joint.
	var attachment := Transform2D(angle, Vector2(side * scale, scale), 0.0, joint)
	v.draw_set_transform_matrix(rig * attachment)
	part(v, source, Rect2(-pivot, Vector2(128, 128)))
	v.draw_set_transform_matrix(rig)

static func limb(v: Control, start: Vector2, control: Vector2, end: Vector2) -> void:
	var points := PackedVector2Array()
	for step in 13:
		var progress := step / 12.0
		points.append(start.lerp(control, progress).lerp(control.lerp(end, progress), progress))
	v.draw_polyline(points, INK, 22.0, true)
	v.draw_polyline(points, CLOTH, 14.0, true)
	var direction := (end - control).normalized()
	cuffs(v, end - direction * 18, end - direction * 8, direction)

static func cuffs(v: Control, a: Vector2, b: Vector2, direction: Vector2) -> void:
	var normal := direction.orthogonal() * 8.0
	for p in [a, b]:
		v.draw_line(p - normal, p + normal, INK, 11, true)
		v.draw_line(p - normal, p + normal, MINT, 6, true)

static func draw_disappointed_face(v: Control, time: float, slump: float, score_glance: float, wipe: float, sigh: float) -> void:
	var blink := maxf(beat(time, 0.72, 0.82, 0.96), beat(time, 5.02, 5.20, 5.45))
	blink = maxf(blink, beat(time, 8.37, 8.54, 8.88))
	for side in [-1, 1]:
		var eye := Vector2(side * 34 - 18.0 * score_glance, -16 + 13.0 * slump - 10.0 * score_glance)
		var lid := eye + Vector2(0, -4.0 - 2.0 * sigh)
		if blink > 0.55:
			v.draw_line(lid - Vector2(9, 0), lid + Vector2(9, 0), MINT, 5, true)
		else:
			v.draw_arc(lid, 9.0 - 2.0 * sigh, 0.22, 2.92, 22, MINT, 5, true)
			v.draw_line(eye + Vector2(-side * 12, -19), eye + Vector2(side * 10, -11), Color(MINT, 0.80), 4, true)

	if sigh > 0.32:
		part(v, GASP, Rect2(-20, 26, 40, 44 + 10 * sigh))
	else:
		part(v, FROWN, Rect2(-43, 18, 86, 80))

	var tear := smoothstep(2.45, 3.45, time)
	var tear_alpha := smoothstep(2.45, 2.63, time) * (1.0 - smoothstep(3.40, 3.80, time))
	if tear_alpha > 0.0 and wipe < 0.76:
		var point := Vector2(41 + 14 * tear, 5 + 50 * tear)
		var water := Color(Color("88d9f0"), tear_alpha)
		v.draw_colored_polygon(PackedVector2Array([point + Vector2(-2, -12),
			point + Vector2(5, -2), point + Vector2(-5, 1)]), water)
		v.draw_circle(point, 5.0, water, true, -1.0, true)

static func draw_face(v: Control, time: float, pose: String, joy: float, gaze: Vector2,
		gesture: float) -> void:
	var blink := fposmod(time + 0.8, 4.1) > 3.99
	var wink := pose == "proud" or (pose == "wink" and fposmod(time + 0.12, 1.68) > 1.21) or (pose == "play_wink" and gesture > 0.5)
	var laughing := pose in ["pump", "cheer"] or (pose == "joy" and joy > 0.54)
	var side_eye := pose in ["side_eye", "shrug", "present", "unimpressed"]
	var squint := pose in ["determined", "squint", "grin"]
	var glance := gaze
	match pose:
		"easy": glance = Vector2(-10, 0)
		"hard": glance = Vector2(10, 0)

	for side in [-1, 1]:
		var socket := Vector2(side * 34, -16)
		var eye := socket + glance
		if pose == "alarm":
			v.draw_arc(eye, 14, 0.0, TAU, 28, RED, 5, true)
			v.draw_circle(eye + Vector2(0, 1), 4.3, RED, true, -1.0, true)
			v.draw_line(eye + Vector2(-10, -23), eye + Vector2(10, -24), RED, 4, true)
		elif side_eye:
			var lid := socket + Vector2(0, -2 if side == -1 else 1)
			var pupil := lid + Vector2(clampf(glance.x * 0.58, -10.0, 10.0), 0)
			v.draw_arc(pupil, 6.1, 0.13, 2.99, 22, MINT, 6, true)
			v.draw_line(lid + Vector2(-14, 0), lid + Vector2(14, -2), MINT, 4, true)
		elif squint:
			v.draw_colored_polygon(PackedVector2Array([eye + Vector2(-side * 13, -1),
				eye + Vector2(side * 15, -8), eye + Vector2(side * 10, 5), eye + Vector2(-side * 9, 6)]), MINT)
		elif laughing or pose in ["easy", "pleased"] or (pose == "invite" and gesture > 0.40):
			var height := 12.0 if laughing else 6.0
			v.draw_polyline(PackedVector2Array([eye + Vector2(-15, 4), eye + Vector2(-8, -height * 0.7),
				eye + Vector2(0, -height), eye + Vector2(8, -height * 0.7), eye + Vector2(15, 4)]), MINT, 6, true)
		elif pose == "hard":
			v.draw_colored_polygon(PackedVector2Array([eye + Vector2(-side * 14, -1),
				eye + Vector2(side * 15, -12), eye + Vector2(side * 9, 9), eye + Vector2(-side * 7, 9)]), MINT)
		elif pose == "crossed_eyes":
			v.draw_circle(socket, 13.0, MINT, true, -1.0, true)
			v.draw_circle(socket + Vector2(-side * 7, 1), 6.0, INK, true, -1.0, true)
		elif pose == "comic_gasp":
			v.draw_circle(eye, 11.0 + 6.0 * gesture, MINT, true, -1.0, true)
			v.draw_circle(eye + Vector2(3, -3), 4.5, INK, true, -1.0, true)
		elif (pose == "snicker" and side == -1) or (pose == "sheepish" and side == 1):
			v.draw_arc(eye + Vector2(0, 8), 11, 3.25, 6.0, 24, MINT, 5, true)
		elif blink or (wink and side == 1):
			v.draw_arc(eye + Vector2(0, 5), 13, 3.69, 5.74, 18, MINT, 6, true)
		else:
			var radius := 13.0 if pose == "jump" or (pose == "curious" and side == 1) else 10.0
			if pose == "quizzical":
				radius = 15.0 if side == 1 else 7.5
			elif pose == "play_pout":
				radius = 7.5
			v.draw_circle(eye, radius, MINT, true, -1.0, true)
			v.draw_circle(eye + Vector2(3, -4), 2.8, HIGHLIGHT, true, -1.0, true)

	if laughing:
		part(v, LAUGH, Rect2(-52, 14, 104, 87))
		return
	match pose:
		"alarm":
			part(v, GASP, Rect2(-45, 7, 90, 100))
		"jump":
			part(v, GASP, Rect2(-24, 22, 48, 64))
		"build", "inspect", "build_grin":
			if gesture <= 0.40:
				part(v, SMIRK, Rect2(-32, 18, 76, 69))
			elif pose == "build":
				var width := 39.0 * gesture
				part(v, GASP, Rect2(10 - width * 0.5, 19, width, 55))
			elif pose == "inspect":
				v.draw_arc(Vector2(13, 47), 15, 3.54, 5.28, 22, INK, 6, true)
			else:
				part(v, LAUGH, Rect2(-33, 17, 88, 68))
		"ready":
			var lift := 6.0 * (1.0 - gesture)
			v.draw_polyline(PackedVector2Array([Vector2(-16, 42), Vector2(-1, 46), Vector2(16, 46),
				Vector2(32, 43 - lift)]), INK, 6, true)
		"bumper":
			part(v, SMILE, Rect2(-33, 15, 89, 69))
		"grin":
			part(v, LAUGH, Rect2(-34, 19, 81, 67))
		"curious":
			v.draw_arc(Vector2(7, 37), 16, 0.33, 2.47, 20, INK, 6, true)
		"side_eye", "present":
			part(v, SMIRK, Rect2(-47, 18, 90, 73))
		"shrug":
			part(v, GASP, Rect2(-33, 27, 47, 46))
		"unimpressed":
			v.draw_line(Vector2(-21, 43), Vector2(24, 43), INK, 7, true)
		"determined", "squint":
			v.draw_polyline(PackedVector2Array([Vector2(-17, 46), Vector2(11, 46), Vector2(28, 39)]), INK, 6, true)
		"drain":
			v.draw_polyline(PackedVector2Array([Vector2(-16, 46), Vector2(-8, 40), Vector2(1, 40),
				Vector2(12, 44), Vector2(26, 45)]), INK, 6, true)
		"invite":
			v.draw_arc(Vector2(0, 35), 23, 0.26, 2.88, 26, INK, 6, true)
		"crossed_eyes":
			part(v, LAUGH, Rect2(-57, 13, 110, 87))
		"comic_gasp":
			part(v, GASP, Rect2(-36, 13, 72, 89))
		"snicker":
			part(v, SMIRK, Rect2(-33, 19, 93, 70))
		"sheepish":
			part(v, LAUGH, Rect2(-43, 21, 77, 63))
		"play_pout":
			v.draw_circle(Vector2(-37, 45), 6, Color("edb1a4"), true, -1.0, true)
			v.draw_circle(Vector2(41, 41), 6, Color("edb1a4"), true, -1.0, true)
			v.draw_arc(Vector2(2, 54), 12, 3.36, 5.98, 24, INK, 6, true)
		"tongue_out":
			part(v, SMILE, Rect2(-52, 10, 92, 71))
			v.draw_circle(Vector2(18, 60), 16, INK, true, -1.0, true)
			v.draw_circle(Vector2(18, 58), 12, Color("ffae9e"), true, -1.0, true)
			v.draw_line(Vector2(16, 52), Vector2(19, 61), Color("c46375"), 3.0, true)
		"quizzical":
			v.draw_arc(Vector2(14, 48), 15, 3.38, 5.2, 24, INK, 6, true)
		"hard", "proud", "watch", "game_started":
			part(v, SMIRK, Rect2(-43, 19, 86, 74))
		_:
			part(v, SMIRK if wink else SMILE, Rect2(-44, 18, 88, 75))
