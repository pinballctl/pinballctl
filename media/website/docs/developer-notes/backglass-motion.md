# Backglass motion

The Hyrule demo keeps its painterly backgrounds, serif titles and gold framing.
The motion pass gives the 44-second attract film separate foreground layers
and shot effects. During a game, event cues land faster and spend most of their
screen time displaying the result. The menu and gameplay HUD use smaller
accents so selection and scores stay easy to read.

The bonus uses independent rupee seals, a tally and a single impact at the
controller-supplied total. Replacing the whole-plate spin gives the final amount
more reading time within the existing three-second window. Full tilt uses one
short impact followed by a stable message. The 1.1-second warning has its own
amber treatment and clears automatically.

The existing artwork and synthesized cues support the new motion. Drawing the
layers in Godot keeps preview pause and replay tied to the same timeline as live
play. Reduced motion fixes the camera, removes moving effects and exposes the
final bonus amount immediately. The controller continues to own the score and
the transition out of full tilt.

Godot's smoke tests cover quick returns, event interruption and preview replay.
The real renderer can capture each attract edit and the short bonus and tilt
timelines. Check frame pacing and readability on the cabinet display when
installing the updated pack.

The Godot project lives in `media/backglass/zelda/`. Its resource paths still
start with `res://zelda/`, so exported resources stay namespaced and Media
can load the same scene entry paths.

See [Backglass development](../developer-guide/backglass.md) for preview and
validation commands.


## Pinball CTL vector sample

The cabinet-themed sample has its own Godot project under
`media/backglass/sample/`. The first scope covers attract, menu, high scores,
tilt, bonus and game over. Each scene now has its own vector backdrop.
Attract uses the original drifting rays and arcs. Menu fans rays out from
below the cabinet. Mode pairs curved cool rays with angular warm rays.
High Scores uses shallow perspective rays behind the rows. Tilt sends a
zigzag out through the shock arcs, and Bonus opens an upward gold burst.
Game Over uses the swirl first tried on Attract, with slower purple ribbons
centred near Relay. The Ball in Play scoreboard uses sweeping diagonal rays. Drifting stars carry through
the scenes and fade to 30% opacity before brightening. Relay, the
original pinball-headed host, enters independently of the cue plate. He
recoils for Tilt, throws one hand up at the Bonus landing, and slumps with
his eyes down for Game Over. The Cabinet Host concept supplied a single PNG.
Relay's steel shell, wide visor, rounded shoes and hands were redrawn as
separate vector parts so the same design can move into each pose.
Relay’s gloves and boots attach at wrist and ankle pivots. Shorter arm poses
and larger gloves bring the proportions closer to the Cabinet Host concept.
Tilt uses red eyes and open palms, and Bonus uses a raised fist and a laugh.
At Game Over, Relay glances back at the score, wipes a tear and sighs.
Mode gives
Easy a rounded panel and Hard an angular panel. Relay stays in the gap
and points at the highlighted choice with a different pose for each side.
Relay was removed from the menu,
where the choices obscured him. The Game Over drain artwork was removed.

Attract remains one continuous composition. A 38-second cut brings the first
launch forward from 18 to 15 seconds. The logo moved into a shared header.
Relay starts with a smaller silhouette centred from the first frame,
including his raised glove and shoes. He crouches, jumps aside and lands
with a short squash and rebound. During assembly Relay follows
the falling parts with his eyes, alternating between surprise, inspection
and a grin. A candy-striped bar beneath Relay shows build progress and names
each part as it arrives. The same panel carries shot updates during play.
Moving those updates away from the score gives the commas room. The shot
poses move his head and limbs while his body stays
upright. The first ball has a curious look, a target wink and a worried
drain. The second gives Relay a sideways glance, shrug, open-palm gesture and
deadpan finish. On the third he squints, braces at launch and saves the
two-fist hop for the biggest flipper shot. Each full gesture is assigned
to one scripted contact. Other hits move the ball and its score while
Relay follows it with his eyes. The closing nod gives the opening wave
its own place in the loop.
The table now has an animated plunger and three drop targets that register
hits, award points and reset for the next ball. Earlier edits tested cuts
between separate title, build and replay layouts, then a 44-second continuous
version with a large logo panel. The shared header leaves more room for the
character and playfield. A soft gradient passes behind the Press Start label.
Start can interrupt Attract immediately. Bonus lands
in 0.65 seconds and releases its Media session at 2.12 seconds. Tilt clears in
1.20 seconds. Game Over holds the final score for a 10-second cue before
handing the display back to Media.

The local Media configuration contains the eight vector entries and uses
Attract as the display default. The Start request goes through the Game
manager. `GAME_STARTED` opens the Relay scoreboard and `GAME_ENDED` plays
Game Over, which returns to Attract after ten seconds. The vector pack has
no initials-entry scene. The local replacement removed the Hyrule Media
entries and archived the old configuration and pack.
The Game Started entry displays **Ball in Play** above its 30-second
scoreboard loop. Relay has the space
beside the live scoreboard to himself. He draws eight gestures and
expressions per pass from a reusable shuffled library of sixteen.
The first and last beats settle into
the same pose. The score, player and ball use the existing backglass
state feed and stay visible throughout. The vector entries are registered
for Media playback.
A live Bonus cue still needs a bonus amount supplied by the controller.

The player, ball and score come from controller text values and scoreboards.
Cabinet buttons use the existing action mappings, and Start requests a rule
rather than changing game state in the presentation. The host completes queued
cues by session ID so a late request cannot dismiss the next cue. Exported scene
loading and queue behavior are covered by automated tests. Cabinet frame
pacing and switch mappings need verification on the target hardware.

The menu opens a dedicated Mode screen. Easy and Hard emit distinct rule
events only on confirmation. The backglass remembers the current selection
within its scene instance and accepts the controller's mode on future loads.

See the [Pinball CTL vector sample](../user-guide/godot.md#pinball-ctl-vector-sample)
for setup.
