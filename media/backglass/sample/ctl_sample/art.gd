extends RefCounted
## Original cabinet artwork, constructed from Godot vector primitives at 1920 × 1080.

const Scenery = preload("res://ctl_sample/scenery.gd")
const Loop = preload("res://ctl_sample/attract_loop.gd")
const BRAND := preload("res://ctl_sample/assets/pinballctl-logo.svg")
const SIZE := Vector2(1920, 1080)
const WHITE := Color("fff0d1")
const MINT := Color("67e8c3")
const AMBER := Color("ffb56b")
const RED := Color("ff776b")
const INK := Color("10182f")
const PANEL := Color("203951")
const EDGE := Color("456787")
const STEEL := Color("c1d6e2")
const POPS := [Vector2(1472, 329), Vector2(1648, 453), Vector2(1327, 477)]
const ATTRACT_TABLE_OFFSET := Vector2(-82, 0)
const PART_LANDINGS := [Vector2(1465, 530), Vector2(1238, 211), POPS[0],
	Loop.TARGETS[0], Vector2(1274, 822), Loop.REST]
const PART_DROP_HEIGHTS := [-675, -284, -332, -162, -350, -308]
const PART_REACTIONS := ["build", "inspect", "build_grin", "watch", "watch", "watch"]
const BALL_REACTIONS := [
	{"launch": "ready", "follow": "curious", "drain": "drain"},
	{"launch": "side_eye", "follow": "side_eye", "drain": "unimpressed"},
	{"launch": "determined", "follow": "squint", "drain": "pleased"},
]
const PALETTES := {
	"attract": [Color("173e59"), Color("7decd6")],
	"menu": [Color("1c4b55"), Color("91f2d0")],
	"mode": [Color("24445e"), Color("8de6cb")],
	"high_scores": [Color("243a67"), Color("89cffa")],
	"bonus": [Color("454666"), Color("ffca77")],
	"tilt": [Color("612f46"), Color("ffac77")],
	"game_over": [Color("3c355b"), Color("d5a2f3")],
	"game_started": [Color("173654"), Color("7ee9d2")],
}

static func render(v: Control) -> void:
	v.draw_rect(Rect2(Vector2.ZERO, v.size), INK)
	if v.complete:
		return
	var scale := minf(v.size.x / SIZE.x, v.size.y / SIZE.y)
	var origin := (v.size - SIZE * scale) * 0.5
	v.art_transform = Transform2D(0.0, Vector2.ONE * scale, 0.0, origin)
	v.draw_set_transform_matrix(v.art_transform)
	var palette: Array = PALETTES[v.screen]
	var background: Color = palette[0]
	var background_clock: float = v.elapsed
	var game_phase := 0.0
	if v.screen == "attract":
		background = background.lerp(Color("225862"), smoothstep(2.4, Loop.PLAY_START, v.elapsed))
		background = background.lerp(Color("343c6b"), smoothstep(Loop.PLAY_START, Loop.PLAY_START + 5.0, v.elapsed))
		background = background.lerp(palette[0], smoothstep(Loop.OUTRO_START, Loop.DURATION, v.elapsed))
	elif v.screen == "game_started":
		# Keep the ambient layer continuous across the live loop.
		game_phase = TAU * fposmod(v.elapsed, v.GAME_STARTED_LOOP) / v.GAME_STARTED_LOOP
		background_clock = 4.0 * (1.0 - cos(game_phase))
	Scenery.backdrop(v, background_clock, palette[1], background)
	match v.screen:
		"attract": attract(v)
		"menu": menu(v)
		"mode": choose_mode(v)
		"high_scores": high_scores(v)
		"bonus": bonus(v)
		"tilt": tilt(v)
		"game_over": game_over(v)
		"game_started": game_started(v, game_phase)
	v.draw_rect(Rect2(0, 0, 1920, 98), Color("090f17"))
	v.draw_rect(Rect2(0, 955, 1920, 125), Color(INK, 0.88))
	v.draw_line(Vector2(0, 98), Vector2(1920, 98), Color("365457"), 2)
	v.draw_line(Vector2(75, 955), Vector2(1845, 955), Color(palette[1], 0.38), 2)
	brand(v, Vector2(74, (98.0 - BRAND.get_height() * 290.0 / BRAND.get_width()) * 0.5), 290.0)
	match v.screen:
		"attract": start_prompt(v)
		"menu": footer(v, "FLIPPERS  Move", "START  Select")
		"mode": footer(v, "FLIPPERS  Choose mode", "START  Confirm")
		"high_scores": footer(v, "FLIPPERS  Change board", "START  Back")
		"bonus", "tilt", "game_over": text(v, player(v), Vector2(80, 1018), 27, STEEL)
	v.draw_set_transform(Vector2.ZERO)
	# Opaque margins mask strokes that cross the authored canvas.
	if origin.x > 0:
		v.draw_rect(Rect2(0, 0, origin.x, v.size.y), INK)
		v.draw_rect(Rect2(v.size.x - origin.x, 0, origin.x, v.size.y), INK)
	if origin.y > 0:
		v.draw_rect(Rect2(0, 0, v.size.x, origin.y), INK)
		v.draw_rect(Rect2(0, v.size.y - origin.y, v.size.x, origin.y), INK)

