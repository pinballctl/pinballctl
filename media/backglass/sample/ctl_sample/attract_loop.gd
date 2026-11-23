extends RefCounted
## The attract demo is an authored replay. These contacts drive the same drawing
## as the assembly without touching text tokens, the game score or live rules.

const DURATION := 38.0
const BUILD_START := 5.0
const PLAY_START := 15.0
const OUTRO_START := 35.0
const BALL_LENGTH := 5.5
const REST := Vector2(1740, 818)
const TARGETS := [Vector2(1390, 607), Vector2(1450, 607), Vector2(1510, 607)]
const TARGET_START := 5.2
# Contacts are [time, position, animated part, points, callout, optional Relay pose].
# Parts 0–2 are the bumpers, 3–4 the flippers, and 5–7 the drop targets.
const PLAYS := [
	[
		[0.0, REST], [0.56, REST], [1.05, Vector2(1740, 287)], [1.28, Vector2(1577, 211)],
		[1.50, Vector2(1472, 267), 0, 1000, "POP BUMPER"],
		[1.68, Vector2(1609, 406), 1, 1500, "POP BUMPER", "bumper"],
		[1.91, Vector2(1375, 454), 2, 1000, "POP BUMPER"],
		[2.17, Vector2(1198, 632)], [2.41, TARGETS[0] + Vector2(0, 33), 5, 3000, "DROP TARGET", "proud"],
		[2.68, Vector2(1387, 787), 3, 2500, "FLIPPER SHOT"],
		[3.18, Vector2(1598, 419), 1, 1500, "POP BUMPER"], [3.50, Vector2(1692, 624)],
		[4.19, Vector2(1501, 803), 4, 2500, "FLIPPER SHOT", "pump"], [4.51, Vector2(1284, 655)],
		[4.88, Vector2(1430, 850)], [5.16, Vector2(1441, 931), -1, 0, "BALL DRAINED"],
	],
	[
		[0.0, REST], [0.44, REST], [0.94, Vector2(1740, 276)], [1.17, Vector2(1550, 215)],
		[1.42, Vector2(1352, 420), 2, 1200, "POP BUMPER"],
		[1.75, Vector2(1496, 382), 0, 1600, "POP BUMPER", "shrug"], [2.10, Vector2(1685, 374)],
		[2.32, Vector2(1658, 399), 1, 1800, "POP BUMPER"],
		[2.59, TARGETS[1] + Vector2(0, 33), 6, 4000, "DROP TARGET"],
		[2.89, Vector2(1506, 786), 4, 4500, "FLIPPER SHOT", "present"], [3.33, Vector2(1207, 601)],
		[3.72, Vector2(1327, 539), 2, 2400, "POP BUMPER"], [4.22, Vector2(1587, 668)],
		[4.63, Vector2(1443, 854)], [5.10, Vector2(1440, 931), -1, 0, "BALL DRAINED"],
	],
	[
		[0.0, REST], [0.42, REST], [0.84, Vector2(1740, 272)], [1.06, Vector2(1562, 209)],
		[1.24, Vector2(1481, 270), 0, 2000, "POP BUMPER"],
		[1.45, Vector2(1604, 415), 1, 2000, "POP BUMPER"],
		[1.64, Vector2(1379, 450), 2, 2000, "POP BUMPER"], [2.09, Vector2(1206, 619)],
		[2.68, Vector2(1374, 781), 3, 7000, "FLIPPER SHOT"],
		[2.97, TARGETS[2] + Vector2(0, 33), 7, 6000, "DROP TARGET", "grin"],
		[3.37, Vector2(1605, 488), 1, 3000, "POP BUMPER"], [3.75, Vector2(1681, 696)],
		[4.01, Vector2(1505, 794), 4, 8000, "FLIPPER SHOT", "cheer"], [4.37, Vector2(1342, 526), 2, 5000, "POP BUMPER"],
		[4.69, Vector2(1170, 647)], [5.08, Vector2(1436, 911), -1, 0, "BALL DRAINED"],
	],
]
const PART_NAMES := ["CABINET", "LANES & RAILS", "POP BUMPERS", "DROP TARGETS", "FLIPPERS", "PLUNGER & BALL"]
const PART_TIMES := [0.0, 1.6, 3.4, TARGET_START, 6.5, 8.0]

