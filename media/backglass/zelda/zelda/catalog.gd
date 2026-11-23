extends RefCounted

const QUESTS = [
	{"name": "Korok Forest", "subtitle": "Awaken the forest", "goal": "Complete the three forest targets", "color": "78cba0", "point": Vector2(390, 610)},
	{"name": "Death Mountain", "subtitle": "Heart of the volcano", "goal": "Build the fire meter with ramp shots", "color": "efaa68", "point": Vector2(620, 340)},
	{"name": "Lake Hylia", "subtitle": "Beneath still waters", "goal": "Shoot the orbit to raise the water", "color": "76c9e5", "point": Vector2(950, 710)},
	{"name": "Temple of Time", "subtitle": "The song of awakening", "goal": "Collect three sacred stones", "color": "e4cd89", "point": Vector2(1040, 370)},
	{"name": "Spirit Temple", "subtitle": "Beyond the desert", "goal": "Alternate left and right ramp shots", "color": "dfaf80", "point": Vector2(1450, 660)},
	{"name": "Ganon's Castle", "subtitle": "The final confrontation", "goal": "Light every jackpot to defeat the darkness", "color": "c1a0eb", "point": Vector2(1490, 320)},
]
# id, heading, eyebrow, subtitle, background, duration, motif
const SCREENS = [
	["attract", "THE HERO OF TIME", "A HYRULE PINBALL ADVENTURE", "A sleeping kingdom. A timeless adventure.", "hyrule", 44.0, "triforce"],
	["gameplay", "KOROK FOREST", "THE QUEST BEGINS", "Complete the three forest targets", "hyrule", 0.0, "rupee"],
	["skill_shot", "TAKE YOUR SHOT", "SKILL SHOT", "Time the plunge. Find your mark.", "hyrule", 6.0, "target"],
	["skill_success", "TRUE AIM", "SKILL SHOT COMPLETE", "A hero's journey begins with one perfect shot.", "hyrule", 1.4, "target"],
	["skill_missed", "THE QUEST CONTINUES", "SKILL SHOT MISSED", "The next adventure is already waiting.", "hyrule", 1.1, "target"],
	["bonus", "TREASURES OF HYRULE", "END OF BALL BONUS", "Every adventure leaves its reward.", "temple", 3.0, "rupee"],
	["multiball", "TRIFORCE MULTIBALL", "POWER  /  WISDOM  /  COURAGE", "Three forces awaken. Keep every ball alive.", "temple", 7.0, "triforce"],
	["jackpot", "JACKPOT", "A TREASURE REVEALED", "The kingdom rewards your courage.", "temple", 1.6, "rupee"],
	["super_jackpot", "SUPER JACKPOT", "THE SACRED REALM OPENS", "Power. Wisdom. Courage. United.", "temple", 2.2, "triforce"],
	["ball_saved", "A FAIRY'S BLESSING", "BALL SAVED", "Your adventure is not over yet.", "hyrule", 1.5, "fairy"],
	["extra_ball", "ANOTHER CHANCE", "EXTRA BALL", "A new heart. A new adventure.", "temple", 1.8, "heart"],
	["quest_complete", "A SAGE AWAKENS", "QUEST COMPLETE", "Another light returns to Hyrule.", "temple", 2.2, "medallion"],
	["wizard", "THE FINAL BATTLE", "GANON'S CASTLE", "Face the darkness. Free the kingdom.", "dark", 8.0, "triforce"],
	["victory", "HYRULE RESTORED", "THE HERO RETURNS", "Your courage will echo through time.", "hyrule", 9.0, "medallion"],
	["ball_lost", "A MOMENT IN TIME", "BALL LOST", "Gather your treasures. Prepare for the next journey.", "hyrule", 1.2, "rupee"],
	["tilt_warning", "STEADY, HERO", "TILT WARNING", "Let the kingdom settle.", "dark", 1.1, "medallion"],
	["tilt", "TIME STANDS STILL", "TILT", "Wait for the controller to resume play.", "dark", 0.0, "medallion"],
	["game_over", "A LEGEND REMEMBERED", "GAME OVER", "Every ending is the beginning of a new legend.", "hyrule", 10.0, "triforce"],
	["initials", "WRITE YOUR LEGEND", "HIGH SCORE", "Choose three letters for the chronicles.", "temple", 0.0, "medallion"],
	["records", "THE CHRONICLES", "HEROES OF HYRULE", "Courage is remembered.", "temple", 0.0, "medallion"],
]

static func screen(id: String) -> Array:
	for entry in SCREENS:
		if entry[0] == id:
			return entry
	return []