static func text(v: Control, label: String, point: Vector2, pixels: int, color: Color = WHITE,
		align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT, face: String = "ui") -> void:
	var font: Font = v.title_font if face == "title" else v.mono_font if face == "mono" else v.ui_font
	var width := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, pixels).x
	if align == HORIZONTAL_ALIGNMENT_CENTER: point.x -= width * 0.5
	elif align == HORIZONTAL_ALIGNMENT_RIGHT: point.x -= width
	v.draw_string(font, point, label, HORIZONTAL_ALIGNMENT_LEFT, -1, pixels, color)

static func brand(v: Control, p: Vector2, width: float) -> void:
	var dimensions := BRAND.get_size()
	v.draw_texture_rect(BRAND, Rect2(p, dimensions * (width / dimensions.x)), false)

static func footer(v: Control, left: String, right: String) -> void:
	text(v, left, Vector2(80, 1018), 27, STEEL)
	text(v, right, Vector2(1840, 1018), 27, MINT, HORIZONTAL_ALIGNMENT_RIGHT)

static func player(v: Control) -> String:
	var name: String = str(v.state.player_name).strip_edges().left(24)
	return ("%s   /   BALL %s" % [name if not name.is_empty() else "PLAYER %s" % v.state.player, v.state.ball]).to_upper()

static func formatted(n: int) -> String:
	return grouped(str(n))

static func grouped(digits: String) -> String:
	var result := ""
	for i in digits.length():
		if i > 0 and (digits.length() - i) % 3 == 0:
			result += ","
		result += digits[i]
	return result

static func ease_out(value: float) -> float:
	return 1.0 - pow(1.0 - clampf(value, 0.0, 1.0), 3.0)

static func title(v: Control, label: String, p: Vector2, size: int, color: Color = WHITE) -> void:
	text(v, label, p + Vector2(7, 10), size, Scenery.SHADOW, HORIZONTAL_ALIGNMENT_LEFT, "title")
	text(v, label, p, size, color, HORIZONTAL_ALIGNMENT_LEFT, "title")

static func start_prompt(v: Control) -> void:
	var pulse: float = (1.0 + sin(v.elapsed * 2.4)) * 0.5
	var plate := Rect2(1490, 979, 346, 67)
	var base := Color("214456")
	v.draw_rect(plate, base)
	var inside := plate.grow(-2.0)
	var half_width := inside.size.x * 0.46
	var phase: float = fposmod(v.elapsed, 4.2) / 4.2
	var centre := lerpf(inside.position.x - half_width, inside.end.x + half_width, phase)
	var stops := [centre - half_width, centre, centre + half_width]
	for i in 2:
		var left := clampf(stops[i], inside.position.x, inside.end.x)
		var right := clampf(stops[i + 1], inside.position.x, inside.end.x)
		if right <= left:
			continue
		var low := base.lerp(MINT, 0.18 * (1.0 - absf(left - centre) / half_width))
		var high := base.lerp(MINT, 0.18 * (1.0 - absf(right - centre) / half_width))
		v.draw_polygon(PackedVector2Array([Vector2(left, inside.position.y), Vector2(right, inside.position.y),
			Vector2(right, inside.end.y), Vector2(left, inside.end.y)]), PackedColorArray([low, high, high, low]))
	v.draw_rect(plate, MINT.lerp(WHITE, pulse * 0.4), false, 2)
	text(v, "PRESS START", Vector2(1663, 1023), 29, WHITE, HORIZONTAL_ALIGNMENT_CENTER, "title")

