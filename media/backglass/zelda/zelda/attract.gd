extends RefCounted
## Time-based film editing. No timers or callbacks can outlive an interrupted shot.
const DURATION := 44.0
const Catalog = preload("res://zelda/catalog.gd")
# background, length, caption, subcaption, camera start/end, zoom start/end
const SHOTS = [
	["hyrule", 7.0, "Before the legend…", "THERE WAS A KINGDOM WORTH SAVING", Vector2(-90, 25), Vector2(75, -20), 1.18, 1.08],
	["map", 6.0, "Six paths. One destiny.", "FOREST  /  FIRE  /  WATER  /  SPIRIT", Vector2(100, 80), Vector2(-80, -60), 1.14, 1.24],
	["sword", 7.0, "Courage waits to awaken.", "IN THE TEMPLE OF TIME", Vector2(50, 10), Vector2(-40, -30), 1.06, 1.18],
	["dark", 6.0, "But the shadows are rising.", "A KINGDOM CANNOT SAVE ITSELF", Vector2(-100, -15), Vector2(50, 20), 1.12, 1.23],
	["temple", 5.0, "POWER. WISDOM. COURAGE.", "THREE FORCES. ONE HERO.", Vector2(0, 35), Vector2(0, -30), 1.25, 1.05],
	["hyrule", 8.0, "THE HERO OF TIME", "A HYRULE PINBALL ADVENTURE", Vector2(45, 20), Vector2(-25, 0), 1.13, 1.04],
	["temple", 5.0, "YOUR LEGEND STARTS HERE", "THE CHRONICLES OF HYRULE", Vector2.ZERO, Vector2(0, -20), 1.06, 1.10],
]

static func shot_at(time: float) -> Dictionary:
	var local := fposmod(time, DURATION)
	for i in SHOTS.size():
		if local < float(SHOTS[i][1]):
			return {"index": i, "time": local, "length": float(SHOTS[i][1])}
		local -= float(SHOTS[i][1])
	return {"index": 0, "time": 0.0, "length": 7.0}

static func camera_rect(v: Control, index: int, time: float) -> Rect2:
	var shot: Array = SHOTS[index]
	var progress := clampf(time / float(shot[1]), 0, 1)
	progress = progress * progress * (3 - 2 * progress)
	if v.reduced_motion: progress = 0.5
	var zoom: float = lerpf(shot[6], shot[7], progress) + (0.045 * (1.0 - v._ease_out(time / 1.2)) if not v.reduced_motion else 0.0)
	var camera: Vector2 = shot[4].lerp(shot[5], progress)
	var dimensions := Vector2(1920, 1080) * zoom
	return Rect2((Vector2(1920, 1080) - dimensions) * 0.5 + camera, dimensions)

static func image_shot(v: Control, index: int, time: float, alpha: float) -> void:
	var image: String = SHOTS[index][0]
	if v.backgrounds.has(image):
		v.draw_texture_rect(v.backgrounds[image], camera_rect(v, index, time), false, Color(1, 1, 1, alpha))

