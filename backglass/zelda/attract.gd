extends RefCounted
## Time-based film editing. No timers or callbacks can outlive an interrupted shot.
const DURATION := 44.0
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

static func image_shot(v: Control, index: int, time: float, alpha: float) -> void:
	var shot: Array = SHOTS[index]
	var progress := clampf(time / float(shot[1]), 0, 1)
	progress = progress * progress * (3 - 2 * progress)
	if v.reduced_motion: progress = 0.5
	var zoom: float = lerpf(shot[6], shot[7], progress)
	var camera: Vector2 = shot[4].lerp(shot[5], progress)
	var dimensions := Vector2(1920, 1080) * zoom
	var rect := Rect2((Vector2(1920, 1080) - dimensions) * 0.5 + camera, dimensions)
	if v.backgrounds.has(shot[0]):
		v.draw_texture_rect(v.backgrounds[shot[0]], rect, false, Color(1, 1, 1, alpha))

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
		atmosphere(v, index, t)
	# A soft vignette holds captions over bright scenery without a UI card.
	for i in 15:
		v.draw_rect(Rect2(0, 650 + i * 15, 1920, 430 - i * 15), Color(0.005, 0.015, 0.01, 0.035))
	var opacity := minf(clampf((t - 0.5) / 0.8, 0, 1), clampf((length - t) / 0.6, 0, 1))
	var lift := 0.0 if v.reduced_motion else (1.0 - clampf((t - 0.5) / 1.2, 0, 1)) * 25
	if index == 4:
		# Three fragments travel inward and lock together over the altar.
		var approach: float = 1.0 if v.reduced_motion else v._ease_out((t - 0.5) / 2.0)
		for i in 3:
			var starts := [Vector2(230, 220), Vector2(1690, 220), Vector2(960, 920)]
			var ends := [Vector2(960, 365), Vector2(845, 565), Vector2(1075, 565)]
			var point: Vector2 = starts[i].lerp(ends[i], approach)
			v.draw_colored_polygon(PackedVector2Array([point + Vector2(0,-120), point + Vector2(105,60), point + Vector2(-105,60)]), Color(v.GOLD, opacity))
		v._text(SHOTS[index][2], Vector2(960, 770 + lift), 49, Color(v.CREAM, opacity), true, true)
	elif index == 5:
		var title_zoom := 1.0 if v.reduced_motion else lerpf(0.91, 1.0, v._ease_out(t / 3.0))
		v._stage(Vector2(960, 500), 0, title_zoom)
		v._text("THE LEGEND OF ZELDA", Vector2(0,-140), 30, Color(v.GOLD, opacity), true)
		v._text("THE HERO", Vector2(0,-25), 118, Color(v.CREAM, opacity), true, true)
		v._text("OF TIME", Vector2(0,100), 118, Color(v.CREAM, opacity), true, true)
		v.draw_line(Vector2(-290,145), Vector2(290,145), Color(v.GOLD, opacity), 2)
		v._text("A HYRULE PINBALL ADVENTURE", Vector2(0,202), 24, Color(v.GOLD, opacity), true)
		v._stage()
	elif index == 6:
		v._text(SHOTS[index][2], Vector2(960, 285), 64, Color(v.CREAM, opacity), true, true)
		v._text(SHOTS[index][3], Vector2(960, 345), 23, Color(v.GOLD, opacity), true)
		var rows: Array = v.records
		if v.preview: rows = [{"name":"LNK", "score":9248500}, {"name":"ZEL", "score":7812000}, {"name":"NAV", "score":6240000}]
		if rows.is_empty():
			v._text("Be the first to write your name in the chronicles.", Vector2(960, 560), 32, Color(v.CREAM, opacity), true)
		else:
			for i in mini(rows.size(), 3):
				v._text("%02d     %s" % [i + 1, rows[i].name], Vector2(530, 470 + i * 95), 38, Color(v.GOLD, opacity), false, true)
				v._text(v._number(rows[i].score), Vector2(1170, 470 + i * 95), 40, Color(v.CREAM, opacity), true)
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

static func atmosphere(v: Control, index: int, t: float) -> void:
	var time: float = v.elapsed
	# Low mist ribbons: two independently moving layers, with no full-screen flashing.
	for band in 3:
		var points := PackedVector2Array()
		var base := 650.0 + band * 65
		for x in range(-100, 2100, 100):
			points.append(Vector2(x, base + sin(x * 0.004 + time * 0.18 + band) * 40))
		points.append(Vector2(2100, 1080))
		points.append(Vector2(-100, 1080))
		v.draw_colored_polygon(points, Color(0.6, 0.75, 0.65, 0.025))
	var color := Color("e6ad65") if index == 3 else Color("d7e6ae")
	for i in 50:
		var x := fposmod(i * 193.7 + time * (13 + i % 6), 2020) - 50
		var y := fposmod(i * 117.3 - time * (10 + i % 9), 850) + 100
		var radius := 1.5 + i % 4
		v.draw_circle(Vector2(x,y), radius * 3, Color(color, 0.035))
		v.draw_circle(Vector2(x,y), radius, Color(color, 0.22 + sin(time + i) * 0.12))
	if index == 0 or index == 1:
		for i in 9:
			var point := Vector2(fposmod(i * 271 + time * 80, 2200) - 140, 180 + fposmod(i * 149 + time * 28, 700))
			var leaf := PackedVector2Array([point + Vector2(-26,0),point + Vector2(0,-9),point + Vector2(26,0),point + Vector2(0,9)])
			v.draw_colored_polygon(leaf, Color(0.10,0.23,0.13,0.45))
	if index == 3:
		# A restrained lightning silhouette, one brief appearance per shot.
		var strength := maxf(0, 1.0 - absf(t - 2.8) / 0.25)
		v.draw_polyline(PackedVector2Array([Vector2(1410,110),Vector2(1310,300),Vector2(1380,280),Vector2(1240,520)]), Color(0.8,0.75,1.0,strength * 0.65), 3, true)