static func attract(v: Control) -> void:
	var time: float = v.elapsed
	var phase := Loop.phase(time)
	var build := time - Loop.BUILD_START
	var demo: Dictionary = {}
	if phase in ["play", "outro"]:
		demo = Loop.replay(Loop.replay_time(time))
	if build >= 0.0:
		playfield(v, demo, build, ATTRACT_TABLE_OFFSET)

	if phase == "build":
		var part := Loop.part_index(build)
		var progress := clampf(build / (Loop.PLAY_START - Loop.BUILD_START), 0.0, 1.0)
		attract_status(v, "BUILDING… " + Loop.PART_NAMES[part], progress)

	if not demo.is_empty():
		var reveal := ease_out((time - Loop.PLAY_START) / 0.58)
		var pos := Vector2(185, 179 + (1.0 - reveal) * 65)
		Scenery.faceplate(v, Rect2(pos, Vector2(714, 215)), Color("191f40"), Scenery.SKY, 31)
		text(v, "SCORE", pos + Vector2(39, 53), 27, Scenery.SKY, HORIZONTAL_ALIGNMENT_LEFT, "mono")
		var ball_count := "BALL %d / %d" % [demo.ball, Loop.PLAYS.size()]
		text(v, ball_count, pos + Vector2(675, 53), 26, AMBER, HORIZONTAL_ALIGNMENT_RIGHT, "title")
		text(v, formatted(demo.score), pos + Vector2(33, 156), 99, WHITE, HORIZONTAL_ALIGNMENT_LEFT, "mono")
		attract_status(v, "YOUR TURN" if phase == "outro" else demo.message)

	if time >= 0.15:
		attract_relay(v, time, phase, demo)

static func attract_status(v: Control, label: String, progress := -1.0) -> void:
	var plate := Rect2(185, 809, 714, 112)
	Scenery.faceplate(v, plate, Color("152a43"), EDGE, 22)
	if progress < 0.0:
		text(v, label, plate.get_center() + Vector2(0, 13), 36, WHITE, HORIZONTAL_ALIGNMENT_CENTER, "title")
		return

	text(v, label, plate.position + Vector2(28, 43), 31, WHITE, HORIZONTAL_ALIGNMENT_LEFT, "mono")
	var track := Rect2(plate.position + Vector2(28, 63), Vector2(658, 26))
	v.draw_rect(track, INK)
	var fill := track.grow(-2.0)
	fill.size.x *= progress
	if fill.size.x > 0.0:
		v.draw_rect(fill, Color("348b83"))
		var a := fill.position
		var b := fill.end
		var bounds := PackedVector2Array([a, Vector2(b.x, a.y), b, Vector2(a.x, b.y)])
		var offset: float = fposmod(v.elapsed * 96.0, 44.0)
		for i in range(-2, ceili(fill.size.x / 44.0)):
			var x := a.x + offset + i * 44.0
			var stripe := PackedVector2Array([Vector2(x + 16, a.y), Vector2(x + 36, a.y),
				Vector2(x + 20, b.y), Vector2(x, b.y)])
			for strip in Geometry2D.intersect_polygons(bounds, stripe):
				# A stripe touching the fill edge can clip to a line.
				if not Geometry2D.triangulate_polygon(strip).is_empty():
					v.draw_colored_polygon(strip, MINT)
	v.draw_rect(track, EDGE, false, 2.0)

static func attract_relay(v: Control, time: float, phase: String, replay: Dictionary) -> void:
	const TAKEOFF := 2.24
	const LAND := 2.85
	var progress := clampf(inverse_lerp(TAKEOFF, LAND, time), 0.0, 1.0)
	var travel := smoothstep(0.0, 1.0, progress)
	var air := 4.0 * progress * (1.0 - progress)
	var crouch := smoothstep(2.06, TAKEOFF, time) * (1.0 - smoothstep(TAKEOFF, TAKEOFF + 0.10, time))
	var landing := clampf((time - LAND) / 0.37, 0.0, 1.0)
	var compression := sin(PI * clampf(landing / 0.35, 0.0, 1.0))
	var rebound := sin(PI * clampf((landing - 0.35) / 0.65, 0.0, 1.0))
	var relay := Vector2(960, 498).lerp(Vector2(542, 574), travel)
	var scale := lerpf(2.36, 1.18, travel)
	var squash := crouch * 0.13 + compression * 0.20 - air * 0.07
	var stretch := Vector2(1.0 + squash * 0.62, 1.0 - squash)
	relay.y += squash * 178.0 * scale - 159.0 * air - 32.0 * rebound
	var gesture := 1.0
	var pose := "watch"
	var gaze := Vector2(12, 0) * smoothstep(LAND, LAND + 0.36, time)
	if phase == "outro":
		pose = "invite"
		gaze = Vector2.ZERO
		gesture = sin(PI * clampf((time - Loop.OUTRO_START - 0.15) / 0.54, 0.0, 1.0))
	elif time < TAKEOFF:
		pose = "wink"
		gaze = Vector2.ZERO
	elif time < LAND:
		pose = "jump"
		gesture = smoothstep(0.0, 0.4, air)
	elif phase == "build":
		var build := time - Loop.BUILD_START
		var part := Loop.part_index(build)
		var age: float = build - Loop.PART_TIMES[part]
		var target: Vector2 = PART_LANDINGS[part] + part_drop(age, Vector2(0, PART_DROP_HEIGHTS[part]))
		if part > 0:
			target = PART_LANDINGS[part - 1].lerp(target, smoothstep(0.0, 0.15, age))
		gaze = table_gaze(relay, target)
		pose = PART_REACTIONS[part]
		gesture = 1.0 - smoothstep(0.55, 0.93, age)
	elif phase == "play":
		var ball: int = replay.ball
		var reactions: Dictionary = BALL_REACTIONS[ball - 1]
		pose = reactions.follow
		gaze = table_gaze(relay, replay.point)
		if replay.launching:
			pose = reactions.launch
			gesture = replay.plunger
		elif replay.drained:
			pose = reactions.drain
			gesture = replay.drain_progress
		elif float(replay.reaction_weight) > 0.13:
			var weight: float = replay.reaction_weight
			gesture = smoothstep(0.13, 0.55, weight) * (1.0 - smoothstep(0.80, 1.0, weight))
			pose = replay.reaction
			if pose == "cheer":
				relay.y -= 39.0 * gesture
		if ball == 2:
			var aside: float = 1.0 - smoothstep(0.20, 0.96, replay.ball_age)
			if pose in ["shrug", "present", "unimpressed"]:
				aside = maxf(aside, gesture * 0.94)
			gaze = gaze.lerp(Vector2(-20, -4), aside)
	var flare := 39.0 * (1.0 - travel) * (0.75 + sin(time * 2.0) * 0.25)
	Scenery.flare(v, relay + Vector2(354, -222), flare, Color(AMBER, 0.65))
	Scenery.mascot(v, relay, scale, time - 0.15, pose, stretch, 0.0, gesture, gaze)

