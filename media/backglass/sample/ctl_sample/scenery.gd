extends RefCounted
## Original vector scenery and Relay, the pinball-headed cabinet host.

const Relay := preload("res://ctl_sample/relay.gd")

const SHADOW := Color("10152b")
const SKY := Color("77d6f9")

static func backdrop(v: Control, time: float, accent: Color, base: Color) -> void:
	v.draw_rect(Rect2(0, 0, 1920, 1080), base)
	# The wide rays drift as solid silhouettes. The nearer line work moves
	# on a different beat so the layers stay legible behind the cue plates.
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
	for i in 14:
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
