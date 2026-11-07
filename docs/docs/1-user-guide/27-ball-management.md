# Ball Management

Ball Management records physical observations and expected movements. Game Management decides whether those observations finish a logical turn. A physical ball inventory and **balls per player** are separate settings.

<img src="./media/screenshot-feature-ball.webp" data-source='{"url": "/login", "dark_mode": true, "settle_ms": 800, "click": [{"action": "type", "selector": "input[name=\"username\"]"}, {"action": "type", "selector": "input[name=\"password\"]"}, {"action": "click", "selector": "button[type=\"submit\"]", "wait_for": "[data-menu-toggle]"}], "next_url": "/ball/"}' alt="Ball Management observation overview" style="width:100%;height:auto;">

## Dashboard and setup

- **Dashboard** shows live sensor observations, in-play estimates, movement status and recent transitions.
- **Sensors** lists mapped switches and what they detect. Use **Add sensor** or a row’s **Edit** button to open the side panel.
- **Ball Locations** lists optional areas that can hold balls, such as a trough or lock. A sensor is the switch. A location is the place one or more switches monitor.
- **Settings** holds the machine’s total physical ball count and the sensor freshness timeout.

## Minimal machine

In **Settings**, set the number of physical balls. In **Sensors**, add the shooter-departure switch as **Launch** and the drain switch as **Drain**. Leave **Ball location** blank for those two switches. Set each switch’s active level and debounce interval. Save while no game is running, then **Sync Rules** to deploy the sensor watches.

Shooter departure adds one to the in-play estimate. Drain removes one when a corresponding estimate exists. Unknown is never treated as zero. The page shows configured physical inventory, inferred in-play count, confidence, sensor levels, last observations, pending movements and a transition timeline. Live View and Playfield also show the published manager summary; Media overlays read the current player, ball and credits from Game Management.

## Troughs, locks and other ball locations

Add a location such as **Trough** and set how many balls it can hold. Edit each trough switch in **Sensors** and select **Trough** as its ball location. Use **Occupancy** for switches that stay active while a ball is parked, or **Entrance** and **Exit** for switches that detect a ball passing through. Use **Lock** to detect a ball entering a lock. A confirmed occupancy count requires an observation from every configured occupancy switch at that location. Entrance and exit observations alone cannot establish an unknown initial count. Counts outside configured capacities require recovery.

### Example: three balls, a trough and a lock

Set **Physical balls in machine** to 3. Add a **Trough** with capacity 3 and a **Ball lock** with capacity 1. Map each switch to the role and location below.

| Switch | Role | Ball location |
| --- | --- | --- |
| Shooter departure | Launch | None |
| Playfield drain | Drain | None |
| Trough slots 1, 2 and 3 (one switch per slot) | Occupancy | Trough |
| Lock position (held active while a ball is parked) | Occupancy | Ball lock |

With two trough switches active and the lock switch active, the dashboard can show **2 / 3** in the trough and **1 / 1** in the lock once all four occupancy switches have reported. The lock switch in this example reports a parked ball. Leave release outputs unset while checking the sensors.

Use **Movement and release options** in the location’s side panel to configure an expected destination, timeout or optional release output.

A requested movement requires active gameplay, fresh confirmed occupancy, a configured destination and no existing movement from that device. Matching destination observations confirm the movement; timeout makes state uncertain and requires recovery. No retry/search sequence fires automatically.

An optional mapped release output and bounded pulse (1–250 ms) can be configured per device. **Request movement** records the expectation, then the existing bridge/ESP safety path sends one pulse request using a fresh firmware timestamp. ESP arming, stale-command, recovery and coil limits still apply. Missing clock support, rejected commands or uncertain delivery enter recovery. A durable send receipt prevents replay after a crash; an uncertain send may therefore be lost, rather than fired twice. Inspect the machine before deliberately requesting a new movement.

## Reset ball locations

While no game is active, select **Reset ball locations** beside **Settings**. Inspect the machine, then enter a whole-number count for every configured location, including zero for empty locations. Add locations such as the shooter lane or an under-table catch before counting them. Each count must fit the location's capacity, and the total must match **Physical balls in machine**.

The panel shows fresh occupancy readings alongside the counts. If the available readings contradict your count, review the difference and explicitly confirm that you want to use your numbers. Locations with incomplete readings or no occupancy switches are labelled accordingly. The dashboard shows saved manual counts separately from sensor counts. The reset clears the in-play estimate and pending movements without operating coils. Movement safety continues to require fresh sensor evidence. Manual counts are cleared when a new game starts, the Pi boots, a backup is restored, or the ball configuration changes.

## Startup and recovery

After a full Pi boot, the dashboard shows a six-second settling delay. With matching firmware and synced Rules, Ball Management then reads the levels of mapped occupancy switches, including ones already held by a parked ball. A location stays unknown until every configured occupancy switch for it has reported. A drain passage alone cannot confirm trough occupancy. The configured inventory remains a setup value.

If a ball stops where there is no sensor, inspect the machine and physically return the ball to the trough. For a mechanism with a mapped release coil, use the existing hardware test controls only after inspecting the mechanism. Startup does not fire coils or assume that all configured balls reached the trough.

A movement timeout, impossible drain or capacity mismatch can block an active game. Inspect the sensor readings and physical ball locations before starting another game.

Input simulation is available only when authorised test mode is enabled in Game Management. Simulated observations never operate outputs directly. Physical events carry explicit firmware provenance; generic event injection cannot create a trusted coin or physical observation.

These are configurable observations and one-shot controlled movements, not a universal mechanical driver, automatic ball-search engine or arbitrary multiball policy. Mechanism-specific retry/search behaviour remains excluded unless separately designed and safety-tested. Actual Pi/ESP sensors, pulse timing and mechanical release/arrival behaviour require physical validation.