static func table_gaze(relay: Vector2, target: Vector2) -> Vector2:
	var direction := (target + ATTRACT_TABLE_OFFSET - relay).normalized()
	return Vector2(direction.x * 18.0, direction.y * 15.0)

static func part_drop(entrance: float, offset: Vector2) -> Vector2:
	var fall := clampf(entrance / 0.71, 0.0, 1.0)
	var drop := offset * (1.0 - fall * fall)
	var bounce := clampf((entrance - 0.71) / 0.29, 0.0, 1.0)
	drop.y -= sin(bounce * PI) * 16.0
	return drop

static func table_transform(v: Control, table: Transform2D, entrance: float, offset: Vector2) -> void:
	v.draw_set_transform_matrix(table.translated_local(part_drop(entrance, offset)))

static func playfield(v: Control, demo: Dictionary, build := 12.0, offset := Vector2.ZERO) -> void:
	var table: Transform2D = v.art_transform.translated_local(offset)
	var outline := PackedVector2Array([Vector2(1210, 161), Vector2(1648, 161), Vector2(1790, 283),
		Vector2(1790, 836), Vector2(1660, 902), Vector2(1244, 902), Vector2(1140, 812),
		Vector2(1140, 273), Vector2(1210, 161)])
	table_transform(v, table, build, Vector2(0, PART_DROP_HEIGHTS[0]))
	var extrusion := PackedVector2Array()
	for p in outline.slice(0, -1):
		extrusion.append(p + Vector2(30, 23))
	v.draw_colored_polygon(extrusion, Scenery.SHADOW)
	v.draw_colored_polygon(outline.slice(0, -1), Color("203b5c"))
	v.draw_polyline(outline, Color("88b5c9"), 9, true)
	v.draw_polyline(PackedVector2Array([Vector2(1248, 862), Vector2(1356, 844), Vector2(1420, 884),
		Vector2(1533, 884), Vector2(1622, 846), Vector2(1691, 849)]), Color("4c71a0"), 12, true)
	if build >= Loop.PART_TIMES[1]:
		table_transform(v, table, build - Loop.PART_TIMES[1], Vector2(0, PART_DROP_HEIGHTS[1]))
		v.draw_polyline(PackedVector2Array([Vector2(1224, 203), Vector2(1166, 299), Vector2(1166, 616), Vector2(1238, 707)]), WHITE, 7, true)
		v.draw_polyline(PackedVector2Array([Vector2(1238, 211), Vector2(1559, 211), Vector2(1652, 258),
			Vector2(1671, 328)]), Color("6f9fba"), 6, true)
		v.draw_polyline(PackedVector2Array([Vector2(1716, 827), Vector2(1716, 334), Vector2(1688, 258)]), EDGE, 5, true)
		v.draw_polyline(PackedVector2Array([Vector2(1763, 827), Vector2(1763, 329), Vector2(1695, 246)]), WHITE, 6, true)
		for side in [-1, 1]:
			var anchor := Vector2(1453 + side * 208, 645)
			var sling := PackedVector2Array([anchor + Vector2(-side * 67, 37),
				anchor + Vector2(side * 35, -28), anchor + Vector2(side * 41, 93)])
			v.draw_colored_polygon(sling, Color("467490"))
			sling.append(sling[0])
			v.draw_polyline(sling, Scenery.SKY, 4, true)
			v.draw_line(anchor + Vector2(-side * 46, 49), anchor + Vector2(side * 31, 82), WHITE, 4, true)
	var hits: Array = demo.get("hits", [0.0, 0.0, 0.0, 0.0, 0.0])
	for i in POPS.size():
		var arrive: float = build - Loop.PART_TIMES[2] - i * 0.31
		if arrive >= 0.0:
			table_transform(v, table, arrive, Vector2((i - 1) * 33, PART_DROP_HEIGHTS[2]))
			pop_bumper(v, POPS[i], hits[i], [MINT, AMBER, Scenery.SKY][i])
	var targets_down: Array = demo.get("targets_down", [false, false, false])
	for i in Loop.TARGETS.size():
		var arrive: float = build - Loop.TARGET_START - i * 0.13
		if arrive >= 0.0:
			table_transform(v, table, arrive, Vector2(0, PART_DROP_HEIGHTS[3]))
			var p: Vector2 = Loop.TARGETS[i]
			var accent: Color = [MINT, AMBER, Scenery.SKY][i]
			var slot := Rect2(p - Vector2(26, 11), Vector2(52, 39))
			v.draw_rect(slot, INK)
			v.draw_rect(slot, EDGE, false, 3)
			var height := 7 if targets_down[i] else 30
			v.draw_rect(Rect2(p + Vector2(-19, 20 - height), Vector2(38, height)), accent.darkened(0.55) if targets_down[i] else accent)
			if not targets_down[i]:
				v.draw_line(p + Vector2(-13, 12), p + Vector2(13, 12), WHITE, 3, true)
	if build >= Loop.PART_TIMES[4]:
		table_transform(v, table, build - Loop.PART_TIMES[4], Vector2(0, PART_DROP_HEIGHTS[4]))
		var pulse := 1.0 - ease_out(v.focus_elapsed / 0.25)
		var left: float = maxf(hits[3], pulse if v.focus_direction < 0 else 0.0)
		var right: float = maxf(hits[4], pulse if v.focus_direction > 0 else 0.0)
		flipper(v, Vector2(1274, 822), -0.25 - 0.56 * left, false, MINT)
		flipper(v, Vector2(1596, 822), 0.25 + 0.56 * right, true, AMBER)
	if build >= Loop.PART_TIMES[5]:
		table_transform(v, table, build - Loop.PART_TIMES[5], Vector2(0, PART_DROP_HEIGHTS[5]))
		plunger(v, demo.get("plunger", 0.0))
	if build >= Loop.PART_TIMES[5] and not demo.get("drained", false):
		var point: Vector2 = demo.get("point", Loop.REST)
		if demo.has("tail") and not demo.launching and point.distance_to(demo.tail) > 8.0:
			v.draw_line(demo.tail, point, Color(Scenery.SKY, 0.48), 12, true)
		steel_ball(v, point, 24)
	if float(demo.get("impact", 0.0)) > 0.0:
		table_impact(v, demo.contact, demo.impact, demo.points)
	v.draw_set_transform_matrix(v.art_transform)