static func part_index(time: float) -> int:
	for i in range(PART_TIMES.size() - 1, 0, -1):
		if time >= PART_TIMES[i]:
			return i
	return 0

static func phase(time: float) -> String:
	if time < BUILD_START:
		return "opening"
	if time < PLAY_START:
		return "build"
	if time < OUTRO_START:
		return "play"
	return "outro"

static func replay_time(elapsed: float) -> float:
	return clampf(inverse_lerp(PLAY_START, OUTRO_START, elapsed), 0.0, 1.0) * BALL_LENGTH * PLAYS.size()

static func replay(time: float) -> Dictionary:
	var ball := mini(floori(maxf(0.0, time) / BALL_LENGTH), PLAYS.size() - 1)
	var local := maxf(0.0, time - ball * BALL_LENGTH)
	var route: Array = PLAYS[ball]
	var score := 0
	for i in ball:
		for step in PLAYS[i]:
			if step.size() > 3:
				score += int(step[3])
	var hits := [0.0, 0.0, 0.0, 0.0, 0.0]
	var targets_down := [false, false, false]
	var message := "SHOOT AGAIN" if ball > 0 else "BALL LAUNCH"
	var message_at := 0.0
	var points := 0
	var reaction := ""
	var reaction_at := 0.0
	var message_hold := "BALL LAUNCH"
	for step in route:
		var passed: float = local - float(step[0])
		if step.size() <= 3 or passed < 0.0:
			continue
		var part: int = step[2]
		score += int(step[3])
		if part >= 5:
			targets_down[part - 5] = true
		elif part >= 0:
			hits[part] = maxf(0.0, 1.0 - passed / (0.23 if part >= 3 else 0.17))
		message = step[4]
		message_at = step[0]
		points = step[3]
		if step.size() > 5:
			reaction = step[5]
			reaction_at = step[0]
	if local >= 0.38 and local - message_at < 0.92:
		message_hold = message
	elif local - message_at >= 0.92:
		message_hold = "BALL IN PLAY"
	var release: float = route[1][0]
	var pull := smoothstep(0.0, release, local) * (1.0 - smoothstep(release, release + 0.09, local))
	var impact := 1.0 - smoothstep(0.0, 0.58, local - message_at) if points > 0 else 0.0
	var reaction_weight := 1.0 - smoothstep(0.0, 0.58, local - reaction_at) if not reaction.is_empty() else 0.0
	var contact: Vector2 = position_at(route, message_at)
	var since_drain := local - float(route[-1][0])
	return {"ball": ball + 1, "ball_age": local, "score": score, "hits": hits, "targets_down": targets_down, "message": message_hold,
		"point": position_at(route, local) + Vector2(0, pull * 13.0),
		"tail": position_at(route, maxf(0.0, local - 0.055)),
		"impact": impact, "contact": contact, "points": points,
		"reaction": reaction, "reaction_weight": reaction_weight,
		"plunger": pull, "launching": local <= release,
		"drained": since_drain >= 0.0, "drain_progress": smoothstep(0.0, 0.17, since_drain)}

static func position_at(route: Array, time: float) -> Vector2:
	for i in range(1, route.size()):
		var stop: float = route[i][0]
		if time <= stop:
			var start: Vector2 = route[i - 1][1]
			var finish: Vector2 = route[i][1]
			var fraction := clampf(inverse_lerp(route[i - 1][0], stop, time), 0.0, 1.0)
			return start.lerp(finish, fraction)
	return route[-1][1]
