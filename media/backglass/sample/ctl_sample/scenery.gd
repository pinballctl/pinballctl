extends RefCounted
## Original vector scenery and Relay, the pinball-headed cabinet host.

const Relay := preload("res://ctl_sample/relay.gd")

const SHADOW := Color("10152b")
const SKY := Color("77d6f9")

static func backdrop(v: Control, scene: String, time: float, accent: Color, base: Color) -> void:
	v.draw_rect(Rect2(0, 0, 1920, 1080), base)
	match scene:
		"attract": attract_rays(v, time, accent, base)
		"menu": menu_rays(v, time, accent, base)
		"mode": mode_rays(v, time, accent, base)
		"high_scores": score_rays(v, time, accent, base)
		"tilt": shock_arcs(v, time, accent, base)
		"bonus": bonus_rays(v, time, accent, base)
		"game_over": spiral(v, time, accent, base)
		"game_started": playfield_rays(v, time, accent, base)
	stars(v, time, accent, 8 if scene == "high_scores" else 14)

static func attract_rays(v: Control, time: float, accent: Color, base: Color) -> void:
	# The wide rays and the nearer arc strokes drift at different speeds.
	var vanishing := Vector2(1340 + sin(time * 0.15) * 138, 468 + cos(time * 0.17) * 76)
	for i in 9:
		var angle := TAU * i / 9.0 + sin(time * 0.11) * 0.20
		var wide := 0.19 + (i % 3) * 0.095
		var inner := Vector2.from_angle(angle + wide * 0.44) * 88.0
		v.draw_colored_polygon(PackedVector2Array([
			vanishing + inner, vanishing + Vector2.from_angle(angle) * 2550,
			vanishing + Vector2.from_angle(angle + wide) * 2550,
		]), base.lerp(accent, 0.07 + i % 3 * 0.025))
	var anchor := Vector2(1280 + sin(time * 0.26) * 114, 500 + cos(time * 0.31) * 52)
	for band in 4:
		var radius := 505.0 + band * 97
		var swing := sin(time * 0.35 + band * 0.66) * 0.26 + band * 0.34
		var line_color := base.lerp(accent, 0.23 - band * 0.032)
		v.draw_arc(anchor, radius, 1.46 + swing, 2.86 + swing, 96, line_color, 5.5 - band * 0.6, true)
		v.draw_arc(anchor, radius, -1.98 + swing, -0.80 + swing, 80, base.lerp(accent, 0.14), 2.5, true)

static func spiral(v: Control, time: float, accent: Color, base: Color) -> void:
	var turn := time * 0.072
	# Keep the hub in Relay's part of the composition, clear of the score plate.
	var hub := Vector2(1530 + sin(turn) * 105.0, 485 + cos(turn) * 50.0)
	for band in 10:
		var angle := TAU * band / 10.0 + turn
		var inner := PackedVector2Array()
		var outer := PackedVector2Array()
		for step in 25:
			var t := step / 24.0
			var radius := lerpf(38.0, 2130.0, t)
			var curl := angle + 1.44 * pow(t, 0.58)
			inner.append(hub + Vector2.from_angle(curl) * radius)
			outer.append(hub + Vector2.from_angle(curl + lerpf(0.10, 0.40, t)) * radius)
		outer.reverse()
		var tint := base.lerp(accent, 0.095 + (band % 3) * 0.026)
		v.draw_colored_polygon(inner + outer, tint)
		if band % 2 == 0:
			v.draw_polyline(inner, base.lerp(accent, 0.17), 3.0, true)

static func ray(v: Control, hub: Vector2, angle: float, spread: float, length: float, tint: Color) -> void:
	v.draw_colored_polygon(PackedVector2Array([
		hub,
		hub + Vector2.from_angle(angle) * length,
		hub + Vector2.from_angle(angle + spread) * length,
	]), tint)

static func menu_rays(v: Control, time: float, accent: Color, base: Color) -> void:
	# Fan the rays out from below the cabinet artwork.
	var hub := Vector2(1520 + sin(time * 0.49) * 46.0, 1060)
	for band in 8:
		var angle := -PI + 0.10 + band * 0.37 + sin(time * 0.7) * 0.09
		var glow := 0.5 + 0.5 * sin(time * 2.1 - band * 0.8)
		ray(v, hub, angle, 0.15 + (band % 3) * 0.028, 2440, base.lerp(accent, 0.075 + 0.08 * glow))
		if band % 2 == 0:
			var direction := Vector2.from_angle(angle + 0.05)
			var start := 100.0 + fposmod(time * 225.0 + band * 115.0, 1650.0)
			var fade := sin(PI * (start - 100.0) / 1650.0)
			v.draw_line(hub + direction * start, hub + direction * (start + 115.0),
				Color(accent, fade * 0.37), 5.0, true)