static func plunger(v: Control, pull: float) -> void:
	var cap := Vector2(1740, 844 + pull * 14.0)
	var spring := PackedVector2Array([cap])
	for i in 7:
		spring.append(Vector2(1740 + (7 if i % 2 == 0 else -7), lerpf(cap.y, 879, (i + 1) / 8.0)))
	spring.append(Vector2(1740, 880))
	v.draw_line(Vector2(1725, 880), Vector2(1755, 880), EDGE, 8, true)
	v.draw_polyline(spring, AMBER, 3, true)
	v.draw_line(cap - Vector2(12, 0), cap + Vector2(12, 0), STEEL, 7, true)

static func table_impact(v: Control, contact: Vector2, strength: float, points: int) -> void:
	var spread := lerpf(82.0, 26.0, strength)
	for i in 6:
		var ray := Vector2.from_angle(i * TAU / 6.0 - 0.37)
		v.draw_line(contact + ray * spread, contact + ray * (spread + 18 * strength), Color(AMBER, strength), 4, true)
	text(v, "+%s" % formatted(points), contact + Vector2(0, lerpf(-79.0, -35.0, strength)),
		22, Color(WHITE, strength), HORIZONTAL_ALIGNMENT_CENTER, "title")

static func pop_bumper(v: Control, p: Vector2, impact: float, accent: Color) -> void:
	v.draw_circle(p + Vector2(0, 10), 66, INK)
	v.draw_circle(p, 67, EDGE)
	v.draw_circle(p, 59, INK)
	v.draw_circle(p, 49 - 7 * impact, PANEL.lerp(accent, impact * 0.72))
	v.draw_arc(p, 58, 0, TAU, 42, accent, 5 + 3 * impact, true)
	v.draw_arc(p, 39, PI * 0.17, PI * 1.72, 34, Color(accent, 0.48), 3, true)
	v.draw_circle(p, 8, accent)