static func render(v: Control) -> void:
	var shot := shot_at(v.elapsed)
	var index: int = shot.index
	var t: float = shot.time
	var length: float = shot.length
	var transition := clampf(t / 0.9, 0, 1)
	if index > 0 and transition < 1:
		image_shot(v, index - 1, SHOTS[index - 1][1], 1.0)
	image_shot(v, index, t, transition if index > 0 else 1.0)
	v.draw_rect(Rect2(0, 0, 1920, 1080), Color(0.015, 0.035, 0.03, 0.17))
	# Separate foreground layers travel faster than the camera to create depth.
	if not v.reduced_motion:
		atmosphere(v, index)
		shot_effects(v, index, t, transition)
	# A soft vignette holds captions over bright scenery without a UI card.
	for i in 15:
		v.draw_rect(Rect2(0, 650 + i * 15, 1920, 430 - i * 15), Color(0.005, 0.015, 0.01, 0.035))
	var opacity := minf(clampf((t - 0.5) / 0.8, 0, 1), clampf((length - t) / 0.6, 0, 1))
	var lift := 0.0 if v.reduced_motion else (1.0 - clampf((t - 0.38) / 0.72, 0, 1)) * 66
	if index == 4:
		# The three fragments accelerate along different paths and hit one mark together.
		var approach: float = 1.0 if v.reduced_motion else pow(clampf((t - 0.35) / 1.22, 0.0, 1.0), 2.0)
		var impact: float = 0.0 if v.reduced_motion or t < 1.57 else v._ease_out((t - 1.57) / 0.75)
		var centre := Vector2(960, 478)
		v.draw_arc(centre, 244, 0, TAU, 96, Color(v.GOLD, opacity * 0.41), 2, true)
		if impact > 0.0 and impact < 1.0:
			v.draw_arc(centre, 227 + impact * 230, 0, TAU, 96, Color(v.GOLD, 1.0 - impact), 4, true)
			v._draw_impact(centre, impact, v.GOLD, Vector2(226, 192))
		var starts := [Vector2(210, 190), Vector2(340, 820), Vector2(1680, 740)]
		var ends := [Vector2(960, 365), Vector2(852, 553), Vector2(1068, 553)]
		for i in 3:
			var point: Vector2 = starts[i].lerp(ends[i], approach)
			var angle := (1.0 - approach) * (i - 1) * 1.6
			var points := PackedVector2Array()
			for vertex in [Vector2(0, -120), Vector2(105, 62), Vector2(-105, 62)]:
				points.append(point + vertex.rotated(angle))
			v.draw_colored_polygon(points, Color(v.GOLD, opacity))
			points.append(points[0])
			v.draw_polyline(points, Color(v.CREAM, opacity * 0.85), 3, true)
		v._text(SHOTS[index][2], Vector2(960, 770 + lift), 49, Color(v.CREAM, opacity), true, true)
	elif index == 5:
		var title_zoom := 1.0 if v.reduced_motion else lerpf(0.78, 1.0, v._ease_out(t / 0.92))
		v._stage(Vector2(960, 500), 0, title_zoom)
		v._text("THE LEGEND OF ZELDA", Vector2(0,-140), 30, Color(v.GOLD, opacity), true)
		v._text("THE HERO", Vector2(-lift,-25), 118, Color(v.CREAM, opacity), true, true)
		v._text("OF TIME", Vector2(lift,100), 118, Color(v.CREAM, opacity), true, true)
		var rule: float = 290.0 if v.reduced_motion else 290.0 * v._ease_out((t - 0.55) / 0.65)
		v.draw_line(Vector2(-rule, 145), Vector2(rule, 145), Color(v.GOLD, opacity), 2)
		v._text("A HYRULE PINBALL ADVENTURE", Vector2(0,202), 24, Color(v.GOLD, opacity), true)
		v._stage()
	elif index == 6:
		var competition: bool = not v.preview and not v.competition_title.is_empty()
		var title: String = v.competition_title if competition else SHOTS[index][2]
		v._text(title, Vector2(960, 285), 42 if competition else 64, Color(v.CREAM, opacity), true, true)
		v._text("COMPETITION LEADERS" if competition else SHOTS[index][3], Vector2(960, 345), 23, Color(v.GOLD, opacity), true)
		var rows: Array = v.leaderboards.get("competition", []) if competition else v.records
		if v.preview: rows = [{"initials":"LNK", "score":9248500}, {"initials":"ZEL", "score":7812000}, {"initials":"NAV", "score":6240000}]
		if rows.is_empty():
			v._text("Be the first to write your name in the chronicles.", Vector2(960, 560), 32, Color(v.CREAM, opacity), true)
		else:
			for i in mini(rows.size(), 3):
				var row: float = 1.0 if v.reduced_motion else v._ease_out((t - 0.52 - i * 0.16) / 0.42)
				var y := 470.0 + i * 95 + (1.0 - row) * 28
				var alpha := opacity * row
				v.draw_rect(Rect2(465, y - 47, 990, 69), Color(0.02, 0.08, 0.06, alpha * 0.74))
				v.draw_line(Vector2(465, y + 22), Vector2(1455, y + 22), Color(v.GOLD, alpha * 0.48), 2)
				v._text("%02d     %s" % [i + 1, rows[i].initials], Vector2(530, y), 38, Color(v.GOLD, alpha), false, true)
				v._text(v._number(int(rows[i].score)), Vector2(1170, y), 40, Color(v.CREAM, alpha), true)
		v._text("THE NEXT CHAPTER IS YOURS", Vector2(960, 790), 28, Color(v.GOLD, opacity), true)
	elif index == 2:
		v._text("THE MASTER SWORD", Vector2(1370, 410 + lift), 23, Color(v.GOLD, opacity), true)
		v._text("Courage waits", Vector2(1370, 500 + lift), 65, Color(v.CREAM, opacity), true, true)
		v._text("to awaken.", Vector2(1370, 580 + lift), 65, Color(v.CREAM, opacity), true, true)
	else:
		v._text(SHOTS[index][2], Vector2(960, 770 + lift), 62, Color(v.CREAM, opacity), true, true)
	if index not in [2, 5, 6]:
		v._text(SHOTS[index][3], Vector2(960, 825 + lift), 22, Color(v.GOLD, opacity), true)
	# Film bars are drawn last. Controls remain outside the cinematic picture.
	v.draw_rect(Rect2(0, 0, 1920, 110), Color.BLACK)
	v.draw_rect(Rect2(0, 910, 1920, 170), Color.BLACK)
	v._text("HYRULE  /  THE HERO OF TIME", Vector2(80, 65), 18, v.MUTED)
	v._text("PRESS SELECT  •  YOUR ADVENTURE AWAITS", Vector2(960, 949), 23, v.GOLD, true)
	for i in SHOTS.size():
		v.draw_line(Vector2(1550 + i * 36, 60), Vector2(1574 + i * 36, 60), v.GOLD if i == index else Color("34483e"), 3)
	# Fade the opening and loop seam; Start never waits for this fade to end.
	var fade := maxf(1.0 - clampf(v.elapsed / 1.2, 0, 1), clampf((fposmod(v.elapsed, DURATION) - 43.3) / 0.7, 0, 1))
	v.draw_rect(Rect2(0, 110, 1920, 800), Color(0, 0, 0, fade))