static func mode_rays(v: Control, time: float, accent: Color, base: Color) -> void:
	var warm := Color("ffbd83")
	var swing := sin(time * 1.2) * 0.12
	# Cool rays bend outward. Warm rays stay angular on the opposite side.
	for band in 5:
		var hub := Vector2(916, 580)
		var points := PackedVector2Array()
		var far_edge := PackedVector2Array()
		for step in 17:
			var distance := 155.0 + step * 108.0
			var curve := 2.26 + band * 0.38 + swing - step * 0.019
			points.append(hub + Vector2.from_angle(curve) * distance)
			far_edge.append(hub + Vector2.from_angle(curve + 0.18) * distance)
		far_edge.reverse()
		v.draw_colored_polygon(points + far_edge, base.lerp(accent, 0.11 + (band % 2) * 0.06))
		v.draw_polyline(points, base.lerp(accent, 0.24), 3.0, true)
		var angle := -0.96 + band * 0.39 - swing
		var edge := Vector2.from_angle(angle) * 1900.0
		var tip := Vector2.from_angle(angle + 0.19) * 1900.0
		v.draw_colored_polygon(PackedVector2Array([
			hub + Vector2.from_angle(angle) * 114.0,
			hub + edge,
			hub + tip,
			hub + Vector2.from_angle(angle + 0.19) * 236.0,
		]), base.lerp(warm, 0.12 + (band % 2) * 0.064))

static func score_rays(v: Control, time: float, accent: Color, base: Color) -> void:
	# Low, lateral perspective keeps the leaderboard rows clear.
	var hub := Vector2(2010, 460 + sin(time * 0.65) * 63.0)
	for band in 9:
		var left_y := -250.0 + band * 192.0
		var pulse := 0.5 + 0.5 * sin(time * 1.25 - band * 0.58)
		var near := Vector2(-24, left_y)
		v.draw_colored_polygon(PackedVector2Array([
			hub, near, near + Vector2(0, 54 + 32 * pulse),
		]), base.lerp(accent, 0.061 + 0.063 * pulse))
		if band % 2 == 0:
			var sweep := 0.5 + 0.42 * sin(time * 1.31 + band * 0.55)
			var end := minf(sweep + 0.22, 1.0)
			v.draw_line(hub.lerp(near, sweep), hub.lerp(near, end), base.lerp(accent, 0.23), 4.0, true)

static func shock_arcs(v: Control, time: float, accent: Color, base: Color) -> void:
	var impulse := 1.0 - smoothstep(0.0, 0.31, time)
	var hub := Vector2(1500 + 34.0 * impulse, 525 - 31.0 * impulse)
	for band in 7:
		var angle := band * TAU / 7.0 + 0.11 - 0.17 * impulse
		ray(v, hub, angle, 0.21 + 0.09 * impulse, 2200,
			base.lerp(accent, 0.077 + (band % 2) * 0.025 + 0.07 * impulse))
	for band in 5:
		var radius := 243.0 + band * 112.0 + time * 125.0
		var angle := PI * (0.69 + band * 0.075) + 0.24 * impulse
		var tint := base.lerp(accent, 0.23 - band * 0.021 + 0.09 * impulse)
		v.draw_arc(hub, radius, angle, angle + PI * 0.83, 100, tint, 9.0 if band % 2 == 0 else 4.0, true)
		v.draw_arc(hub, radius, angle - PI * 0.87, angle - PI * 0.36, 72, tint, 5.0, true)
	# A broken lightning stroke travels out between the arc bands.
	var bolt := PackedVector2Array()
	for joint in 6:
		var x := 1275.0 + joint * 127.0 + time * 84.0
		var y := 245.0 - joint * 20.0 + (joint % 2) * (65.0 + 20.0 * impulse)
		bolt.append(Vector2(x, y))
	v.draw_polyline(bolt, Color(accent, 0.26 + 0.30 * impulse), 7.0, true)