static func flipper(v: Control, p: Vector2, rotation: float, left: bool, accent: Color) -> void:
	var tip := p + Vector2(-128 if left else 128, 0).rotated(rotation)
	v.draw_line(p + Vector2(0, 9), tip + Vector2(0, 9), INK, 35, true)
	v.draw_line(p, tip, accent, 29, true)
	v.draw_line(p, tip, WHITE, 12, true)
	v.draw_circle(p, 19, PANEL)
	v.draw_circle(p, 7, accent)

static func steel_ball(v: Control, p: Vector2, radius: float) -> void:
	v.draw_circle(p + Vector2(4, 9), radius + 5, Color(0, 0, 0, 0.61))
	v.draw_circle(p, radius, Color("374e60"))
	v.draw_circle(p + Vector2(-2, -3), radius * 0.86, Color("92adbf"))
	v.draw_arc(p, radius * 0.81, 3.55, 5.40, 22, WHITE, 3, true)
	v.draw_circle(p + Vector2(-radius * 0.31, -radius * 0.33), radius * 0.22, WHITE)

static func menu(v: Control) -> void:
	playfield(v, Loop.replay(fposmod(v.elapsed, Loop.BALL_LENGTH)))
	title(v, "MENU", Vector2(96, 318), 115, MINT)
	for i in v.MENU.size():
		var active: bool = v.focus_index == i
		var shift := 20.0 * (1.0 - ease_out(v.focus_elapsed / 0.20)) if active else 0.0
		var row := Rect2(100 + shift, 366 + i * 115, 865, 94)
		Scenery.faceplate(v, row, MINT if active else Color("23415c"), WHITE if active else EDGE)
		var label: String = v.MENU[i]
		text(v, label.to_upper(), row.position + Vector2(34, 61), 38, INK if active else WHITE,
			HORIZONTAL_ALIGNMENT_LEFT, "title")
		if label == "Mode":
			text(v, v.MODES[v.selected_mode].to_upper(), row.position + Vector2(754, 60),
				29, INK if active else MINT, HORIZONTAL_ALIGNMENT_RIGHT, "mono")
		if active:
			v.draw_polyline(PackedVector2Array([row.position + Vector2(804, 30), row.position + Vector2(825, 47),
				row.position + Vector2(804, 64)]), INK, 4, true)
	if v.start_requested:
		text(v, "START REQUESTED", Vector2(103, 862), 24, STEEL, HORIZONTAL_ALIGNMENT_LEFT, "mono")

static func choose_mode(v: Control) -> void:
	title(v, "SELECT MODE", Vector2(96, 286), 112, WHITE)
	for i: int in v.MODES.size():
		var focused: bool = v.mode_focus == i
		var drop := 12.0 * (1.0 - ease_out(v.focus_elapsed / 0.19)) if focused else 0.0
		var easy := i == 0
		var accent := MINT if easy else AMBER
		var card := Rect2(105, 430, 570, 270) if easy else Rect2(1245, 393, 570, 344)
		card.position.y += drop
		mode_plate(v, card, easy, accent if focused else PANEL, WHITE if focused else accent)
		var caption := INK if focused else accent
		var centre := card.get_center()
		text(v, v.MODES[i].to_upper(), centre + Vector2(0, 33), 101, caption,
			HORIZONTAL_ALIGNMENT_CENTER, "title")
		if v.selected_mode == i:
			text(v, "CURRENT MODE", centre + Vector2(0, 86), 26, caption,
				HORIZONTAL_ALIGNMENT_CENTER, "mono")
	var easy_focused: bool = v.mode_focus == 0
	var reach := lerpf(0.68, 1.0, ease_out(v.focus_elapsed / 0.18))
	var lean := (-0.055 if easy_focused else 0.055) * reach
	Scenery.mascot(v, Vector2(960, 543), 1.28, v.elapsed, "easy" if easy_focused else "hard",
		Vector2.ONE, lean, reach)

static func mode_plate(v: Control, card: Rect2, easy: bool, fill: Color, edge: Color) -> void:
	var outline := PackedVector2Array()
	if easy:
		var radius := 67.0
		var inset := card.grow(-radius)
		var corners := [Vector2(inset.end.x, inset.position.y), inset.end,
			Vector2(inset.position.x, inset.end.y), inset.position]
		for corner in 4:
			for step in 9:
				var angle := (corner - 1 + step / 8.0) * PI * 0.5
				outline.append(corners[corner] + Vector2.from_angle(angle) * radius)
	else:
		var a := card.position
		var b := card.end
		outline = PackedVector2Array([a + Vector2(105, 0), Vector2(b.x - 38, a.y), Vector2(b.x, a.y + 44),
			b - Vector2(75, 38), b - Vector2(124, 0), Vector2(a.x + 47, b.y),
			Vector2(a.x, b.y - 51), a + Vector2(62, 37)])
	var shadow := PackedVector2Array()
	for point in outline:
		shadow.append(point + Vector2(12, 16))
	v.draw_colored_polygon(shadow, Color(Scenery.SHADOW, 0.87))
	v.draw_colored_polygon(outline, fill)
	outline.append(outline[0])
	v.draw_polyline(outline, edge, 4, true)