static func atmosphere(v: Control, index: int) -> void:
	var time: float = v.elapsed
	# Low mist ribbons: two independently moving layers, with no full-screen flashing.
	for band in 4:
		var points := PackedVector2Array()
		var base := 505.0 + band * 99
		for x in range(-100, 2100, 100):
			points.append(Vector2(x, base + sin(x * 0.004 + time * (0.36 + band * 0.16) + band) * 47))
		points.append(Vector2(2100, 1080))
		points.append(Vector2(-100, 1080))
		v.draw_colored_polygon(points, Color(0.6, 0.75, 0.65, 0.033))
	var color := Color("e6ad65") if index == 3 else Color("d7e6ae")
	for i in 50:
		var x := fposmod(i * 193.7 + time * (26 + i % 11), 2020) - 50
		var y := fposmod(i * 117.3 - time * (17 + i % 9), 850) + 100
		var radius := 1.5 + i % 4
		v.draw_circle(Vector2(x,y), radius * 3, Color(color, 0.035))
		v.draw_circle(Vector2(x,y), radius, Color(color, 0.22 + sin(time + i) * 0.12))
	if index == 0 or index == 1:
		for i in 9:
			var point := Vector2(fposmod(i * 271 + time * 80, 2200) - 140, 180 + fposmod(i * 149 + time * 28, 700))
			var leaf := PackedVector2Array()
			for vertex in [Vector2(-34, 0), Vector2(0, -10), Vector2(29, 0), Vector2(0, 10)]:
				leaf.append(point + vertex.rotated(time * 1.45 + i))
			v.draw_colored_polygon(leaf, Color(0.10,0.23,0.13,0.45))

static func shot_effects(v: Control, index: int, t: float, opacity: float) -> void:
	match index:
		0, 5:
			# Widely spaced shafts drift across the valley and frame the title.
			for i in 6:
				var x := 210.0 + i * 310 + sin(t * 0.8 + i) * 58
				var points := PackedVector2Array([Vector2(x, 110), Vector2(x + 36, 110), Vector2(x - 330, 890), Vector2(x - 455, 890)])
				v.draw_colored_polygon(points, Color(v.GOLD, opacity * (0.035 + i % 3 * 0.019)))
		1:
			# Connect the six stops in order, with a moving head and a fading route behind it.
			var travel := clampf((t - 0.48) / 3.1, 0.0, 1.0) * (Catalog.QUESTS.size() - 1)
			var frame := camera_rect(v, index, t)
			var map_scale := frame.size / Vector2(1920, 1080)
			for i in Catalog.QUESTS.size():
				var point: Vector2 = frame.position + Catalog.QUESTS[i].point * map_scale
				if i > 0:
					var previous: Vector2 = frame.position + Catalog.QUESTS[i - 1].point * map_scale
					var leg := clampf(travel - i + 1, 0.0, 1.0)
					if leg > 0.0:
						var head := previous.lerp(point, leg)
						v.draw_line(previous, head, Color(v.INK, opacity * 0.65), 8, true)
						v.draw_line(previous, head, Color(v.GOLD, opacity * 0.85), 3, true)
						if leg < 1.0: v.draw_circle(head, 7, Color(v.CREAM, opacity))
				if travel >= i:
					v.draw_circle(point, 18, Color(v.INK, opacity * 0.8))
					v.draw_arc(point, 20, 0, TAU, 32, Color(v.GOLD, opacity * 0.85), 2, true)
					v.draw_circle(point, 8, Color(Color(Catalog.QUESTS[i].color), opacity))
		2:
			var reveal := clampf((t - 0.75) / 1.7, 0.0, 1.0)
			var centre := Vector2(325, 490)
			if reveal > 0.0:
				for i in 3:
					var radius := 116.0 + i * 39
					var angle := t * (0.44 if i % 2 == 0 else -0.38) + i * 1.6
					v.draw_arc(centre, radius, angle, angle + TAU * 0.71 * reveal, 64, Color(v.GOLD, opacity * 0.36), 2, true)
					var point := centre + Vector2.from_angle(angle) * radius
					v.draw_circle(point, 5, Color(v.CREAM, opacity * reveal))
		3:
			# A single distant fork silhouettes the storm without a full-frame flash.
			var strength := maxf(0, 1.0 - absf(t - 2.05) / 0.31) * opacity
			if strength > 0.0:
				var fork := PackedVector2Array([Vector2(1410, 110), Vector2(1290, 287), Vector2(1360, 263), Vector2(1210, 510)])
				v.draw_polyline(fork, Color(0.58, 0.41, 0.77, strength * 0.32), 18, true)
				v.draw_polyline(fork, Color(0.88, 0.78, 1.0, strength * 0.88), 3, true)
				v.draw_polyline(PackedVector2Array([Vector2(1290, 287), Vector2(1225, 306), Vector2(1160, 419)]), Color(0.88, 0.78, 1.0, strength * 0.59), 2, true)