static func bonus_rays(v: Control, time: float, accent: Color, base: Color) -> void:
	var rise := 1.0 - pow(1.0 - clampf(time / 0.78, 0.0, 1.0), 3.0)
	var hub := Vector2(940, 1125 - rise * 180.0)
	for band in 9:
		var angle := -PI + 0.21 + band * 0.32
		var arrival := smoothstep(0.0, 0.23, time - absf(band - 4.0) * 0.043)
		var spread := lerpf(0.055, 0.24, arrival)
		ray(v, hub, angle, spread, 2220, base.lerp(accent, 0.10 + 0.09 * arrival - rise * 0.04))
		if band % 2 == 1:
			var direction := Vector2.from_angle(angle + spread * 0.39)
			var distance := 159.0 + time * (402.0 + band * 23.0)
			var fade := sin(PI * clampf(time / 1.8, 0.0, 1.0))
			v.draw_line(hub + direction * distance, hub + direction * (distance + 125),
				Color(accent, 0.45 * fade), 8.0, true)

static func playfield_rays(v: Control, time: float, accent: Color, base: Color) -> void:
	# Long tapered lanes sweep diagonally behind the live score.
	for lane in range(-1, 7):
		var wave := sin(time * 0.77 - lane * 0.80)
		var y := lane * 204.0 + wave * 46.0
		var width := 67.0 + 23.0 * wave
		v.draw_colored_polygon(PackedVector2Array([
			Vector2(-32, y + 695), Vector2(1952, y - 162),
			Vector2(1952, y - 162 + width), Vector2(-32, y + 737),
		]), base.lerp(accent, 0.091 + 0.044 * wave))
		var from := Vector2(-28, y + 699)
		var to := Vector2(1948, y - 157)
		var progress := 0.5 + 0.36 * sin(time * 0.93 - lane * 0.72)
		v.draw_line(from.lerp(to, progress), from.lerp(to, progress + 0.12),
			base.lerp(accent, 0.22), 6.0, true)

static func stars(v: Control, time: float, accent: Color, count: int) -> void:
	for i in count:
		var point := Vector2(fposmod(i * 419.0 + time * (21 + i % 5 * 9), 2016) - 48,
			126 + fposmod(i * 263.0, 833.0) + sin(time * 0.65 + i) * (8 + i % 4 * 5))
		var size := 6.0 + (i % 4) * 3.0
		var fade := 0.5 + 0.5 * cos(time * (0.92 + i % 4 * 0.09) + i * 0.79)
		var light := lerpf(0.30, 0.62, fade)
		flare(v, point, size, Color(accent, light))

static func flare(v: Control, p: Vector2, radius: float, tint: Color) -> void:
	if radius <= 0.25 or tint.a <= 0.0:
		return
	v.draw_colored_polygon(PackedVector2Array([
		p + Vector2(0, -radius * 1.5), p + Vector2(radius * 0.22, -radius * 0.25),
		p + Vector2(radius, 0), p + Vector2(radius * 0.22, radius * 0.25),
		p + Vector2(0, radius * 1.5), p + Vector2(-radius * 0.22, radius * 0.25),
		p + Vector2(-radius, 0), p + Vector2(-radius * 0.22, -radius * 0.25),
	]), tint)

static func faceplate(v: Control, rect: Rect2, tint: Color, trim: Color, cut := 24.0) -> void:
	var a := rect.position
	var b := rect.end
	var outline := PackedVector2Array([
		Vector2(a.x + cut, a.y), Vector2(b.x, a.y), Vector2(b.x, b.y - cut),
		Vector2(b.x - cut, b.y), Vector2(a.x, b.y), Vector2(a.x, a.y + cut),
	])
	var shadow := PackedVector2Array()
	for p in outline:
		shadow.append(p + Vector2(12, 15))
	v.draw_colored_polygon(shadow, Color(SHADOW, 0.87))
	v.draw_colored_polygon(outline, tint)
	outline.append(outline[0])
	v.draw_polyline(outline, trim, 3, true)

static func mascot(v: Control, at: Vector2, scale: float, time: float, pose: String,
		stretch := Vector2.ONE, lean := 0.0, gesture := 1.0, gaze := Vector2.ZERO) -> void:
	Relay.draw(v, at, scale, time, pose, stretch, lean, gesture, gaze)