static func high_scores(v: Control) -> void:
	var keys: Array = v.board_keys()
	var board: String = keys[v.board_index]
	title(v, "HIGH SCORES", Vector2(91, 280), 108)
	var heading: String = v.competition.left(42) if board == "competition" else v.BOARDS[board]
	text(v, heading.to_upper(), Vector2(1828, 278), 33, MINT, HORIZONTAL_ALIGNMENT_RIGHT, "mono")
	var rows: Variant = v.boards.get(board, [])
	if not rows is Array or rows.is_empty():
		v.draw_rect(Rect2(94, 344, 1732, 513), PANEL)
		text(v, "NO SCORES YET", Vector2(960, 604), 45, STEEL, HORIZONTAL_ALIGNMENT_CENTER, "mono")
		return
	var shown := mini(5, rows.size())
	for i in shown:
		var row: Variant = rows[i]
		if not row is Dictionary:
			continue
		var arrive := ease_out((maxf(v.focus_elapsed, 0.05) - i * 0.037) / 0.20)
		var rect := Rect2(94 + (1.0 - arrive) * 50, 344 + i * 104, 1699, 84)
		Scenery.faceplate(v, rect, Color("315671") if i == 0 else Color("242f56"), Scenery.SKY if i == 0 else EDGE, 17)
		text(v, "%02d" % int(row.get("rank", i + 1)), rect.position + Vector2(34, 61), 34, MINT, HORIZONTAL_ALIGNMENT_LEFT, "mono")
		var initials := str(row.get("initials", "")).strip_edges()
		var name := str(row.get("name", "")).strip_edges().left(30)
		text(v, initials if not initials.is_empty() else name, rect.position + Vector2(152, 63), 41, WHITE,
			HORIZONTAL_ALIGNMENT_LEFT, "title")
		text(v, formatted(int(row.get("score", 0))), rect.position + Vector2(1661, 59), 47, WHITE,
			HORIZONTAL_ALIGNMENT_RIGHT, "mono")

static func bonus(v: Control) -> void:
	var t: float = v.elapsed
	var enter := ease_out(t / 0.17)
	var exit := ease_out((t - 1.83) / 0.29)
	var reel := clampf((t - 0.16) / 0.49, 0.0, 1.0)
	var landed := 1.0 - ease_out((t - 0.65) / 0.23) if t >= 0.65 else 0.0
	var slide := Vector2(-340 * (1.0 - enter), (1.0 - enter) * 111 - exit * 920)
	var frame := Rect2(Vector2(128, 229) + slide, Vector2(1270, 560))
	Scenery.faceplate(v, frame.grow(10), Color("762f64"), AMBER, 43)
	Scenery.faceplate(v, frame, Color("322a53"), AMBER.lerp(WHITE, landed), 37)
	title(v, "BONUS", Vector2(229, 380) + slide, 124, AMBER)
	var slot := Rect2(Vector2(230, 419) + slide, Vector2(1064, 178))
	v.draw_rect(slot, INK)
	v.draw_rect(slot, EDGE, false, 3)
	var amount := grouped(str(roundi(int(v.state.bonus) * reel)).lpad(str(v.state.bonus).length(), "0"))
	var digits := (124 if amount.length() < 11 else 98) + roundi(landed * 9)
	var size: float = v.mono_font.get_string_size("0", HORIZONTAL_ALIGNMENT_LEFT, -1, digits).x
	var first: float = 762.0 - size * (amount.length() - 1) / 2.0
	for i in amount.length():
		var spin := sin(t * 49.0 + i * 0.64) * sin(reel * PI) * 13.0 if amount[i] != "," else 0.0
		text(v, amount[i], Vector2(first + i * size, 554 + spin) + slide, digits, MINT.lerp(WHITE, landed),
			HORIZONTAL_ALIGNMENT_CENTER, "mono")
	text(v, "×%d MULTIPLIER" % v.state.multiplier, Vector2(762, 693) + slide, 39, MINT, HORIZONTAL_ALIGNMENT_CENTER, "mono")
	for i in 13:
		var on := i < ceili(reel * 13.0)
		v.draw_rect(Rect2(Vector2(325 + i * 69, 739) + slide, Vector2(48, 9)), MINT if on else EDGE)

	var relay := Vector2(1603, 496) + Vector2(320 * exit, 0)
	Scenery.mascot(v, relay, 1.43, maxf(0.0, t - 0.06), "joy")
	for i in 5:
		var angle := -1.52 + i * 0.55
		var ray := Vector2.from_angle(angle)
		Scenery.flare(v, relay + ray * (205 + (1.0 - landed) * 125), 23 * landed, Color(AMBER, landed))

static func tilt(v: Control) -> void:
	var t: float = v.elapsed
	var clamp_in := ease_out(t / 0.12)
	var open := ease_out((t - 0.97) / 0.23)
	var kick := sin(t * 63) * 29 * (1.0 - ease_out(t / 0.24))
	var position := Vector2(123 + kick - (1.0 - clamp_in) * 1000 - open * 1280, 302)
	var frame := Rect2(position, Vector2(1140, 387))
	Scenery.faceplate(v, frame.grow(15), Color("7b4053"), AMBER, 49)
	Scenery.faceplate(v, frame, Color("3d233a"), RED, 39)
	for i in 5:
		var x := position.x + 829 + i * 44
		v.draw_line(Vector2(x, 352), Vector2(x - 123, 634), Color(RED, 0.23), 15, true)
	title(v, "TILT", position + Vector2(174, 268), 246, Color("ff9c74"))
	Scenery.mascot(v, Vector2(1538 + 440 * open, 485), 1.64, t, "alarm")

static func game_over(v: Control) -> void:
	const EXIT_DURATION := 0.28
	var t: float = v.elapsed
	var settle := ease_out((t - 0.16) / 0.17)
	var exit_start: float = v.DURATIONS["game_over"] - EXIT_DURATION
	var leave := ease_out((t - exit_start) / EXIT_DURATION)
	var drop := Vector2(0, leave * 950)
	var x := -295.0 * (1.0 - settle)
	Scenery.faceplate(v, Rect2(Vector2(83 + x, 305) + drop, Vector2(1249, 508)), Color("26254e"), Color("ccadf8"), 41)
	title(v, "GAME OVER", Vector2(140 + x, 483) + drop, 135, Color("e1befc"))
	text(v, formatted(int(v.state.score)), Vector2(143 + x, 686) + drop, 119, WHITE, HORIZONTAL_ALIGNMENT_LEFT, "mono")
	text(v, "FINAL SCORE", Vector2(150 + x, 761) + drop, 30, STEEL, HORIZONTAL_ALIGNMENT_LEFT, "mono")
	Scenery.mascot(v, Vector2(1573, 500) + drop, 1.20, t, "end")

static func game_started(v: Control, phase: float) -> void:
	var gaze := Vector2(-6.0 + 8.0 * sin(phase), 3.0 * cos(phase))
	var mascot_clock := 0.36 + 2.5 * (1.0 - cos(phase))
	var action: Dictionary = v.RelayActions.sample(v.elapsed, v.game_started_actions)
	var strength: float = action.get("strength", 0.0)
	var pose: String = action.pose if strength > 0.16 else "game_started"
	if strength > 0.0:
		gaze = gaze.lerp(action.gaze, strength)
		mascot_clock = lerpf(mascot_clock, 0.36 + float(action.age), strength)
	Scenery.mascot(v, Vector2(1468, 516), 1.60, mascot_clock, pose,
		Vector2.ONE, 0.0, strength, gaze)

	title(v, "GAME STARTED", Vector2(94, 281), 106, MINT)
	var frame := Rect2(98, 345, 950, 363)
	Scenery.faceplate(v, frame, Color("172745"), Scenery.SKY, 42)
	text(v, "SCORE", Vector2(153, 440), 32, Scenery.SKY, HORIZONTAL_ALIGNMENT_LEFT, "mono")
	var score := formatted(int(v.state.score))
	var score_size := mini(148, int(836.0 / float(v.mono_font.get_string_size(score, HORIZONTAL_ALIGNMENT_LEFT, -1, 148).x) * 148.0))
	text(v, score, Vector2(149, 603), score_size, WHITE, HORIZONTAL_ALIGNMENT_LEFT, "mono")
	Scenery.faceplate(v, Rect2(98, 743, 950, 102), PANEL, EDGE)
	var name := str(v.state.player_name).strip_edges().left(24).to_upper()
	var player_label := name if not name.is_empty() else "PLAYER %s" % v.state.player
	var player_size := mini(36, int(640.0 / float(v.title_font.get_string_size(player_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 36).x) * 36.0))
	text(v, player_label, Vector2(147, 806), player_size, WHITE, HORIZONTAL_ALIGNMENT_LEFT, "title")
	text(v, "BALL %s" % v.state.ball, Vector2(998, 806), 35, MINT, HORIZONTAL_ALIGNMENT_RIGHT, "mono")
